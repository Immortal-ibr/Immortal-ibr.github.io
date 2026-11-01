"""Score a no-submission image from the frozen runner's public manifest."""

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--trial", required=True, type=Path)
args = parser.parse_args()
trial = args.trial.resolve()
truth = json.loads((trial / "ground_truth.json").read_text(encoding="utf-8"))
run = json.loads((trial / "v2_run_manifest.json").read_text(encoding="utf-8"))
if truth["expected_new_turns"] != 0:
    raise RuntimeError("This scorer requires a zero-turn control")
processes = run["processes"]
score = {
    "trial_id": trial.name,
    "condition": truth["condition"],
    "expected_new_turns": 0,
    "ground_truth_supplied_to_frozen_method": run["ground_truth_supplied"],
    "active_renderer_processes_scanned": len(processes),
    "stream_item_signature_hits": sum(row.get("signature_hits", 0) for row in processes),
    "complete_bounded_records": sum(row.get("unique_complete_records", 0) for row in processes),
    "candidate_turns": sum(row.get("candidate_turns", 0) for row in processes),
    "false_joins_observed_in_this_control": sum(row.get("candidate_turns", 0) for row in processes),
    "clean_vm_reset": truth["clean_vm_reset"],
    "limitation": "A signed-in account and previously used VM cannot serve as an independent no-visit control or a general false-positive-rate estimate.",
}
(trial / "control_score.json").write_text(json.dumps(score, indent=2), encoding="utf-8")
print(json.dumps(score, indent=2))
