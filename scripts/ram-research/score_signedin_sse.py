"""Score a sealed RAM-derived signed-in turn against later-read screen facts.

Only conversation URL ID, exact prompt and exact rendered answer were observed
independently. User/assistant message IDs are recovered and internally joined
but were not checked against live DOM IDs, so this is a 3-field visible score.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--recovered", type=Path, required=True)
    cli.add_argument("--ground-truth", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Ground-truth scoring detail stays outside repository")
    if output.exists():
        raise FileExistsError(output)
    recovered_bytes = args.recovered.read_bytes()
    recovered_sha256 = hashlib.sha256(recovered_bytes).hexdigest().upper()
    recovered = json.loads(recovered_bytes)
    if recovered.get("ground_truth_supplied") is not False:
        raise ValueError("Recovery output claims to have received ground truth")
    truth = json.loads(args.ground_truth.read_text(encoding="utf-8-sig"))
    scored = []
    for candidate in recovered["candidate_turns"]:
        fields = {field: candidate[field] == truth[field]
                  for field in ("conversation_id", "prompt", "response")}
        scored.append({"visible_field_match": fields,
                       "visible_score": sum(fields.values()),
                       "visible_score_denominator": 3,
                       "response_characters": len(candidate["response"]),
                       "user_and_assistant_ids_internally_linked": bool(
                           candidate["user_message_id"] and candidate["assistant_message_id"]
                           and candidate["user_message_id"] != candidate["assistant_message_id"]),
                       "user_and_assistant_ids_independently_observed": False})
    result = {"scored_utc": datetime.now(timezone.utc).isoformat(),
              "recovered_output_sha256_before_ground_truth_read": recovered_sha256,
              "independent_ground_truth_source": "private saved guest screen and URL observation",
              "scored_candidates": scored}
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
