"""Run the frozen SSE framer on a compact VMware saved-memory state.

Volatility's windows.memmap gives guest-physical addresses. MemProcFS resolves
those addresses through VMware metadata; they are not flat .vmem file offsets.
No prompt, answer, conversation ID, message ID or memory offset is an input.
Unfiltered SSE output must stay outside the public repository.
"""

import argparse
import json
import os
from pathlib import Path
import sys

from bounded_json import USER_LIMIT
from sse_event_records import scan


REPOSITORY = Path(__file__).resolve().parents[4]


class PhysicalReader:
    def __init__(self, memory, flags):
        self.memory = memory
        self.flags = flags
        self.position = 0
        self.failed_reads = 0

    def seek(self, position):
        if position < 0:
            raise ValueError("Negative physical address")
        self.position = position

    def read(self, amount):
        try:
            data = self.memory.read(self.position, amount, self.flags)
        except RuntimeError:
            self.failed_reads += 1
            return b""
        self.position += len(data)
        return data


def verify_samples(vmm, process, rows, flags, count=32):
    user = [row for row in rows if int(row["Virtual"]) < USER_LIMIT]
    if not user:
        raise ValueError("No resident user mappings")
    indexes = sorted({round(i * (len(user) - 1) / max(1, count - 1))
                      for i in range(min(count, len(user)))})
    matched = 0
    for index in indexes:
        row = user[index]
        virtual, physical = int(row["Virtual"]), int(row["Physical"])
        observed_physical = process.memory.virt2phys(virtual)
        if observed_physical != physical:
            raise ValueError(f"Virtual/physical translation mismatch at sample {index}")
        by_process = process.memory.read(virtual, 16, flags)
        by_physical = vmm.memory.read(physical, 16, flags)
        if by_process != by_physical or len(by_process) != 16:
            raise ValueError(f"Virtual/physical byte mismatch at sample {index}")
        matched += 1
    return {"requested": len(indexes), "matched": matched}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", type=Path, required=True)
    cli.add_argument("--vmem", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, required=True)
    cli.add_argument("--pid", type=int, required=True)
    cli.add_argument("--process-name", choices=("msedge.exe", "chrome.exe"),
                     default="msedge.exe")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Unfiltered signed-in records must stay outside the repository")
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
        result = scan(reader, rows, image_size)
        result.update({"pid": args.pid, "process_name": process.name,
                       "memprocfs_volatility_samples": samples,
                       "physical_read_failures": reader.failed_reads})
        with output.open("x", encoding="utf-8") as target:
            json.dump(result, target, indent=2, ensure_ascii=True)
            target.write("\n")
        print(json.dumps({"pid": args.pid,
                          "unique_complete_records": result["unique_complete_records"],
                          "contiguous_segments": len(result["contiguous_segments"]),
                          "samples": samples,
                          "physical_read_failures": reader.failed_reads}))
    finally:
        del vmm
        if dll:
            dll.close()


if __name__ == "__main__":
    main()
