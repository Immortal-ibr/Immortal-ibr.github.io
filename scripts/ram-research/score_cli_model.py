"""Seal model-input recovery, then score C/T/P/R/A against host observations.

Model input ID M is recovered from RAM but not equated with API user-item ID U.
Development on a failed core-v1 image is never relabeled held-out validation.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from score_cli_core import read, validate_frozen


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("recovered", "events", "acquisition", "processes", "output"):
        cli.add_argument("--" + name, required=True, type=Path)
    cli.add_argument("--native-pid", required=True, type=int)
    cli.add_argument("--role", choices=("development", "held-out"), default="development")
    cli.add_argument("--frozen-manifest", type=Path)
    args = cli.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to replace a score")
    raw = args.recovered.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    sealed = datetime.now(timezone.utc).isoformat()
    recovered = json.loads(raw)
    events = [json.loads(line) for line in args.events.read_text(encoding="utf-8").splitlines()]
    starts = [e for e in events if e["direction"] == "host_to_native_cli" and e["message"].get("method") == "turn/start"]
    if len(starts) != 1:
        raise SystemExit("Requires exactly one observed intended turn")
    start = starts[0]["message"]["params"]
    if args.role == "held-out":
        if not args.frozen_manifest:
            raise SystemExit("A held-out score requires a pre-submission method freeze")
        validate_frozen(recovered, read(args.frozen_manifest), starts[0]["observed_utc"])
    done = [e for e in events if e["direction"] == "native_cli_to_host" and e["message"].get("method") == "turn/completed"
            and e["message"]["params"].get("threadId") == start["threadId"]]
    if len(done) != 1 or done[0]["message"]["params"]["turn"].get("status") != "completed":
        raise SystemExit("No unique observed successfully completed turn")
    turn = done[0]["message"]["params"]["turn"]
    items = [e["message"]["params"]["item"] for e in events if e["direction"] == "native_cli_to_host"
             and e["message"].get("method") == "item/completed"
             and e["message"]["params"].get("threadId") == start["threadId"]
             and e["message"]["params"].get("turnId") == turn["id"]]
    users = [item for item in items if item.get("type") == "userMessage"]
    agents = [item for item in items if item.get("type") == "agentMessage" and item.get("phase") == "final_answer"]
    if len(users) != 1 or len(agents) != 1:
        raise SystemExit("Unexpected observed items")
    truth = {"thread_id": start["threadId"], "turn_id": turn["id"],
             "prompt": "".join(part["text"] for part in start["input"]), "response": agents[0]["text"],
             "agent_message_id": agents[0]["id"]}
    scores = []
    for candidate in recovered["join"]["candidates"]:
        checks = {key: candidate.get(key) == value for key, value in truth.items()}
        scores.append({"exact_field_matches": checks, "all_five_match": all(checks.values()),
                       "agent_id_independently_bound": candidate["agent_id_independently_bound"],
                       "api_user_item_id_recovered": candidate["api_user_item_id_recovered"],
                       "model_input_id_equals_observed_api_user_item_id": candidate["model_input_message_id"] == users[0]["id"],
                       "model_input_id_independently_ground_truth_scored": False})
    acquisition = read(args.acquisition)
    backend = [p for p in read(args.processes) if p["ProcessId"] == args.native_pid and p["Name"] == "codex.exe"]
    result = {"sealed_before_scoring_utc": sealed, "recovered_output_sha256": digest,
              "raw_sha256": acquisition["raw_sha256"].lower(), "trial_id": acquisition["trial_id"],
              "cohort": "instrumented native app-server stdio; " + args.role,
              "method_scope": "tagged model input + terminal RPC, NOT core-v1's C/T/U/P/R test",
              "native_pid": args.native_pid, "backend_present_before_acquisition": len(backend) == 1,
              "response_complete_observed_utc": done[0]["observed_utc"],
              "acquisition_started_utc": acquisition["started_utc"], "acquisition_ended_utc": acquisition["ended_utc"],
              "response_to_acquisition_seconds": (datetime.fromisoformat(acquisition["started_utc"])
                  - datetime.fromisoformat(done[0]["observed_utc"])).total_seconds(),
              "candidate_count": len(scores), "candidate_scores": scores,
              "account_identity_claimed": False}
    if args.frozen_manifest:
        result["frozen_method_manifest_sha256"] = hashlib.sha256(args.frozen_manifest.read_bytes()).hexdigest()
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
