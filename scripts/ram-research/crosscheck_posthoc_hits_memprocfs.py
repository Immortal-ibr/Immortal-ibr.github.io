"""Verify first exact-value mapped hits with independent MemProcFS reads.

This is a post-hoc diagnostic. It receives synthetic UI ground truth and
cannot reconstruct a turn or prove exclusive process ownership of a page.
The output contains private virtual and physical addresses.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys


REPOSITORY = Path(__file__).resolve().parents[2]
MAP_NAME = re.compile(r"(?:renderer|network|process)_(\d+)_memmap\.json\Z|memmap-(\d+)\.json\Z")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", type=Path, required=True)
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--hit-report", type=Path, action="append", required=True)
    cli.add_argument("--known-values", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY) or output.exists():
        raise ValueError("Private cross-check output must be new and outside the repository")
    known = json.loads(args.known_values.read_text(encoding="utf-8-sig"))
    values = {key: known[key] for key in ("conversation_id", "prompt", "response")}
    needles = {f"{key}/{encoding}": value.encode(encoding)
               for key, value in values.items()
               for encoding in ("utf-8", "utf-16-le")}
    sdk = args.sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll_scope = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs

    image = args.image.resolve(strict=True)
    vmm = memprocfs.Vmm(["-device", str(image)])
    checks = []
    with image.open("rb", buffering=0) as raw:
        for report_path in args.hit_report:
            report = json.loads(report_path.read_text(encoding="utf-8-sig"))
            if report.get("ground_truth_supplied") is not True:
                raise ValueError(f"Not a labeled post-hoc report: {report_path}")
            for process_map in report["renderer_maps"]:
                match = MAP_NAME.fullmatch(process_map["mapfile"])
                if not match:
                    raise ValueError("Unexpected map filename in post-hoc report")
                pid = int(match.group(1) or match.group(2))
                process = vmm.process(pid)
                for label, hit in process_map["first_hits_private"].items():
                    needle = needles[label]
                    virtual = hit["virtual"]
                    physical = hit["physical"]
                    raw.seek(physical)
                    physical_bytes = raw.read(len(needle))
                    translated = process.memory.virt2phys(virtual)
                    mapped_bytes = process.memory.read(
                        virtual, len(needle), memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING
                    )
                    checks.append({
                        "pid": pid, "label": label, "virtual_private": virtual,
                        "physical_private": physical,
                        "length_matches": len(needle) == hit["byte_length"],
                        "translation_matches": translated == physical,
                        "raw_bytes_match": physical_bytes == needle,
                        "memprocfs_bytes_match": mapped_bytes == needle,
                    })
    result = {
        "method": "MemProcFS reread of first mapped synthetic-value hit per process/encoding",
        "ground_truth_supplied": True,
        "not_a_turn_reconstruction": True,
        "hits_checked": len(checks),
        "all_checks_match": bool(checks) and all(
            check["length_matches"] and check["translation_matches"]
            and check["raw_bytes_match"] and check["memprocfs_bytes_match"]
            for check in checks
        ),
        "checks_private": checks,
    }
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "checks_private"}, indent=2))
    del vmm
    if dll_scope:
        dll_scope.close()


if __name__ == "__main__":
    main()
