"""Reread one mapped copy per draft encoding with independent MemProcFS.

This is a post-hoc byte/map check, not blind turn reconstruction. The draft
observation is used only after the frozen parser's output has been sealed.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys

from posthoc_draft_known_text import REPOSITORY, draft_prompt


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", type=Path, required=True)
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--hit-report", type=Path, required=True)
    cli.add_argument("--draft-observation", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY) or output.exists():
        raise ValueError("Cross-check output must be new and private")

    observation = json.loads(args.draft_observation.read_text(encoding="utf-8-sig"))
    prompt = draft_prompt(observation)
    needles = {f"prompt/{encoding}": prompt.encode(encoding)
               for encoding in ("utf-8", "utf-16-le")}
    report = json.loads(args.hit_report.read_text(encoding="utf-8-sig"))
    if report.get("ground_truth_supplied") is not True or report.get("submission_attempted") is not False:
        raise ValueError("Expected a labeled unsent-draft diagnostic")

    sdk = args.sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll_scope = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs

    image = args.image.resolve(strict=True)
    vmm = memprocfs.Vmm(["-device", str(image)])
    checks = []
    try:
        with image.open("rb", buffering=0) as raw:
            for process_map in report["process_maps"]:
                match = re.fullmatch(r"memmap-(\d+)\.json", process_map["mapfile"])
                if not match:
                    raise ValueError("Unexpected private process-map name")
                pid = int(match.group(1))
                process = vmm.process(pid)
                for label, hit in process_map["first_hits_private"].items():
                    needle = needles[label]
                    virtual, physical = hit["virtual"], hit["physical"]
                    raw.seek(physical)
                    physical_bytes = raw.read(len(needle))
                    translated = process.memory.virt2phys(virtual)
                    mapped_bytes = process.memory.read(
                        virtual, len(needle), memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING
                    )
                    checks.append({
                        "pid": pid, "label": label,
                        "virtual_private": virtual, "physical_private": physical,
                        "length_matches": len(needle) == hit["byte_length"],
                        "translation_matches": translated == physical,
                        "raw_bytes_match": physical_bytes == needle,
                        "memprocfs_bytes_match": mapped_bytes == needle,
                    })
    finally:
        del vmm
        if dll_scope:
            dll_scope.close()
    result = {
        "method": "MemProcFS reread of first mapped synthetic draft hit per encoding",
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
    print(json.dumps({key: value for key, value in result.items() if key != "checks_private"}))


if __name__ == "__main__":
    main()
