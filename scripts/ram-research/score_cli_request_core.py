"""Score a request/core join against independent host observations.

The recovered result is sealed by hash before host events are read. The trial
role is supplied by the caller; no prompt, response, account details, or
identifier values enter the output.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("recovered", "events", "acquisition", "output"):
        cli.add_argument("--" + name, required=True, type=Path)
    cli.add_argument("--verification", type=Path,
                     help="Verified host decompression record for direct-gzip captures")
    cli.add_argument("--experimental-role", default="post-hoc development on an existing image")
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    raw = args.recovered.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    sealed = datetime.now(timezone.utc).isoformat()
    result = json.loads(raw)
    events = [json.loads(line) for line in args.events.read_text(encoding="utf-8").splitlines()]
    starts = [event for event in events
              if event["direction"] == "host_to_native_cli"
              and event["message"].get("method") == "turn/start"]
    if len(starts) != 1:
        raise ValueError("Expected exactly one independently observed turn/start")
    start = starts[0]["message"]["params"]
    done = [event for event in events
            if event["direction"] == "native_cli_to_host"
            and event["message"].get("method") == "turn/completed"
            and event["message"]["params"].get("threadId") == start["threadId"]]
    if len(done) != 1 or done[0]["message"]["params"]["turn"].get("status") != "completed":
        raise ValueError("Expected one successfully completed observed turn")
    turn = done[0]["message"]["params"]["turn"]
    agents = [event["message"]["params"]["item"] for event in events
              if event["direction"] == "native_cli_to_host"
              and event["message"].get("method") == "item/completed"
              and event["message"]["params"].get("threadId") == start["threadId"]
              and event["message"]["params"].get("turnId") == turn["id"]
              and event["message"]["params"]["item"].get("type") == "agentMessage"
              and event["message"]["params"]["item"].get("phase") == "final_answer"]
    if len(agents) != 1:
        raise ValueError("Expected one independently observed final answer")
    truth = {"thread_id": start["threadId"], "turn_id": turn["id"],
             "prompt": "".join(part["text"] for part in start["input"]),
             "response": agents[0]["text"]}
    scores = [{"exact_field_matches": {key: candidate.get(key) == value
                                        for key, value in truth.items()},
               "model_input_id_independently_scored": False,
               "assistant_message_id_independently_bound": candidate["assistant_message_id_independently_bound"]}
              for candidate in result["join"]["candidates"]]
    acquisition = json.loads(args.acquisition.read_text(encoding="utf-8-sig"))
    raw_sha256 = acquisition.get("raw_sha256")
    if raw_sha256 is None:
        if args.verification is None:
            raise ValueError("Direct-gzip capture requires --verification")
        verification = json.loads(args.verification.read_text(encoding="utf-8-sig"))
        if (verification["trial_id"] != acquisition["trial_id"]
                or verification["archive_sha256"].lower() != acquisition["archive_sha256"].lower()
                or not verification["copy_verified_against_guest_sha256"]
                or not verification["gzip_stream_read_to_eof"]):
            raise ValueError("Direct-gzip verification does not match acquisition")
        raw_sha256 = verification["raw_sha256"]
    summary = {"scored_utc": sealed, "recovered_output_sha256": digest,
               "raw_sha256": raw_sha256.lower(),
               "trial_id": acquisition["trial_id"],
               "experimental_role": args.experimental_role,
               "candidate_count": len(scores), "candidate_scores": scores,
               "account_identity_claimed": False}
    args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
