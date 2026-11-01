"""Apply the frozen pilot method to every active ChatGPT.exe renderer in RAM.

Process selection uses Volatility pslist/cmdline from the captured image. No
ground-truth prompt, response, IDs, or offsets are loaded by this runner or its
two frozen child scripts. Private per-process outputs stay in ./private.
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"C:\Users\Win10\Desktop\cheater_ram_research_2026-09-16")
TRIAL = Path(__file__).resolve().parent
PRIVATE = TRIAL / "private"
IMAGE = PRIVATE / "memory.raw"
VOL = Path(r"C:\Users\Win10\Desktop\volatility3-2.8.0\vol.py")
FREEZE = json.loads((ROOT / "FROZEN_METHOD.json").read_text(encoding="utf-8"))
PARSE = ROOT / "trial_iab_visible_002" / "parse_stream_items.py"
JOIN = ROOT / "trial_iab_visible_002" / "reconstruct_turns.py"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


for relative, expected in FREEZE["method_files"].items():
    actual = sha256(ROOT / relative)
    if actual != expected:
        raise RuntimeError(f"Frozen method hash mismatch: {relative}")

cmdlines = json.loads((PRIVATE / "cmdline.json").read_text(encoding="utf-8-sig"))
processes = json.loads((PRIVATE / "pslist.json").read_text(encoding="utf-8-sig"))
active_pids = {int(p["PID"]) for p in processes if p.get("ExitTime") is None}
pids = sorted({int(row["PID"]) for row in cmdlines if row.get("Process") == "ChatGPT.exe" and "--type=renderer" in str(row.get("Args")) and int(row["PID"]) in active_pids})
print(f"Selected {len(pids)} active renderer PIDs: {pids}", flush=True)

manifest = {
    "trial_id": "trial_iab_away_003",
    "start_utc": now_utc(),
    "selection": "all active ChatGPT.exe processes with --type=renderer in image-derived pslist/cmdline",
    "ground_truth_supplied": False,
    "frozen_method_sha256": FREEZE["method_files"],
    "image_sha256": json.loads((TRIAL / "acquisition.json").read_text(encoding="utf-8-sig"))["image_sha256"],
    "processes": [],
}

for pid in pids:
    print(f"PID {pid}: Volatility user/process map", flush=True)
    mapfile = PRIVATE / f"renderer_{pid}_memmap.json"
    with mapfile.open("w", encoding="utf-8") as handle:
        result = subprocess.run([sys.executable, str(VOL), "-q", "--offline", "-r", "json", "-f", str(IMAGE), "windows.memmap", "--pid", str(pid)], stdout=handle, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        manifest["processes"].append({"pid": pid, "memmap_error": result.stderr[-1000:]})
        print(f"PID {pid}: memmap failed", flush=True)
        continue
    parsedfile = PRIVATE / f"renderer_{pid}_parsed_private.json"
    reconstructedfile = PRIVATE / f"renderer_{pid}_reconstructed_private.json"
    print(f"PID {pid}: frozen parser and joiner", flush=True)
    subprocess.run([sys.executable, str(PARSE), "--image", str(IMAGE), "--memmap", str(mapfile), "--output", str(parsedfile)], check=True, stdout=subprocess.DEVNULL)
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
    (TRIAL / "frozen_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"PID {pid}: {row['unique_complete_records']} records; {row['candidate_turns']} candidate turns", flush=True)

manifest["end_utc"] = now_utc()
(TRIAL / "frozen_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("Frozen run complete", flush=True)
