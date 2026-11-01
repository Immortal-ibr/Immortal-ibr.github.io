"""Explain the unavailable cross-check samples without printing memory contents."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", required=True, type=Path)
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--crosscheck", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite diagnostics")
    sdk = args.sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll_scope = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs

    crosscheck = json.loads(args.crosscheck.read_text(encoding="utf-8"))
    vmm = memprocfs.Vmm(["-device", str(args.image.resolve(strict=True))])
    process = vmm.process(crosscheck["pid_checked"])
    diagnostics = []
    address_mask = ((1 << 52) - 1) & ~0xFFF
    with args.image.open("rb") as source:
        for sample in crosscheck["samples"]:
            if sample.get("physical_match") and sample.get("bytes_match"):
                continue
            virtual = sample["virtual"]
            row = {"virtual": virtual, "volatility_physical": sample["volatility_physical"],
                   "dtb": process.dtb, "page_table_walk": [], "read_modes": {}}
            table = process.dtb & address_mask
            for level, shift in ((4, 39), (3, 30), (2, 21), (1, 12)):
                entry_address = table + ((virtual >> shift) & 0x1FF) * 8
                source.seek(entry_address)
                entry = int.from_bytes(source.read(8), "little")
                row["page_table_walk"].append({"level": level, "physical_address": entry_address,
                                              "entry": entry, "present_bit": bool(entry & 1)})
                if not (entry & 1) or (level in (2, 3) and entry & (1 << 7)):
                    break
                table = entry & address_mask
            source.seek(sample["volatility_physical"])
            expected = source.read(sample["bytes_compared"])
            for name, flags in (("resident_only", memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING),
                                ("default_page_recovery", memprocfs.FLAG_NOCACHE)):
                try:
                    observed = process.memory.read(virtual, sample["bytes_compared"], flags)
                    row["read_modes"][name] = {"length": len(observed), "bytes_match": observed == expected,
                                              "sha256": hashlib.sha256(observed).hexdigest()}
                except Exception as error:
                    row["read_modes"][name] = {"error": type(error).__name__}
            diagnostics.append(row)
    result = {"pid": crosscheck["pid_checked"], "diagnostics": diagnostics,
              "scope": "page-table flags and read behavior; no content printed or known turn values used"}
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    print(json.dumps(result, indent=2))
    del vmm
    if dll_scope is not None:
        dll_scope.close()


if __name__ == "__main__":
    main()
