"""Development: join a native response.create request to task_complete in RAM.

This grammar was discovered after the two earlier frozen CLI methods failed on
the museum image. It is a post-hoc method, not a prospective held-out result.
Neither ground-truth text nor an offset is supplied. The input record's
model-message ID is not an API user-item ID; task_complete does not bind an
assistant-message ID.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from bounded_json import DEFAULT_CAP
from cli_core_events import optional_time
from cli_model_turns import tagged_user
from cli_rpc_records import PREFIXES, scan, valid_id

METHOD_FILES = ("bounded_json.py", "cli_rpc_records.py", "cli_core_events.py",
                "cli_model_turns.py", "cli_request_core_turns.py")


def method_hashes():
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in METHOD_FILES}


def support(record):
    return {key: record[key] for key in ("record_sha256", "encoding", "raw_byte_length",
                                         "source_virtual_addresses", "source_spans")}


def request_record(value):
    if not isinstance(value, dict) or value.get("type") != "response.create":
        return False
    meta = value.get("client_metadata")
    return (isinstance(meta, dict) and valid_id(meta.get("thread_id"))
            and valid_id(meta.get("turn_id")) and isinstance(value.get("input"), list))


def completion_record(value):
    if not isinstance(value, dict) or value.get("type") != "task_complete":
        return False
    if not valid_id(value.get("turn_id")) or not isinstance(value.get("last_agent_message"), str):
        return False
    if not value["last_agent_message"]:
        return False
    fields = ("started_at", "completed_at", "duration_ms")
    if not all(optional_time(value.get(field)) for field in fields):
        return False
    start, end = value.get("started_at"), value.get("completed_at")
    return start is None or end is None or end >= start


def join(records):
    requests, completions, bindings = defaultdict(dict), defaultdict(dict), defaultdict(set)
    rejected = Counter()
    for record in records:
        value = record["payload"]
        if request_record(value):
            meta = value["client_metadata"]
            identity = (meta["thread_id"], meta["turn_id"])
            bindings[meta["turn_id"]].add(meta["thread_id"])
            inputs = [item for item in value["input"]
                      if tagged_user(item)
                      and item["internal_chat_message_metadata_passthrough"]["turn_id"] == meta["turn_id"]]
            if len(inputs) != 1:
                rejected["request_without_one_matching_human_input"] += 1
                continue
            item = inputs[0]
            prompt = "".join(part["text"] for part in item["content"])
            if not prompt:
                rejected["empty_human_input"] += 1
                continue
            key = item["id"], prompt
            requests[identity].setdefault(key, []).append(support(record))
        elif completion_record(value):
            key = (value["last_agent_message"], value.get("started_at"),
                   value.get("completed_at"), value.get("duration_ms"))
            completions[value["turn_id"]].setdefault(key, []).append(support(record))

    candidates, incomplete = [], []
    for (thread_id, turn_id), inputs in sorted(requests.items()):
        endings = completions.get(turn_id, {})
        summary = {"thread_id": thread_id, "turn_id": turn_id,
                   "input_variants": len(inputs), "completion_variants": len(endings),
                   "thread_bindings_for_turn": len(bindings[turn_id])}
        if len(inputs) != 1 or len(endings) != 1 or len(bindings[turn_id]) != 1:
            incomplete.append(summary)
            continue
        (model_id, prompt), request_support = next(iter(inputs.items()))
        (response, start, end, duration), completion_support = next(iter(endings.items()))
        candidates.append({**summary, "model_input_message_id": model_id,
                           "prompt": prompt, "response": response,
                           "task_complete_times_raw": {"started_at": start,
                                                       "completed_at": end,
                                                       "duration_ms": duration},
                           "request_support": request_support,
                           "completion_support": completion_support,
                           "assistant_message_id_independently_bound": False,
                           "api_user_item_id_recovered": False})
    return {"rule": "same native process; response.create metadata thread/turn IDs; exactly one tagged human input for that turn; unique task_complete for the same turn",
            "candidate_count": len(candidates), "candidates": candidates,
            "incomplete_or_ambiguous": incomplete, "semantic_rejections": dict(rejected)}


def recover(source, rows, image_size, cap=DEFAULT_CAP):
    parsed = scan(source, rows, image_size, cap=cap, keep_rejected=True,
                  prefixes=PREFIXES + ('{"type"',))
    frames = parsed["records"] + parsed["development_format_inspection_private"]
    records = [record for record in frames
               if request_record(record["payload"]) or completion_record(record["payload"])]
    return {"method": "post-hoc native request/core join; distinct from frozen core-v1 and model-input-v1",
            "ground_truth_supplied": False,
            "scope": "one native process's resident user-space mappings",
            "record_byte_cap": cap, "user_space_rows": parsed["user_space_rows"],
            "skipped_kernel_rows": parsed["skipped_kernel_rows"],
            "framing_stats": parsed["stats"], "unique_complete_records": len(records),
            "records": records, "join": join(records)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--record-cap", type=int, default=DEFAULT_CAP)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    before = method_hashes()
    rows = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    with args.image.open("rb") as image:
        result = recover(image, rows, args.image.stat().st_size, args.record_cap)
    if method_hashes() != before:
        raise SystemExit("Method changed during recovery")
    result["executed_method_sha256"] = before
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=True)
    print(json.dumps({"unique_complete_records": len(result["records"]),
                      "candidate_count": result["join"]["candidate_count"],
                      "semantic_rejections": result["join"]["semantic_rejections"]}))


if __name__ == "__main__":
    main()
