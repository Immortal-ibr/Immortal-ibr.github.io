"""Private, post-hoc format-development inspection around synthetic UI markers.

This is not blind reconstruction or a scored parser. It saves bounded source
contexts outside the repository; stdout contains only field-name summaries.
"""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from bounded_json import MappedReader, normalize_rows
from scan_vmware_snapshot import PhysicalReader


REPOSITORY = Path(__file__).resolve().parents[2]


def inspect(mapped, runs, markers, max_each=5, before=512, after=1024):
    found = {label: [] for label in markers}
    overlap = max(map(len, markers.values())) - 1
    for run_start, run_size in runs:
        run_end = run_start + run_size
        tail = b""
        for position in range(run_start, run_end, 1024 * 1024):
            block, _ = mapped.read(position, min(1024 * 1024, run_end - position))
            window = tail + block
            base = position - len(tail)
            for label, (encoding, marker) in markers.items():
                cursor = 0
                while (offset := window.find(marker, cursor)) != -1:
                    address = base + offset
                    cursor = offset + 1
                    if len(found[label]) >= max_each:
                        continue
                    left = min(before, address - run_start)
                    left -= left % 2
                    start = address - left
                    context, spans = mapped.read(start, min(left + len(marker) + after,
                                                            run_end - start))
                    decoded = context.decode(encoding, errors="replace")
                    keys = re.findall(r'"([A-Za-z_][A-Za-z0-9_]{0,79})"\s*:', decoded)
                    found[label].append({
                        "virtual_address": address,
                        "context_start": start,
                        "context_sha256": hashlib.sha256(context).hexdigest(),
                        "context_base64_private": base64.b64encode(context).decode("ascii"),
                        "source_spans": spans,
                        "field_names_near_marker": keys,
                    })
            tail = window[-overlap:] if overlap else b""
    return found


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", required=True, type=Path)
    cli.add_argument("--vmem", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--pid", required=True, type=int)
    cli.add_argument("--known-json", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Unfiltered context output must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    known = json.loads(args.known_json.read_text(encoding="utf-8"))
    markers = {f"{name}/{encoding}": (encoding, value.encode(encoding))
               for name, value in known.items()
               for encoding in ("utf-8", "utf-16-le")}
    values = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    image_size = max(int(row["Physical"]) + int(row["Size"]) for row in values)
    rows, skipped = normalize_rows(values, image_size)
    sdk = args.sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs
    vmm = memprocfs.Vmm(["-device", str(args.vmem.resolve(strict=True))])
    try:
        process = vmm.process(args.pid)
        if process.name.casefold() != "msedge.exe":
            raise ValueError("PID is not an Edge process")
        flags = memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING
        reader = PhysicalReader(vmm.memory, flags)
        mapped = MappedReader(reader, rows)
        found = inspect(mapped, mapped.runs(), markers)
        result = {"method": "private post-hoc format development",
                  "pid": args.pid, "skipped_kernel_rows": skipped,
                  "physical_read_failures": reader.failed_reads,
                  "contexts": found}
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({label: [row["field_names_near_marker"]
                                  for row in occurrences]
                          for label, occurrences in found.items()}))
    finally:
        del vmm
        if dll:
            dll.close()


if __name__ == "__main__":
    main()
