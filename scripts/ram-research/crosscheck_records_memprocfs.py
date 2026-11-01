"""Check every recovered record occurrence against independent MemProcFS reads."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", type=Path, required=True)
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--records", type=Path, required=True)
    cli.add_argument("--pid", type=int, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to replace a cross-check")
    sdk = args.sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs
    vmm = memprocfs.Vmm(["-device", str(args.image.resolve(strict=True))])
    process = vmm.process(args.pid)
    recovered = json.loads(args.records.read_text(encoding="utf-8"))
    results = []
    for record in recovered["records"]:
        digest = record.get("record_sha256", record.get("sha256"))
        byte_length = record.get("raw_byte_length", record.get("byte_length"))
        addresses = record.get("source_virtual_addresses", record.get("virtual_addresses"))
        if not digest or not byte_length or addresses is None:
            raise ValueError("Recovered record lacks byte digest, length, or addresses")
        for address, spans in zip(addresses, record["source_spans"], strict=True):
            value = {"virtual": address, "record_sha256": digest,
                     "raw_byte_length": byte_length, "translations": []}
            try:
                raw = process.memory.read(address, byte_length,
                                          memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING)
                value["memprocfs_sha256"] = hashlib.sha256(raw).hexdigest()
                value["bytes_match"] = value["memprocfs_sha256"] == digest
                for span in spans:
                    physical = process.memory.virt2phys(span["virtual"])
                    value["translations"].append({"virtual": span["virtual"], "volatility_physical": span["physical"],
                                                   "memprocfs_physical": physical, "match": physical == span["physical"]})
            except Exception as error:
                value["error"] = type(error).__name__
            results.append(value)
    result = {"method": "same-image independent MemProcFS reads of every recovered record occurrence",
              "pid": args.pid, "record_count": len(recovered["records"]), "occurrences": results,
              "all_record_bytes_and_translations_match": bool(results) and all(
                  value.get("bytes_match") and value.get("translations") and
                  all(span["match"] for span in value["translations"]) for value in results),
              "exclusive_physical_page_ownership_claimed": False}
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    print(json.dumps({key: value for key, value in result.items() if key != "occurrences"}, indent=2))
    del vmm
    if dll:
        dll.close()


if __name__ == "__main__":
    main()
