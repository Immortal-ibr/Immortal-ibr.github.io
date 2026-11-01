"""Independently reread first post-hoc synthetic-byte hits with MemProcFS.

This verifies the Volatility virtual-to-physical map and exact bytes at sampled
hit locations. It does not reconstruct a turn or prove page ownership.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from count_known_raw_gzip import known_values, load


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--sdk-root", type=Path, required=True)
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--hit-report", type=Path, required=True)
    cli.add_argument("--submission", type=Path, required=True)
    cli.add_argument("--observation", type=Path, required=True)
    cli.add_argument("--ids", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    values = known_values(load(args.submission), load(args.observation), load(args.ids))
    needles = {f"{name}/{encoding}": value.encode(encoding)
               for name, value in values.items() for encoding in ("utf-8", "utf-16-le")}
    sdk = args.sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs

    vmm = memprocfs.Vmm(["-device", str(args.image.resolve(strict=True))])
    results = []
    with args.image.open("rb") as raw:
        for process_map in load(args.hit_report)["process_maps"]:
            match = re.fullmatch(r"pid_(\d+)_memmap\.json", process_map["mapfile"])
            if not match:
                raise ValueError("Expected a PID-labeled private map")
            pid = int(match.group(1))
            process = vmm.process(pid)
            for label, hit in process_map["first_hits_private"].items():
                needle = needles[label]
                if len(needle) != hit["byte_length"]:
                    raise ValueError("Hit length disagrees with private ground truth")
                virtual = hit["virtual"]
                physical = hit["physical"]
                raw.seek(physical)
                physical_bytes = raw.read(len(needle))
                mapped_physical = process.memory.virt2phys(virtual)
                mapped_bytes = process.memory.read(
                    virtual, len(needle), memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING
                )
                results.append({
                    "pid": pid, "label": label,
                    "physical_address_matches": mapped_physical == physical,
                    "raw_bytes_match": physical_bytes == needle,
                    "memprocfs_bytes_match": mapped_bytes == needle,
                })
    summary = {
        "method": "MemProcFS reread of one first mapped hit per nonzero value and encoding",
        "hits_checked": len(results),
        "all_translations_and_bytes_match": bool(results) and all(
            hit["physical_address_matches"] and hit["raw_bytes_match"] and hit["memprocfs_bytes_match"]
            for hit in results
        ),
        "checks": results,
        "not_a_turn_reconstruction": True,
    }
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "checks"}, indent=2))
    del vmm
    if dll:
        dll.close()


if __name__ == "__main__":
    main()
