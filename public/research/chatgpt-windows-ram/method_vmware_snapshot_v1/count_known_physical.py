"""Count known text in VMware guest-physical RAM after blind parsing.

This is a post-hoc diagnostic, not a conversation reconstruction. The input
values must come from an independently recorded page observation. The output
contains offsets and value hashes, never the values or surrounding RAM.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


CHUNK = 4 * 1024 * 1024


def scan_ranges(memory, ranges, needles, flags, chunk_size=CHUNK):
    if not needles or chunk_size <= 0:
        raise ValueError("At least one needle and a positive chunk size are required")
    hits = {label: set() for label in needles}
    overlap = max(map(len, needles.values())) - 1
    bytes_read = 0
    failed_reads = []
    for start, size in ranges:
        if start < 0 or size < 0:
            raise ValueError("Invalid physical memory range")
        carry = b""
        position = start
        end = start + size
        while position < end:
            amount = min(chunk_size, end - position)
            try:
                block = memory.read(position, amount, flags)
            except RuntimeError:
                block = b""
            if len(block) != amount:
                failed_reads.append({"physical_start": position, "bytes": amount})
                carry = b""
                position += amount
                continue
            bytes_read += amount
            window = carry + block
            base = position - len(carry)
            for label, needle in needles.items():
                cursor = 0
                while (found := window.find(needle, cursor)) != -1:
                    hits[label].add(base + found)
                    cursor = found + 1
            carry = window[-overlap:] if overlap else b""
            position += amount
    return {"hits": {label: sorted(offsets) for label, offsets in hits.items()},
            "bytes_read": bytes_read, "failed_reads": failed_reads}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", type=Path, required=True)
    cli.add_argument("--vmem", type=Path, required=True)
    cli.add_argument("--known-json", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    known = json.loads(args.known_json.read_text(encoding="utf-8-sig"))
    if not isinstance(known, dict) or not known or not all(
        isinstance(label, str) and isinstance(value, str) and value
        for label, value in known.items()
    ):
        raise ValueError("known-json must map labels to nonempty strings")
    needles = {f"{label}/{encoding}": value.encode(encoding)
               for label, value in known.items()
               for encoding in ("utf-8", "utf-16-le")}
    sdk = args.sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs

    vmm = memprocfs.Vmm(["-device", str(args.vmem.resolve(strict=True))])
    try:
        ranges = vmm.maps.memmap()
        flags = memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING
        scan = scan_ranges(vmm.memory, ranges, needles, flags)
        result = {
            "method": "post-hoc exact-value count in VMware guest-physical ranges",
            "blind_reconstruction": False,
            "snapshot": args.vmem.name,
            "physical_ranges": ranges,
            "value_sha256": {label: hashlib.sha256(value.encode("utf-8")).hexdigest().upper()
                             for label, value in known.items()},
            "counts": {label: len(offsets) for label, offsets in scan["hits"].items()},
            **scan,
        }
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"snapshot": args.vmem.name, "counts": result["counts"],
                          "bytes_read": result["bytes_read"],
                          "failed_reads": len(result["failed_reads"])}))
    finally:
        del vmm
        if dll:
            dll.close()


if __name__ == "__main__":
    main()
