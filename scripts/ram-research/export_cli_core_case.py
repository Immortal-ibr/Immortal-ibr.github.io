"""Export a reviewed synthetic CLI case, never an unfiltered RAM scan.

This publishing filter runs AFTER recovery/scoring. Its known synthetic values
are not parser inputs. It refuses extra record fields or unrelated candidates.
Full RPC logs, format inspection, profiles and whole images remain private.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def subset(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError("Unexpected fields require a separate privacy review")


def review(value, candidate):
    kind = value["type"]
    if kind == "item_completed":
        subset(value, ("type", "thread_id", "turn_id", "item", "started_at_ms", "completed_at_ms"))
        subset(value["item"], ("type", "id", "content"))
        content = value["item"]["content"]
        if len(content) != 1:
            raise ValueError("Only the reviewed single-text synthetic input can be published")
        subset(content[0], ("type", "text", "text_elements"))
        if content[0].get("text_elements") not in (None, []):
            raise ValueError("Input annotation requires review")
        if (value["thread_id"] != candidate["thread_id"] or value["turn_id"] != candidate["turn_id"]
                or value["item"]["id"] != candidate["user_message_id"]
                or content[0]["text"] != candidate["prompt"]):
            raise ValueError("An unrelated user record cannot be exported")
    elif kind == "task_complete":
        subset(value, ("type", "turn_id", "last_agent_message", "started_at", "completed_at", "duration_ms", "time_to_first_token_ms"))
        if value["turn_id"] != candidate["turn_id"] or value["last_agent_message"] != candidate["response"]:
            raise ValueError("An unrelated completion cannot be exported")
    elif kind == "agentMessage":
        subset(value, ("type", "id", "text", "phase", "memoryCitation", "delivery", "questions"))
        if value["text"] != candidate["response"] or any(value.get(k) is not None for k in ("memoryCitation", "delivery", "questions")):
            raise ValueError("Assistant extras require review")
    else:
        raise ValueError("Unreviewed serialization")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--capture", required=True, type=Path)
    cli.add_argument("--records", required=True, type=Path)
    cli.add_argument("--score", required=True, type=Path)
    cli.add_argument("--observer", required=True, type=Path)
    cli.add_argument("--observations", type=Path,
                     help="Host-only RPC log required to privacy-review a zero-candidate case after scoring")
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    result, score, observer = read(args.records), read(args.score), read(args.observer)
    if hashlib.sha256(args.records.read_bytes()).hexdigest() != score["recovered_output_sha256"]:
        raise SystemExit("The reviewed score does not refer to this recovery")
    count = result["join"]["candidate_count"]
    if count == 1 and len(score["candidate_scores"]) == 1 and score["candidate_scores"][0]["all_five_match"]:
        candidate = result["join"]["candidates"][0]
    elif count == 0 and score["candidate_count"] == 0 and args.observations:
        observed = [json.loads(line) for line in args.observations.read_text(encoding="utf-8").splitlines()]
        submissions = [e["message"]["params"] for e in observed
                       if e["direction"] == "host_to_native_cli" and e["message"].get("method") == "turn/start"]
        if len(submissions) != 1:
            raise SystemExit("Zero-case review requires exactly one observed synthetic turn")
        submission = submissions[0]
        endings = [e["message"]["params"]["turn"] for e in observed
                   if e["direction"] == "native_cli_to_host" and e["message"].get("method") == "turn/completed"
                   and e["message"]["params"]["threadId"] == submission["threadId"]]
        if len(endings) != 1 or endings[0]["status"] != "completed":
            raise SystemExit("No unique observed completed turn for privacy review")
        ending = endings[0]
        items = [e["message"]["params"]["item"] for e in observed if e["direction"] == "native_cli_to_host"
                 and e["message"].get("method") == "item/completed"
                 and e["message"]["params"]["threadId"] == submission["threadId"]
                 and e["message"]["params"]["turnId"] == ending["id"]]
        users = [item for item in items if item["type"] == "userMessage"]
        agents = [item for item in items if item["type"] == "agentMessage" and item.get("phase") == "final_answer"]
        if len(users) != 1 or len(agents) != 1:
            raise SystemExit("Unexpected input/output items require manual review")
        candidate = {"thread_id": submission["threadId"], "turn_id": ending["id"], "user_message_id": users[0]["id"],
                     "prompt": "".join(part["text"] for part in submission["input"]), "response": agents[0]["text"]}
    else:
        raise SystemExit("Ambiguous or mismatched records require manual privacy review")
    if not candidate["prompt"].startswith("For the synthetic label "):
        raise SystemExit("This is not the approved synthetic-prompt format")
    fixture = []
    with (args.capture / "memory.verified.raw").open("rb") as source:
        for record in result["records"]:
            review(record["payload"], candidate)
            raw = bytearray()
            for span in record["source_spans"][0]:
                source.seek(span["physical"])
                raw.extend(source.read(span["size"]))
            if len(raw) != record["raw_byte_length"] or hashlib.sha256(raw).hexdigest() != record["record_sha256"]:
                raise SystemExit("Source record bytes no longer match the sealed recovery")
            fixture.append({"encoding": record["encoding"], "raw_hex": raw.hex(),
                            "record_sha256": record["record_sha256"], "raw_byte_length": len(raw)})
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    for src, name in ((args.records, "recovery.json"), (args.score, "score.json"),
                      (args.capture / "acquisition.json", "acquisition.json"),
                      (args.capture / "copy-verification-private.json", "copy-verification.json"),
                      (args.capture / "core-records-memprocfs-private.json", "memprocfs-records.json")):
        shutil.copyfile(src, target / name)
    with (target / "source-byte-fixture.json").open("x", encoding="utf-8") as output:
        expected = {key: candidate[key] for key in ("thread_id", "turn_id", "user_message_id", "prompt", "response", "agent_id_independently_bound")} if count else {}
        json.dump({"scope": "Only exact bytes of reviewed synthetic records; NOT a full memory image or native process map",
                   "records": fixture, "expected_candidate_count": count, "expected": expected}, output, indent=2)
    with (target / "observer-comparison.json").open("x", encoding="utf-8") as output:
        json.dump({"observer_scope": "opaque guest transport relay, not native backend attribution",
                   "stats": observer["stats"], "unique_complete_core_records": observer["unique_complete_core_records"],
                   "linked_candidates": observer["join"]["candidate_count"],
                   "unbound_agent_objects": observer["join"]["unbound_agent_object_count"]}, output, indent=2)
    presentation = "turn-for-viewer.json" if count else "observation-not-recovery.json"
    with (target / presentation).open("x", encoding="utf-8") as output:
        data = {"trial_id": score["trial_id"], "cohort": score["cohort"],
                   **{key: candidate[key] for key in ("thread_id", "turn_id", "user_message_id", "prompt", "response")},
                   "assistant_id_independently_bound": False,
                   "presentation_only": "Selected recovered fields" if count else "HOST OBSERVATION ONLY: these five fields were NOT linked by the RAM parser"}
        if count:
            data.update({"five_linked_fields_match_observation": score["candidate_scores"][0]["all_five_match"],
                         "task_times": candidate["task_complete_times_raw"],
                         "text_matching_unbound_assistant_ids": [item["agent_message_id"]
                             for item in candidate["text_matching_unbound_agent_objects"]]})
        json.dump(data, output, indent=2)
    print(json.dumps({"published_synthetic_records": len(fixture), "full_ram_published": False,
                      "unfiltered_rpc_published": False, "observer_candidates": observer["join"]["candidate_count"]}))


if __name__ == "__main__":
    main()
