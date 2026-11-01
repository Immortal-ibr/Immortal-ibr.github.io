"""Recover shareable trial-2 files after its folder was manually removed.

Reads only FileChange content recorded in the local Codex session log. It does
not recover the RAM image or private extracts and does not execute log content.
"""

import hashlib
import json
from pathlib import Path


ROOT = Path(r"C:\Users\Win10\Desktop\cheater_ram_research_2026-09-16")
LOG = Path(r"C:\Users\Win10\.codex\sessions\2026\09\16\rollout-2026-09-16T19-44-34-01a0ab1b-18ab-7393-ad9d-872f261e0e3f.jsonl")
OUT = ROOT / "trial_iab_visible_002"
NAMES = {
    "acquire.ps1",
    "ground_truth.json",
    "parse_stream_items.py",
    "reconstruct_turns.py",
    "scan_mapped_pages.py",
    "score_pilot.py",
    "inspect_target_events.py",
}
latest = {}
for line in LOG.open(encoding="utf-8"):
    try:
        item = json.loads(line).get("payload", {}).get("item", {})
    except json.JSONDecodeError:
        continue
    if item.get("type") != "FileChange":
        continue
    for path_text, change in item.get("changes", {}).items():
        path = Path(path_text)
        if path.parent == OUT and path.name in NAMES and isinstance(change.get("content"), str):
            latest[path.name] = change["content"]

OUT.mkdir(exist_ok=True)
results = []
for name in sorted(NAMES):
    if name not in latest:
        results.append({"file": name, "recovered": False})
        continue
    data = latest[name].encode("utf-8")
    (OUT / name).write_bytes(data)
    results.append({"file": name, "recovered": True, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest().upper()})
print(json.dumps(results, indent=2))
