"""Post-hoc known-string baseline across active renderer user-space mappings.

The exact turn values are supplied from ground truth, so this is not the frozen
reconstruction method. Counts are per mapping and cannot prove exclusive page
ownership. No byte neighborhoods or unrelated content are saved.
"""

import json
from pathlib import Path


RESULTS = Path(__file__).resolve().parent
TRIAL = RESULTS.parent / "trial_iab_away_003"
PRIVATE = TRIAL / "private"
truth = json.loads((RESULTS / "ground_truth.json").read_text(encoding="utf-8"))
run = json.loads((RESULTS / "frozen_run_manifest.json").read_text(encoding="utf-8"))
image = PRIVATE / "memory.raw"
size = image.stat().st_size
fields = {
    "prompt": truth["prompt"],
    "response": truth["actual_response"],
    "conversation_id": truth["conversation_id_from_url"],
    "user_message_id": truth["user_message_id_from_DOM"],
    "assistant_message_id": truth["assistant_message_id_from_DOM"],
}
needles = {name: value.encode("utf-8") for name, value in fields.items()}
results = []
with image.open("rb", buffering=0) as source:
    for process in run["processes"]:
        pid = process["pid"]
        mapfile = PRIVATE / f"renderer_{pid}_memmap.json"
        if not mapfile.exists():
            continue
        rows = json.loads(mapfile.read_text(encoding="utf-8-sig"))
        counts = {name: 0 for name in needles}
        pages = {name: set() for name in needles}
        scanned_rows = 0
        for row in rows:
            physical, virtual, amount = (int(row[name]) for name in ("Physical", "Virtual", "Size"))
            if virtual >= (1 << 47) or amount <= 0 or physical < 0 or physical + amount > size:
                continue
            scanned_rows += 1
            source.seek(physical)
            data = source.read(amount)
            for name, needle in needles.items():
                cursor = 0
                while True:
                    index = data.find(needle, cursor)
                    if index < 0:
                        break
                    counts[name] += 1
                    pages[name].add(physical + index // 4096 * 4096)
                    cursor = index + 1
        results.append({
            "pid": pid,
            "user_space_rows_scanned": scanned_rows,
            "known_value_hit_counts": counts,
            "physical_4k_pages_with_hit": {name: len(page_set) for name, page_set in pages.items()},
        })
        print(f"PID {pid}: {counts}", flush=True)

output = {
    "trial_id": "trial_iab_away_003",
    "method": "ground-truth-assisted per-row exact ASCII scan of active renderer user-space mappings",
    "ground_truth_supplied": True,
    "limitations": "Not blind reconstruction; strings split across rows can be missed; a mapped page is not exclusive process ownership; no bounded turn or IDs are joined.",
    "processes": results,
}
(RESULTS / "known_marker_mapped_renderers.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
