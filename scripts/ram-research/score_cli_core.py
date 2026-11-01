"""Host-only scoring after sealing the recovered core-event output.

Observed RPC ground truth is never supplied to the RAM parser. Scoring reports
text/identity equality separately from unsupported assistant-ID attribution.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_frozen(recovered, manifest, turn_start_observed):
    expected = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    if recovered.get("executed_method_sha256") != expected:
        raise ValueError("Recovery did not record the frozen method's exact source hashes")
    if recovered["record_byte_cap"] != manifest["record_cap_bytes"]:
        raise ValueError("Recovery cap differs from the frozen method")
    if datetime.fromisoformat(manifest["frozen_utc"]) >= datetime.fromisoformat(turn_start_observed):
        raise ValueError("Method was not frozen before this turn was submitted")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--recovered", type=Path, required=True)
    cli.add_argument("--events", type=Path, required=True)
    cli.add_argument("--acquisition", type=Path, required=True)
    cli.add_argument("--processes", type=Path, required=True)
    cli.add_argument("--native-pid", type=int, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--role", choices=("development", "held-out"), default="development")
    cli.add_argument("--frozen-manifest", type=Path)
    args = cli.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to replace a score")
    # Seal first. No known value can affect the already completed recovery.
    recovered_bytes = args.recovered.read_bytes()
    recovered_hash = hashlib.sha256(recovered_bytes).hexdigest()
    sealed_utc = datetime.now(timezone.utc).isoformat()
    recovered = json.loads(recovered_bytes)
    observed = [json.loads(line) for line in args.events.read_text(encoding="utf-8").splitlines()]
    starts = [event["message"]["params"] for event in observed if event["direction"] == "host_to_native_cli"
              and event["message"].get("method") == "turn/start"]
    if len(starts) != 1:
        raise SystemExit("This score requires exactly one intended turn")
    start = starts[0]
    if args.role == "held-out":
        if not args.frozen_manifest:
            raise SystemExit("A held-out score requires a pre-submission frozen method manifest")
        submission = next(event["observed_utc"] for event in observed
                          if event["direction"] == "host_to_native_cli" and event["message"].get("method") == "turn/start")
        validate_frozen(recovered, read(args.frozen_manifest), submission)
    done = [event for event in observed if event["direction"] == "native_cli_to_host"
            and event["message"].get("method") == "turn/completed"
            and event["message"].get("params", {}).get("threadId") == start["threadId"]]
    if len(done) != 1 or done[0]["message"]["params"]["turn"].get("status") != "completed":
        raise SystemExit("No unique observed successfully completed turn")
    turn = done[0]["message"]["params"]["turn"]
    items = [event["message"]["params"]["item"] for event in observed
             if event["direction"] == "native_cli_to_host" and event["message"].get("method") == "item/completed"
             and event["message"]["params"].get("threadId") == start["threadId"]
             and event["message"]["params"].get("turnId") == turn["id"]]
    users = [item for item in items if item.get("type") == "userMessage"]
    agents = [item for item in items if item.get("type") == "agentMessage" and item.get("phase") == "final_answer"]
    if len(users) != 1 or len(agents) != 1:
        raise SystemExit("Scoring requires one observed user item and final agent item")
    truth = {"thread_id": start["threadId"], "turn_id": turn["id"],
             "user_message_id": users[0]["id"], "prompt": "".join(part["text"] for part in start["input"]),
             "response": agents[0]["text"], "agent_message_id": agents[0]["id"]}
    scores = []
    for candidate in recovered["join"]["candidates"]:
        checks = {field: candidate.get(field) == truth[field] for field in
                  ("thread_id", "turn_id", "user_message_id", "prompt", "response")}
        scores.append({"exact_strong_field_matches": checks, "all_five_match": all(checks.values()),
                       "agent_id_independently_bound": candidate["agent_id_independently_bound"],
                       "observed_agent_id_among_unbound_text_matches": any(
                           item["agent_message_id"] == truth["agent_message_id"]
                           for item in candidate["text_matching_unbound_agent_objects"]),
                       "task_start_matches_api": candidate["task_complete_times_raw"]["started_at"] == turn.get("startedAt"),
                       "task_end_matches_api": candidate["task_complete_times_raw"]["completed_at"] == turn.get("completedAt")})
    acquisition = read(args.acquisition)
    processes = read(args.processes)
    backend = [item for item in processes if item["ProcessId"] == args.native_pid and item["Name"] == "codex.exe"]
    response_observed = datetime.fromisoformat(done[0]["observed_utc"])
    capture_start = datetime.fromisoformat(acquisition["started_utc"])
    result = {"sealed_before_scoring_utc": sealed_utc, "recovered_output_sha256": recovered_hash,
              "raw_sha256": acquisition["raw_sha256"].lower(), "trial_id": acquisition["trial_id"],
              "cohort": "instrumented native app-server stdio; " + args.role,
              "native_pid": args.native_pid, "backend_present_before_acquisition": len(backend) == 1,
              "response_complete_observed_utc": done[0]["observed_utc"],
              "acquisition_started_utc": acquisition["started_utc"],
              "acquisition_ended_utc": acquisition["ended_utc"],
              "response_to_acquisition_seconds": (capture_start - response_observed).total_seconds(),
              "candidate_count": len(scores), "candidate_scores": scores,
              "account_identity_claimed": False,
              "scope": "five linked fields; standalone assistant ID is not independently thread/turn bound"}
    if args.frozen_manifest:
        result["frozen_method_manifest_sha256"] = hashlib.sha256(args.frozen_manifest.read_bytes()).hexdigest()
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
