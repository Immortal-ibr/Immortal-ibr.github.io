"""Observed model-input metadata + terminal RPC join; development, not core-v1.

No known text/IDs/offsets. Model-input IDs are NOT API user-item IDs. The observed
user.text tag distinguishes human text from role=user environment context.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from bounded_json import DEFAULT_CAP
from cli_rpc_records import PREFIXES, scan, valid_id

METHOD_FILES = ("bounded_json.py", "cli_rpc_records.py", "cli_model_turns.py")


def support(record):
    return {key: record[key] for key in ("record_sha256", "encoding", "raw_byte_length",
                                         "source_virtual_addresses", "source_spans")}


def tagged_user(value):
    if not isinstance(value, dict) or value.get("type") != "message" or value.get("role") != "user":
        return False
    meta = value.get("internal_chat_message_metadata_passthrough")
    parts = value.get("content")
    return (isinstance(meta, dict) and valid_id(meta.get("turn_id")) and valid_id(value.get("id"))
            and isinstance(parts, list) and bool(parts)
            and meta.get("content_item_kinds") == ["user.text"] * len(parts)
            and all(isinstance(part, dict) and part.get("type") == "input_text"
                    and isinstance(part.get("text"), str) for part in parts))


def terminal(value):
    if not isinstance(value, dict) or value.get("method") != "turn/completed":
        return False
    params = value.get("params")
    if not isinstance(params, dict) or not valid_id(params.get("threadId")):
        return False
    turn = params.get("turn")
    return (isinstance(turn, dict) and valid_id(turn.get("id")) and turn.get("status") == "completed"
            and turn.get("error") is None and isinstance(turn.get("items"), list))


def join_model(records):
    users, answers, bindings = defaultdict(dict), defaultdict(dict), defaultdict(set)
    rejected = Counter()
    for record in records:
        value = record["payload"]
        if tagged_user(value):
            meta = value["internal_chat_message_metadata_passthrough"]
            prompt = "".join(part["text"] for part in value["content"])
            key = value["id"], prompt
            users[meta["turn_id"]].setdefault(key, []).append({**support(record), "model_input_create_time_raw": meta.get("create_time")})
        elif terminal(value):
            params, turn = value["params"], value["params"]["turn"]
            identity = params["threadId"], turn["id"]
            bindings[turn["id"]].add(params["threadId"])
            for item in turn["items"]:
                if (not isinstance(item, dict) or item.get("type") != "agentMessage"
                        or not valid_id(item.get("id")) or not isinstance(item.get("text"), str)
                        or not item["text"] or item.get("phase") != "final_answer"):
                    rejected["non_final_or_nontext_item"] += 1
                    continue
                key = item["id"], item["text"]
                answers[identity].setdefault(key, []).append({**support(record),
                    "turn_times_raw": {"started_at": turn.get("startedAt"), "completed_at": turn.get("completedAt"), "duration_ms": turn.get("durationMs")}})
    candidates, incomplete = [], []
    for (thread_id, turn_id), finals in sorted(answers.items()):
        inputs = users.get(turn_id, {})
        summary = {"thread_id": thread_id, "turn_id": turn_id, "tagged_input_variants": len(inputs),
                   "final_agent_variants": len(finals), "thread_bindings_for_turn": len(bindings[turn_id])}
        if len(inputs) != 1 or len(finals) != 1 or len(bindings[turn_id]) != 1:
            incomplete.append(summary)
            continue
        (model_id, prompt), input_support = next(iter(inputs.items()))
        (agent_id, response), answer_support = next(iter(finals.items()))
        candidates.append({**summary, "prompt": prompt, "response": response,
                           "model_input_message_id": model_id, "agent_message_id": agent_id,
                           "agent_id_independently_bound": True, "api_user_item_id_recovered": False,
                           "input_support": input_support, "answer_support": answer_support})
    return {"rule": "same process; exact turn ID; one user.text input, final agent variant and thread binding",
            "candidate_count": len(candidates), "candidates": candidates,
            "incomplete_or_ambiguous": incomplete, "semantic_rejections": dict(rejected)}


def recover(source, values, image_size, cap=DEFAULT_CAP):
    parsed = scan(source, values, image_size, cap=cap, keep_rejected=True, prefixes=PREFIXES + ('{"type"',))
    frames = parsed["records"] + parsed["development_format_inspection_private"]
    records = [record for record in frames if tagged_user(record["payload"]) or terminal(record["payload"])]
    env = sum(isinstance(record["payload"], dict) and record["payload"].get("role") == "user"
              and not tagged_user(record["payload"]) for record in frames)
    return {"method": "observed tagged model input + terminal RPC; separate from core-v1",
            "ground_truth_supplied": False, "record_byte_cap": cap,
            "scope": "selected resident user-space mappings; not a native object graph",
            "user_space_rows": parsed["user_space_rows"], "skipped_kernel_rows": parsed["skipped_kernel_rows"],
            "stats": parsed["stats"], "other_user_role_records_excluded": env,
            "unique_complete_records": len(records), "records": records, "join": join_model(records)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--record-cap", type=int, default=DEFAULT_CAP)
    args = cli.parse_args()
    root = Path(__file__).resolve().parent
    hashes = lambda: {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in METHOD_FILES}
    before = hashes()
    values = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    with args.image.open("rb") as image:
        result = recover(image, values, args.image.stat().st_size, args.record_cap)
    if hashes() != before:
        raise SystemExit("Method changed during recovery")
    result["executed_method_sha256"] = before
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    print(json.dumps({key: value for key, value in result.items() if key not in ("records", "join")}, indent=2))
    print(json.dumps({"candidate_count": result["join"]["candidate_count"]}))


if __name__ == "__main__":
    main()
