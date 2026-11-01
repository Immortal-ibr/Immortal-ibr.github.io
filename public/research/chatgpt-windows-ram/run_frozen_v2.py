"""Apply frozen v2 method to every active ChatGPT renderer in a RAM image.

The runner selects processes from image-derived pslist/cmdline, verifies both
method hashes, and passes no known turn values to parser or joiner. Per-process
parsed records and candidates remain private.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VOL = Path(r"C:\Users\Win10\Desktop\volatility3-2.8.0\vol.py")
FREEZE = json.loads((ROOT / "FROZEN_METHOD_V2.json").read_text(encoding="utf-8"))
PARSE = ROOT / "trial_iab_visible_002" / "parse_stream_items.py"
JOIN = ROOT / "method_v2" / "reconstruct_turns.py"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--trial", required=True, type=Path)
    args = cli.parse_args()
    trial = args.trial.resolve()
    private = trial / "private"
    image = private / "memory.raw"
    for relative, expected in FREEZE["method_files"].items():
        actual = sha256(ROOT / relative)
        if actual != expected:
            raise RuntimeError(f"Frozen v2 hash mismatch: {relative}")

    cmdlines = json.loads((private / "cmdline.json").read_text(encoding="utf-8-sig"))
    processes = json.loads((private / "pslist.json").read_text(encoding="utf-8-sig"))
    active_pids = {int(p["PID"]) for p in processes if p.get("ExitTime") is None}
    pids = sorted({int(row["PID"]) for row in cmdlines if row.get("Process") == "ChatGPT.exe" and "--type=renderer" in str(row.get("Args")) and int(row["PID"]) in active_pids})
    print(f"Selected {len(pids)} active renderer PIDs: {pids}", flush=True)

    manifest = {
        "trial_id": trial.name,
        "start_utc": now_utc(),
        "selection": "all active ChatGPT.exe processes with --type=renderer in image-derived pslist/cmdline",
        "ground_truth_supplied": False,
        "frozen_method_sha256": FREEZE["method_files"],
        "image_sha256": json.loads((trial / "acquisition.json").read_text(encoding="utf-8-sig"))["image_sha256"],
        "processes": [],
    }

    for pid in pids:
        print(f"PID {pid}: Volatility user/process map", flush=True)
        mapfile = private / f"renderer_{pid}_memmap.json"
        with mapfile.open("w", encoding="utf-8") as handle:
            result = subprocess.run([sys.executable, str(VOL), "-q", "--offline", "-r", "json", "-f", str(image), "windows.memmap", "--pid", str(pid)], stdout=handle, stderr=subprocess.PIPE, text=True)
        if result.returncode:
            manifest["processes"].append({"pid": pid, "memmap_error": result.stderr[-1000:]})
            print(f"PID {pid}: memmap failed", flush=True)
            continue
        parsedfile = private / f"renderer_{pid}_parsed_private.json"
        reconstructedfile = private / f"renderer_{pid}_v2_reconstructed_private.json"
        print(f"PID {pid}: frozen v2 parser and joiner", flush=True)
        subprocess.run([sys.executable, str(PARSE), "--image", str(image), "--memmap", str(mapfile), "--output", str(parsedfile)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, str(JOIN), "--parsed", str(parsedfile), "--output", str(reconstructedfile)], check=True, stdout=subprocess.DEVNULL)
        parsed = json.loads(parsedfile.read_text(encoding="utf-8"))
        reconstructed = json.loads(reconstructedfile.read_text(encoding="utf-8"))
        row = {
            "pid": pid,
            "memmap_rows": parsed["user_space_rows"],
            "signature_hits": parsed["signature_hits"],
            "unique_complete_records": parsed["unique_complete_records"],
            "candidate_turns": len(reconstructed["candidate_turns"]),
        }
        manifest["processes"].append(row)
        (trial / "v2_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"PID {pid}: {row['unique_complete_records']} records; {row['candidate_turns']} candidate turns", flush=True)

    manifest["end_utc"] = now_utc()
    (trial / "v2_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Frozen v2 run complete", flush=True)


if __name__ == "__main__":
    main()
