"""Post-capture field-level scoring for a single synthetic v2 RAM trial.

Ground truth is read only here, after the frozen parser and joiner finish. This
script is not part of process selection or reconstruction.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_from_unix(value):
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--trial", required=True, type=Path)
    args = cli.parse_args()
    trial = args.trial.resolve()
    private = trial / "private"
    truth = json.loads((trial / "ground_truth.json").read_text(encoding="utf-8"))
    run = json.loads((trial / "v2_run_manifest.json").read_text(encoding="utf-8"))
    fields = {
        "conversation_id": "conversation_id_from_url",
        "prompt": "prompt",
        "response": "actual_response",
        "user_message_id": "user_message_id_from_DOM",
        "assistant_message_id": "assistant_message_id_from_DOM",
    }

    candidates = {}
    for process in run["processes"]:
        pid = process["pid"]
        path = private / f"renderer_{pid}_v2_reconstructed_private.json"
        if not path.exists():
            continue
        reconstructed = json.loads(path.read_text(encoding="utf-8"))
        for candidate in reconstructed["candidate_turns"]:
            key = tuple(candidate.get(field) for field in (*fields, "turn_id"))
            item = candidates.setdefault(key, {"candidate": candidate, "pids": []})
            item["pids"].append(pid)

    scored = []
    for item in candidates.values():
        candidate = item["candidate"]
        exact = {field: candidate.get(field) == truth.get(truth_field) for field, truth_field in fields.items()}
        user_time = utc_from_unix(candidate.get("user_create_time_unix"))
        assistant_time = utc_from_unix(candidate.get("assistant_create_time_unix"))
        scored.append({
            "pids": item["pids"],
            "turn_id": candidate.get("turn_id"),
            "field_exact_match": exact,
            "complete_exact_match": all(exact.values()),
            "user_create_time_utc_from_ram": user_time,
            "assistant_create_time_utc_from_ram": assistant_time,
            "user_time_in_submit_window": bool(user_time and truth["submit_start_utc"] <= user_time <= truth["submit_end_utc"]),
            "assistant_start_before_completion_observed": bool(assistant_time and assistant_time <= truth["completion_observed_utc"]),
            "ambiguous_user_ancestors": candidate.get("ambiguous_user_ancestors"),
            "support": candidate.get("support"),
        })

    result = {
        "trial_id": truth["trial_id"],
        "condition": truth["condition"],
        "validation_status": "fresh image with frozen v2 method, but same VM without reset and same investigator environment",
        "image_sha256": run["image_sha256"],
        "frozen_v2_method_sha256": run["frozen_method_sha256"],
        "active_renderer_processes_scanned": len(run["processes"]),
        "active_renderer_complete_records": sum(row.get("unique_complete_records", 0) for row in run["processes"]),
        "unique_candidate_turns": len(candidates),
        "candidate_scores": scored,
        "complete_exact_candidate_count": sum(row["complete_exact_match"] for row in scored),
    }
    (trial / "result_v2_redacted.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"candidates": len(candidates), "complete_exact": result["complete_exact_candidate_count"]}, indent=2))


if __name__ == "__main__":
    main()
