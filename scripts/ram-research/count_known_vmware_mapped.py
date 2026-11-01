"""Post-hoc known-value control on VMware-aware resident renderer mappings.

This is deliberately not a conversation parser. Values must come from an
independent UI observation, and the resulting counts cannot establish a turn.
Keep the known-value input and output private for signed-in profiles.
"""

import argparse
import json
import os
from pathlib import Path
import sys

from bounded_json import MappedReader, normalize_rows
from scan_vmware_snapshot import PhysicalReader


def count_mapped(source, values, image_size, needles):
    rows, skipped = normalize_rows(values, image_size)
    mapped = MappedReader(source, rows)
    overlap = max(map(len, needles.values())) - 1
    counts = dict.fromkeys(needles, 0)
    scanned = 0
    short_reads = 0
    for start, size in mapped.runs():
        tail = b""
        for position in range(start, start + size, 1024 * 1024):
            wanted = min(1024 * 1024, start + size - position)
            block, _ = mapped.read(position, wanted)
            scanned += len(block)
            window = tail + block
            for label, needle in needles.items():
                cursor = 0
                while (offset := window.find(needle, cursor)) != -1:
                    counts[label] += 1
                    cursor = offset + 1
            if len(block) != wanted:
                short_reads += 1
                tail = b""
            else:
                tail = window[-overlap:] if overlap else b""
    return {"mapped_counts": counts, "resident_user_rows": len(rows),
            "skipped_kernel_rows": skipped, "scanned_bytes_with_possible_aliases": scanned,
            "short_reads": short_reads}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", required=True, type=Path)
    cli.add_argument("--vmem", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--pid", required=True, type=int)
    cli.add_argument("--known-json", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    known = json.loads(args.known_json.read_text(encoding="utf-8"))
    if not isinstance(known, dict) or not known or not all(
        isinstance(label, str) and isinstance(value, str) and value
        for label, value in known.items()
    ):
        raise ValueError("known-json must be a nonempty mapping of labels to strings")
    needles = {f"{label}/{encoding}": value.encode(encoding)
               for label, value in known.items()
               for encoding in ("utf-8", "utf-16-le")}
    values = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    image_size = max(int(row["Physical"]) + int(row["Size"]) for row in values)
    sdk = args.sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs
    vmm = memprocfs.Vmm(["-device", str(args.vmem.resolve(strict=True))])
    try:
        process = vmm.process(args.pid)
        if process.name.casefold() not in {"msedge.exe", "chrome.exe", "chatgpt.exe"}:
            raise ValueError("PID is not a selected browser renderer process")
        flags = memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING
        reader = PhysicalReader(vmm.memory, flags)
        result = {"method": "post-hoc exact-value count, not blind reconstruction",
                  "process_name": process.name, "pid": args.pid,
                  **count_mapped(reader, values, image_size, needles),
                  "memprocfs_physical_read_failures": reader.failed_reads}
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        del vmm
        if dll:
            dll.close()


if __name__ == "__main__":
    main()
