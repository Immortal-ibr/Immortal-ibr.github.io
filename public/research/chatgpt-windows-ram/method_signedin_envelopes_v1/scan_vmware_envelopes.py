"""Scan resident browser renderer mappings in a VMware memory snapshot.

The bounded JSON parser receives no prompt, answer, conversation ID, or offset.
Full accepted records are written only to a private output path.
"""

import argparse
import json
import os
from pathlib import Path
import sys


METHODS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(METHODS / "method_vmware_snapshot_v1"))

from browser_json_envelopes import scan  # noqa: E402
from scan_vmware_snapshot import PhysicalReader, verify_samples  # noqa: E402


REPOSITORY = Path(__file__).resolve().parents[4]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", type=Path, required=True)
    cli.add_argument("--vmem", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, required=True)
    cli.add_argument("--pid", type=int, required=True)
    cli.add_argument("--process-name", choices=("msedge.exe", "chrome.exe"), required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()

    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Unfiltered records must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)

    rows = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    highest_physical_end = max(int(row["Physical"]) + int(row["Size"]) for row in rows)
    sdk = args.sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs

    vmm = memprocfs.Vmm(["-device", str(args.vmem.resolve(strict=True))])
    try:
        process = vmm.process(args.pid)
        if process.name.casefold() != args.process_name.casefold():
            raise ValueError("Selected PID does not match --process-name")
        flags = memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING
        samples = verify_samples(vmm, process, rows, flags)
        reader = PhysicalReader(vmm.memory, flags)
        result = scan(reader, rows, highest_physical_end)
        result.update({
            "pid": args.pid,
            "process_name": process.name,
            "translation_samples": samples,
            "physical_read_failures": reader.failed_reads,
        })
        with output.open("x", encoding="utf-8") as target:
            json.dump(result, target, indent=2, ensure_ascii=True)
            target.write("\n")
        print(json.dumps({
            "pid": args.pid,
            "unique_complete_records": result["unique_complete_records"],
            "stats": result["stats"],
            "translation_samples": samples,
            "physical_read_failures": reader.failed_reads,
        }))
    finally:
        del vmm
        if dll:
            dll.close()


if __name__ == "__main__":
    main()
