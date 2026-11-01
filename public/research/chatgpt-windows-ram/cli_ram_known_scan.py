"""Exploratory, ground-truth-assisted Codex CLI process-memory comparison.

This is separate from the frozen web reconstruction method. It counts exact
synthetic values in mapped user-space bytes of image-derived active CLI PIDs.
It does not reconstruct a conversation or establish exclusive page ownership.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--trial", type=Path, required=True)
    cli.add_argument("--vol", type=Path, required=True, help="Path to the local Volatility 3 vol.py")
    cli.add_argument("--process-tag", help="Substring in image-derived CLI command lines; defaults to trial folder name")
    args = cli.parse_args()
    vol = args.vol.resolve(strict=True)
    trial = args.trial.resolve()
    private = trial / "private"
    image = private / "memory.raw"
    truth = json.loads((trial / "ground_truth.json").read_text(encoding="utf-8-sig"))
    pslist = json.loads((private / "pslist.json").read_text(encoding="utf-8-sig"))
    cmdline = json.loads((private / "cmdline.json").read_text(encoding="utf-8-sig"))
    active = {int(p["PID"]) for p in pslist if p.get("ExitTime") is None}
    process_tag = (args.process_tag or trial.name).lower()
    pids = sorted({int(p["PID"]) for p in cmdline
                   if p.get("Process", "").lower() in {"node.exe", "codex.exe"}
                   and process_tag in str(p.get("Args", "")).lower()
                   and int(p["PID"]) in active})

    values = {"prompt": truth["prompt"], "response": truth["actual_response"],
              "marker": truth["marker"],
              "prompt_prefix_48": truth["prompt"][:48],
              "response_prefix_48": truth["actual_response"][:48]}
    needles = {f"{name}_{encoding}": value.encode("utf-8" if encoding == "utf8" else "utf-16le")
               for name, value in values.items() for encoding in ("utf8", "utf16le")}
    result = {
        "trial_id": truth["trial_id"],
        "start_utc": now_utc(),
        "method": "post-capture ground-truth-assisted exact-value count in image-derived active native codex.exe and node.exe launcher user-space mappings",
        "ground_truth_supplied": True,
        "selected_pids": pids,
        "process_tag": process_tag,
        "processes": [],
        "limitations": "An exact hit is content presence in a mapped page, not a linked conversation or proof of exclusive process ownership; split, compressed, or transformed values can be missed.",
    }
    size = image.stat().st_size
    with image.open("rb", buffering=0) as source:
        for pid in pids:
            mapfile = private / f"cli_{pid}_memmap.json"
            with mapfile.open("w", encoding="utf-8") as handle:
                run = subprocess.run([sys.executable, str(vol), "-q", "--offline", "-r", "json",
                                      "-f", str(image), "windows.memmap", "--pid", str(pid)],
                                     stdout=handle, stderr=subprocess.PIPE, text=True)
            if run.returncode:
                result["processes"].append({"pid": pid, "memmap_error": run.stderr[-1000:]})
                continue
            rows = json.loads(mapfile.read_text(encoding="utf-8-sig"))
            counts = dict.fromkeys(needles, 0)
            pages = {name: set() for name in needles}
            scanned_rows = 0
            for row in rows:
                physical, virtual, amount = (int(row[name]) for name in ("Physical", "Virtual", "Size"))
                if virtual >= (1 << 47) or physical < 0 or amount <= 0 or physical + amount > size:
                    continue
                scanned_rows += 1
                source.seek(physical)
                data = source.read(amount)
                for name, needle in needles.items():
                    cursor = 0
                    while (offset := data.find(needle, cursor)) >= 0:
                        counts[name] += 1
                        pages[name].add((physical + offset) // 4096)
                        cursor = offset + 1
            result["processes"].append({
                "pid": pid,
                "user_space_rows_scanned": scanned_rows,
                "known_value_hit_counts": counts,
                "physical_4k_pages_with_hit": {name: len(hits) for name, hits in pages.items()},
            })
            print(f"PID {pid}: {counts}", flush=True)
    result["end_utc"] = now_utc()
    (trial / "cli_ram_known_scan.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Selected {len(pids)} active Codex CLI PID(s)")


if __name__ == "__main__":
    main()
