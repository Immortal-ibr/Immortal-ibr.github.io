"""Count bounded browser record formats in a VMware saved-memory snapshot.

Volatility supplies each renderer's resident virtual-to-guest-physical map.
MemProcFS supplies VMware-aware guest-physical reads: a .vmem file can be
shorter than the highest guest physical address, so treating offsets in it as
a flat WinPmem raw image would silently miss pages. No record content is
written to the output; this is unscored format triage, not conversation proof.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from bounded_json import USER_LIMIT, scan as scan_stream
from chrome_state_records import scan as scan_state


class PhysicalReader:
    """Minimal seek/read adapter for MemProcFS guest physical memory."""

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
        if amount < 0:
            raise ValueError("Negative read length")
        try:
            data = self.memory.read(self.position, amount, self.flags)
        except RuntimeError:
            self.failed_reads += 1
            return b""
        self.position += len(data)
        return data


def state_turn_shape(record):
    state = record["state"]
    messages = state["messages"]
    if len(messages) < 2:
        return False
    user, assistant = messages[-2:]
    return (user.get("role") == "user" and assistant.get("role") == "assistant"
            and bool(user.get("content")) and bool(assistant.get("content"))
            and state.get("parentMessageId") == assistant.get("id"))


def summarize(parsed, kind):
    result = {"signature_hits": parsed["stats"].get("signature_hits", 0),
              "complete_occurrences": parsed["stats"].get("complete_record_occurrences", 0),
              "unique_complete_records": parsed["unique_complete_records"],
              "user_space_rows": parsed["user_space_rows"],
              "skipped_kernel_rows": parsed["skipped_kernel_rows"],
              "framing_stats": parsed["stats"]}
    if kind == "state":
        result["two_message_turn_shapes"] = sum(state_turn_shape(record)
                                                 for record in parsed["records"])
    else:
        result["decoded_event_count"] = sum(len(record["decoded_events"])
                                            for record in parsed["records"])
    return result


def verify_samples(vmm, process, rows, flags, count=32):
    user = [row for row in rows if int(row["Virtual"]) < USER_LIMIT]
    if not user:
        raise ValueError("No resident user mappings")
    indexes = sorted({round(index * (len(user) - 1) / max(1, count - 1))
                      for index in range(min(count, len(user)))})
    matched = translation_unavailable = physical_unavailable = 0
    for index in indexes:
        row = user[index]
        virtual, expected = int(row["Virtual"]), int(row["Physical"])
        try:
            physical = process.memory.virt2phys(virtual)
        except RuntimeError:
            translation_unavailable += 1
            try:
                if len(vmm.memory.read(expected, 16, flags)) != 16:
                    physical_unavailable += 1
            except RuntimeError:
                physical_unavailable += 1
            continue
        if physical != expected:
            raise ValueError(f"MemProcFS/Volatility translation disagrees at sample {index}")
        try:
            by_process = process.memory.read(virtual, 16, flags)
            by_physical = vmm.memory.read(physical, 16, flags)
        except RuntimeError:
            physical_unavailable += 1
            continue
        if by_process != by_physical or len(by_process) != 16:
            raise ValueError(f"MemProcFS virtual/physical bytes disagree at sample {index}")
        matched += 1
    return {"requested": len(indexes), "matched": matched,
            "virtual_translation_unavailable": translation_unavailable,
            "physical_sample_unavailable": physical_unavailable}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", type=Path, required=True)
    cli.add_argument("--vmem", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, required=True)
    cli.add_argument("--pid", type=int, required=True)
    cli.add_argument("--process-name", required=True,
                     choices=("ChatGPT.exe", "chrome.exe", "msedge.exe"))
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
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
            raise ValueError("PID no longer identifies the selected process name")
        flags = memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING
        samples = verify_samples(vmm, process, rows, flags)
        reader = PhysicalReader(vmm.memory, flags)
        stream = scan_stream(reader, rows, image_size)
        state = scan_state(reader, rows, image_size)
        result = {
            "method": "Volatility memmap + MemProcFS VMware-aware physical reads + bounded JSON format parsers",
            "ground_truth_supplied": False,
            "scored_conversation_claim": False,
            "raw_record_content_stored": False,
            "process_name": args.process_name,
            "pid": args.pid,
            "vmem_file_bytes": args.vmem.stat().st_size,
            "highest_guest_physical_end": image_size,
            "memprocfs_virtual_physical_samples": samples,
            "memprocfs_physical_read_failures_during_scan": reader.failed_reads,
            "stream_item": summarize(stream, "stream"),
            "state_object": summarize(state, "state"),
            "parser_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                              for name in ("bounded_json.py", "chrome_state_records.py",
                                           "scan_vmware_snapshot.py")},
        }
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"process_name": args.process_name, "pid": args.pid,
                          "stream_records": result["stream_item"]["unique_complete_records"],
                          "state_records": result["state_object"]["unique_complete_records"],
                          "state_turn_shapes": result["state_object"]["two_message_turn_shapes"],
                          "translation_samples": samples,
                          "physical_read_failures": reader.failed_reads}))
    finally:
        del vmm
        if dll:
            dll.close()


if __name__ == "__main__":
    main()
