"""Post-hoc, redacted scoring of the navigated-away frozen-method trial."""

import hashlib
import json
from pathlib import Path


ROOT = Path(r"C:\Users\Win10\Desktop\cheater_ram_research_2026-09-16")
TRIAL = Path(__file__).resolve().parent
PRIVATE = TRIAL / "private"
truth = json.loads((TRIAL / "ground_truth.json").read_text(encoding="utf-8"))
old_truth = json.loads((ROOT / "trial_iab_visible_002" / "ground_truth.json").read_text(encoding="utf-8"))
acquisition = json.loads((TRIAL / "acquisition.json").read_text(encoding="utf-8-sig"))
frozen = json.loads((TRIAL / "frozen_run_manifest.json").read_text(encoding="utf-8"))
raw = json.loads((PRIVATE / "raw_carved_stream_items_private.json").read_text(encoding="utf-8"))
known = json.loads((TRIAL / "known_marker_baseline.json").read_text(encoding="utf-8"))
contexts = json.loads((PRIVATE / "raw_signature_contexts_private.json").read_text(encoding="utf-8"))
psscan = json.loads((PRIVATE / "psscan.json").read_text(encoding="utf-8-sig"))

record_like = [row for row in contexts if row["label"] == "record_like"]
old_id = old_truth["conversation_id_from_url"]
current_id = truth["conversation_id_from_url"]
result = {
    "trial_id": truth["trial_id"],
    "condition": "completed response, then navigate away before full-RAM acquisition",
    "validation_status": "fresh image with unchanged frozen scripts, but same VM without reset; exploratory, not independent validation",
    "image_sha256": acquisition["image_sha256"],
    "capture_start_utc": acquisition["start_utc"],
    "capture_end_utc": acquisition["end_utc"],
    "frozen_method_sha256": frozen["frozen_method_sha256"],
    "active_renderer_processes_scanned": len(frozen["processes"]),
    "active_renderer_signature_hits": sum(p.get("signature_hits", 0) for p in frozen["processes"]),
    "active_renderer_complete_records": sum(p.get("unique_complete_records", 0) for p in frozen["processes"]),
    "active_renderer_candidate_turns": sum(p.get("candidate_turns", 0) for p in frozen["processes"]),
    "frozen_method_field_score": {
        "conversation_id": "absent",
        "prompt": "absent",
        "response": "absent",
        "user_message_id": "absent",
        "assistant_message_id": "absent",
        "timestamps": "absent",
        "joined_turn": "absent"
    },
    "former_renderer_pid_8336_in_psscan": any(row.get("PID") == 8336 for row in psscan),
    "exploratory_full_physical_scan": {
        "stream_item_syntax_hits": raw["signature_hits"],
        "complete_records": raw["unique_complete_records"],
        "record_like_fragments": len(record_like),
        "record_like_fragments_with_previous_visible_pilot_id": sum(old_id in row["context_ascii"] for row in record_like),
        "record_like_fragments_with_current_away_trial_id": sum(current_id in row["context_ascii"] for row in record_like),
        "code_or_log_like_fragments": sum(row["label"] == "code_or_log_like" for row in contexts),
        "unclassified_fragments": sum(row["label"] == "unclassified" for row in contexts)
    },
    "known_string_baseline_counts": known["counts"],
    "interpretation": "The frozen active-renderer method yielded no bounded turn after navigation. The exited earlier renderer was not found by psscan. A separate raw physical scan found incomplete syntax fragments, including residue from the prior visible pilot, but no complete attributable turn. The ground-truth-assisted string baseline found the away-trial prompt, answer, and IDs somewhere in RAM, without process provenance. This does not show erasure or make the sequential trial independent."
}
(TRIAL / "result_redacted.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({"frozen_candidates": result["active_renderer_candidate_turns"], "raw_complete_records": raw["unique_complete_records"], "prior_pilot_fragments": result["exploratory_full_physical_scan"]["record_like_fragments_with_previous_visible_pilot_id"]}, indent=2))
