"""Post-hoc comparison of frozen-method output with the visible-trial ground truth."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


DIR = Path(__file__).resolve().parent
truth = json.loads((DIR / "ground_truth.json").read_text(encoding="utf-8"))
acquisition = json.loads((DIR / "acquisition.json").read_text(encoding="utf-8-sig"))
reconstruction = json.loads((DIR / "reconstructed_turns_private.json").read_text(encoding="utf-8"))


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def utc_from_unix(value):
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z") if isinstance(value, (int, float)) else None


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


matches = []
for candidate in reconstruction["candidate_turns"]:
    fields = {
        "conversation_id": candidate["conversation_id"] == truth["conversation_id_from_url"],
        "prompt": candidate["prompt"] == truth["prompt"],
        "response": candidate["response"] == truth["actual_response"],
        "user_message_id": candidate["user_message_id"] == truth["user_message_id_from_DOM"],
        "assistant_message_id": candidate["assistant_message_id"] == truth["assistant_message_id_from_DOM"],
    }
    user_time = utc_from_unix(candidate.get("user_create_time_unix"))
    assistant_time = utc_from_unix(candidate.get("assistant_create_time_unix"))
    user_time_in_submit_window = bool(user_time and parse_utc(truth["submission_utc_interval"][0]) <= parse_utc(user_time) <= parse_utc(truth["submission_utc_interval"][1]))
    assistant_time_plausible = bool(assistant_time and parse_utc(truth["submission_utc_interval"][0]) <= parse_utc(assistant_time) <= parse_utc(truth["response_complete_observed_utc"]))
    matches.append({
        "turn_id_derived_from_ram": candidate["turn_id"],
        "field_exact_match": fields,
        "user_create_time_utc_from_ram": user_time,
        "assistant_create_time_utc_from_ram": assistant_time,
        "user_time_in_submit_window": user_time_in_submit_window,
        "assistant_start_time_before_completed_ui": assistant_time_plausible,
        "support": candidate["support"],
        "complete_join_for_this_visible_trial": all(fields.values()) and user_time_in_submit_window and assistant_time_plausible and not candidate["ambiguous_user_ancestors"],
    })

result = {
    "trial_id": truth["trial_id"],
    "status": "pilot development; not independent held-out validation",
    "capture_image_sha256": acquisition["image_sha256"],
    "method_hashes_sha256": {
        "parse_stream_items.py": file_sha256(DIR / "parse_stream_items.py"),
        "reconstruct_turns.py": file_sha256(DIR / "reconstruct_turns.py"),
    },
    "candidate_turn_count": len(reconstruction["candidate_turns"]),
    "matches": matches,
    "limitation": "The parser was developed on this image. Only the visible state was tested; there was no VM reset or independent control. Assistant create_time is a message-start time, not the completed-response time."
}
(DIR / "result_redacted.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({"candidate_turn_count": result["candidate_turn_count"], "complete_matches": sum(m["complete_join_for_this_visible_trial"] for m in matches)}, indent=2))
