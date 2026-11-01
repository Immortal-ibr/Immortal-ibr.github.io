"""Publish only reviewed synthetic model-input/terminal-RPC records after scoring.

This is a privacy filter, not a recovery step. Known text and IDs are used here
only to prevent unrelated RAM data from entering the public evidence bundle.
"""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

from export_cli_core_case import read, subset


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def observed_for_review(path):
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    starts = [e["message"]["params"] for e in events if e["direction"] == "host_to_native_cli"
              and e["message"].get("method") == "turn/start"]
    if len(starts) != 1:
        raise ValueError("Privacy review requires one intended turn")
    start = starts[0]
    endings = [e["message"]["params"]["turn"] for e in events if e["direction"] == "native_cli_to_host"
               and e["message"].get("method") == "turn/completed"
               and e["message"]["params"].get("threadId") == start["threadId"]]
    if len(endings) != 1 or endings[0]["status"] != "completed":
        raise ValueError("Privacy review requires one completed turn")
    ending = endings[0]
    agents = [e["message"]["params"]["item"] for e in events if e["direction"] == "native_cli_to_host"
              and e["message"].get("method") == "item/completed"
              and e["message"]["params"].get("threadId") == start["threadId"]
              and e["message"]["params"].get("turnId") == ending["id"]
              and e["message"]["params"]["item"].get("type") == "agentMessage"
              and e["message"]["params"]["item"].get("phase") == "final_answer"]
    if len(agents) != 1 or len(start["input"]) != 1 or start["input"][0]["type"] != "text":
        raise ValueError("Unexpected input/output requires manual privacy review")
    return {"thread_id": start["threadId"], "turn_id": ending["id"],
            "prompt": start["input"][0]["text"], "response": agents[0]["text"],
            "agent_message_id": agents[0]["id"]}


