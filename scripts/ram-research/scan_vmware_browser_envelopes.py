"""Private structural envelope scan of VMware-snapshot renderer mappings.

No target text or conversation identifier is an input. Full accepted JSON
objects stay in the requested private output outside the blog repository.
"""

import argparse
import json
import os
from pathlib import Path
import sys

from browser_json_envelopes import scan as scan_envelopes
from sse_event_records import scan as scan_sse
from scan_vmware_snapshot import PhysicalReader, verify_samples


REPOSITORY = Path(__file__).resolve().parents[2]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", type=Path, required=True)
    cli.add_argument("--vmem", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, required=True)
    cli.add_argument("--pid", type=int, required=True)
    cli.add_argument("--process-name", choices=("msedge.exe", "chrome.exe"),
                     default="msedge.exe")
    cli.add_argument("--parser", choices=("browser-envelopes", "sse-events"),
                     default="browser-envelopes")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Unfiltered renderer objects must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    rows = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    image_size = max(int(row["Physical"]) + int(row["Size"]) for row in rows)
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
        parser = scan_envelopes if args.parser == "browser-envelopes" else scan_sse
        result = parser(reader, rows, image_size)
        result.update({"pid": args.pid, "process_name": process.name,
                       "parser": args.parser,
                       "translation_samples": samples,
                       "physical_read_failures": reader.failed_reads})
        with output.open("x", encoding="utf-8") as target:
            json.dump(result, target, indent=2, ensure_ascii=True)
            target.write("\n")
        print(json.dumps({"pid": args.pid, "stats": result["stats"],
                          "unique_complete_records": result["unique_complete_records"],
                          "translation_samples": samples,
                          "physical_read_failures": reader.failed_reads}))
    finally:
        del vmm
        if dll:
            dll.close()


if __name__ == "__main__":
    main()
