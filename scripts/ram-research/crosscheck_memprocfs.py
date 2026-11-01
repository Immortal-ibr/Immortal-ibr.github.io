"""Independent MemProcFS inventory and deterministic resident-page cross-check.

Command lines are private. Public stdout contains counts, not recovered contents.
No prompt, answer, conversation ID or message ID is accepted as an argument.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

USER_LIMIT = 1 << 47
TARGET_NAMES = {"chrome.exe", "msedge.exe", "chatgpt.exe", "codex.exe"}


def integer(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--sdk-root", required=True, type=Path)
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--pid", required=True, type=int)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--samples", type=int, default=32)
    args = cli.parse_args()
    if args.samples < 1:
        raise SystemExit("Sample count must be positive")
    if args.output.exists():
        raise SystemExit("Refusing to overwrite a private cross-check result")
    sdk = args.sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll_scope = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs

    vmm = memprocfs.Vmm(["-device", str(args.image.resolve(strict=True))])
    inventory = []
    for process in vmm.process_list():
        if process.name.lower() not in TARGET_NAMES:
            continue
        value = {"pid": process.pid, "ppid": process.ppid, "name": process.name, "state": process.state}
        try:
            value["cmdline_private"] = process.cmdline
            match = re.search(r"--type=([\w-]+)", value["cmdline_private"])
            value["type"] = match.group(1) if match else ("main" if value["cmdline_private"] else "unknown")
        except Exception as error:
            value["cmdline_error"] = type(error).__name__
            value["type"] = "unknown"
        inventory.append(value)
    rows = sorted((row for row in json.loads(args.memmap.read_text(encoding="utf-8-sig"))
                   if integer(row["Virtual"]) < USER_LIMIT), key=lambda row: integer(row["Virtual"]))
    indexes = sorted({round(i * (len(rows) - 1) / max(1, args.samples - 1))
                      for i in range(min(args.samples, len(rows)))})
    process = vmm.process(args.pid)
    samples = []
    with args.image.open("rb") as raw:
        for index in indexes:
            row = rows[index]
            virtual, physical, size = (integer(row[key]) for key in ("Virtual", "Physical", "Size"))
            length = min(size, 256)
            raw.seek(physical)
            expected = raw.read(length)
            sample = {"virtual": virtual, "volatility_physical": physical, "bytes_compared": length}
            try:
                observed_physical = process.memory.virt2phys(virtual)
                observed = process.memory.read(virtual, length, memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING)
                sample.update({
                    "memprocfs_physical": observed_physical,
                    "physical_match": observed_physical == physical,
                    "bytes_match": observed == expected,
                    "expected_sha256": hashlib.sha256(expected).hexdigest(),
                    "observed_sha256": hashlib.sha256(observed).hexdigest(),
                })
            except Exception as error:
                sample["error"] = type(error).__name__
            samples.append(sample)
    result = {
        "method": "MemProcFS process inventory; deterministic samples from Volatility resident user mappings",
        "ground_truth_supplied": False,
        "pid_checked": args.pid,
        "mapped_rows": len(rows),
        "all_samples_match": bool(samples) and all(s.get("physical_match") and s.get("bytes_match") for s in samples),
        "process_inventory_private": inventory,
        "samples": samples,
    }
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=True)
    print(json.dumps({"target_processes": len(inventory), "samples_checked": len(samples),
                      "all_samples_match": result["all_samples_match"],
                      "unknown_cmdlines": sum(p["type"] == "unknown" for p in inventory)}, indent=2))
    del vmm
    if dll_scope is not None:
        dll_scope.close()


if __name__ == "__main__":
    main()