def review(value, candidate):
    if value.get("type") == "message":
        subset(value, ("type", "id", "role", "content", "internal_chat_message_metadata_passthrough"))
        meta, content = value["internal_chat_message_metadata_passthrough"], value["content"]
        subset(meta, ("turn_id", "create_time", "content_item_kinds"))
        if (value["role"] != "user" or (candidate.get("model_input_message_id") is not None
                                       and value["id"] != candidate["model_input_message_id"])
                or meta["turn_id"] != candidate["turn_id"] or meta["content_item_kinds"] != ["user.text"]
                or not number(meta["create_time"]) or not isinstance(content, list) or len(content) != 1):
            raise ValueError("Unreviewed model input or metadata")
        subset(content[0], ("type", "text"))
        if content[0]["type"] != "input_text" or content[0]["text"] != candidate["prompt"]:
            raise ValueError("Unrelated input text")
    elif value.get("method") == "turn/completed":
        subset(value, ("method", "params", "emittedAtMs"))
        subset(value["params"], ("threadId", "turn"))
        turn = value["params"]["turn"]
        subset(turn, ("id", "items", "itemsView", "status", "error", "startedAt", "completedAt", "durationMs"))
        if (value["params"]["threadId"] != candidate["thread_id"] or turn["id"] != candidate["turn_id"]
                or turn["status"] != "completed" or turn["error"] is not None
                or turn["itemsView"] not in ("summary", "full") or len(turn["items"]) != 1
                or not all(number(turn[k]) for k in ("startedAt", "completedAt", "durationMs"))
                or not number(value["emittedAtMs"])):
            raise ValueError("Unreviewed terminal record")
        item = turn["items"][0]
        subset(item, ("type", "id", "text", "phase", "memoryCitation", "delivery", "questions"))
        if (item["type"] != "agentMessage" or item["phase"] != "final_answer"
                or item["id"] != candidate["agent_message_id"] or item["text"] != candidate["response"]
                or any(item.get(k) is not None for k in ("memoryCitation", "delivery", "questions"))):
            raise ValueError("Unrelated assistant item or unreviewed annotations")
    else:
        raise ValueError("Unreviewed record type")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("capture", "records", "score", "memprocfs", "observer", "output"):
        cli.add_argument("--" + name, required=True, type=Path)
    cli.add_argument("--observations", type=Path,
                     help="Host observation used only for post-score privacy review of a zero-candidate case")
    args = cli.parse_args()
    result, score, observer = read(args.records), read(args.score), read(args.observer)
    if hashlib.sha256(args.records.read_bytes()).hexdigest() != score["recovered_output_sha256"]:
        raise SystemExit("The score is not for this sealed recovery")
    count = result["join"]["candidate_count"]
    if count == 1 and len(score["candidate_scores"]) == 1 and score["candidate_scores"][0]["all_five_match"]:
        candidate = result["join"]["candidates"][0]
        if not candidate["agent_id_independently_bound"] or candidate["api_user_item_id_recovered"]:
            raise SystemExit("Unexpected identifier scope")
    elif count == 0 and score["candidate_count"] == 0 and args.observations:
        candidate = observed_for_review(args.observations)
    else:
        raise SystemExit("Ambiguous or mismatched output requires manual privacy review")
    if not candidate["prompt"].startswith("For the synthetic label "):
        raise SystemExit("Unexpected synthetic-case or identifier scope")
    fixture = []
    with (args.capture / "memory.verified.raw").open("rb") as source:
        for record in result["records"]:
            review(record["payload"], candidate)
            raw = bytearray()
            for span in record["source_spans"][0]:
                source.seek(span["physical"])
                raw.extend(source.read(span["size"]))
            if len(raw) != record["raw_byte_length"] or hashlib.sha256(raw).hexdigest() != record["record_sha256"]:
                raise SystemExit("Raw source bytes no longer match the sealed result")
            fixture.append({"encoding": record["encoding"], "raw_hex": raw.hex(),
                            "record_sha256": record["record_sha256"], "raw_byte_length": len(raw)})
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    for source, name in ((args.records, "recovery.json"), (args.score, "score.json"),
                         (args.memprocfs, "memprocfs-records.json"),
                         (args.capture / "acquisition.json", "acquisition.json"),
                         (args.capture / "copy-verification-private.json", "copy-verification.json")):
        shutil.copyfile(source, target / name)
    expected = {key: candidate[key] for key in ("thread_id", "turn_id", "prompt", "response",
                "model_input_message_id", "agent_message_id", "agent_id_independently_bound", "api_user_item_id_recovered")} if count else {}
    with (target / "source-byte-fixture.json").open("x", encoding="utf-8") as output:
        json.dump({"scope": "Reviewed synthetic bytes only; NOT full RAM or an original process map",
                   "records": fixture, "expected_candidate_count": count, "expected": expected}, output, indent=2)
    with (target / "observer-comparison.json").open("x", encoding="utf-8") as output:
        json.dump({"scope": "Opaque guest transport relay, not native backend attribution",
                   "stats": observer["stats"], "unique_complete_records": observer["unique_complete_records"],
                   "linked_candidates": observer["join"]["candidate_count"]}, output, indent=2)
    presentation = "turn-for-viewer.json" if count else "observation-not-recovery.json"
    with (target / presentation).open("x", encoding="utf-8") as output:
        json.dump({"trial_id": score["trial_id"], "cohort": score["cohort"],
                   **(expected if count else candidate),
                   "five_linked_fields_match_observation": score["candidate_scores"][0]["all_five_match"] if count else None,
                   "model_input_id_independently_ground_truth_scored": False,
                   "timestamp_warning": "Model-input creation time is NOT a human submission timestamp",
                   "account_identity_claimed": False,
                   "presentation_only": "Selected recovered fields" if count else "HOST OBSERVATION ONLY: these five fields were NOT linked by the RAM parser"}, output, indent=2)
    print(json.dumps({"published_synthetic_records": len(fixture), "full_ram_published": False,
                      "unfiltered_rpc_published": False, "observer_candidates": observer["join"]["candidate_count"]}))


if __name__ == "__main__":
    main()
