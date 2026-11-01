"""Development: link observed native CLI core-event serializations in raw RAM.

Different grammar from the public app-server JSON-RPC wire. Input receives no
known prompt, response or ID. A candidate proves only the recovered fragment,
not that the whole conversation or an account identity has been reconstructed.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from bounded_json import DEFAULT_CAP
from cli_rpc_records import scan as framed_scan, valid_id

CORE_TYPES = {"item_completed", "task_complete", "agentMessage"}
METHOD_FILES = ("bounded_json.py", "cli_rpc_records.py", "cli_core_events.py")


def method_hashes():
    root = Path(__file__).resolve().parent
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in METHOD_FILES}


def core_record(value):
    return (isinstance(value, dict) and isinstance(value.get("type"), str)
            and value["type"] in CORE_TYPES)


def optional_time(value):
    # These observed fields are integer seconds/milliseconds, not arbitrary
    # JSON values. Missing timestamps do not create an attribution link.
    return value is None or (type(value) is int and value >= 0)


def support(record):
    return {key: record[key] for key in ("record_sha256", "encoding", "raw_byte_length",
                                         "source_virtual_addresses", "source_spans")}


def join_core(records):
    users, completions, agents = defaultdict(dict), defaultdict(dict), defaultdict(dict)
    rejected = Counter()
    for record in records:
        value = record["payload"]
        if not isinstance(value, dict):
            continue
        if value.get("type") == "item_completed":
            item = value.get("item")
            if (not valid_id(value.get("thread_id")) or not valid_id(value.get("turn_id")) or
                    not isinstance(item, dict) or item.get("type") != "UserMessage" or not valid_id(item.get("id"))):
                continue
            content = item.get("content")
            if (not isinstance(content, list) or not content or
                    any(not isinstance(part, dict) or part.get("type") != "text" or
                        not isinstance(part.get("text"), str) for part in content)):
                continue
            prompt = "".join(part["text"] for part in content)
            key = item["id"], prompt
            identity = value["thread_id"], value["turn_id"]
            users[identity].setdefault(key, []).append(support(record))
        elif value.get("type") == "task_complete":
            if valid_id(value.get("turn_id")) and isinstance(value.get("last_agent_message"), str) and value["last_agent_message"]:
                if not all(optional_time(value.get(field)) for field in ("started_at", "completed_at", "duration_ms")):
                    rejected["invalid_task_timestamp"] += 1
                    continue
                if (value.get("started_at") is not None and value.get("completed_at") is not None
                        and value["completed_at"] < value["started_at"]):
                    rejected["task_end_before_start"] += 1
                    continue
                key = value["last_agent_message"], value.get("started_at"), value.get("completed_at"), value.get("duration_ms")
                completions[value["turn_id"]].setdefault(key, []).append(support(record))
        elif value.get("type") == "agentMessage":
            if (valid_id(value.get("id")) and isinstance(value.get("text"), str) and value["text"] and
                    value.get("phase") == "final_answer"):
                agents[value["text"]].setdefault(value["id"], []).append(support(record))

    thread_bindings = defaultdict(set)
    for thread_id, turn_id in users:
        thread_bindings[turn_id].add(thread_id)
    candidates, ambiguous = [], []
    for (thread_id, turn_id), variants in sorted(users.items()):
        endings = completions.get(turn_id, {})
        if len(variants) != 1 or len(endings) != 1 or len(thread_bindings[turn_id]) != 1:
            ambiguous.append({"thread_id": thread_id, "turn_id": turn_id,
                              "user_variants": len(variants), "completion_variants": len(endings),
                              "thread_bindings_for_turn": len(thread_bindings[turn_id])})
            continue
        (user_id, prompt), user_support = next(iter(variants.items()))
        (response, start, end, duration), completion_support = next(iter(endings.items()))
        # The standalone agent object has no thread/turn field. Even a unique
        # exact text match is not an independent identifier binding.
        unbound = [{"agent_message_id": identity, "association": "exact text only; not thread/turn bound",
                    "support": sources} for identity, sources in sorted(agents.get(response, {}).items())]
        candidates.append({"thread_id": thread_id, "turn_id": turn_id, "user_message_id": user_id,
                           "prompt": prompt, "response": response,
                           "task_complete_times_raw": {"started_at": start, "completed_at": end, "duration_ms": duration},
                           "user_support": user_support, "completion_support": completion_support,
                           "text_matching_unbound_agent_objects": unbound,
                           "agent_id_independently_bound": False,
                           "completion_scope": "task_complete serialization; not a universal success/erasure claim"})
    return {"rule": "same process; exact turn ID; one thread binding, user variant and task-complete variant",
            "candidate_count": len(candidates), "candidates": candidates,
            "incomplete_or_ambiguous": ambiguous,
            "unbound_agent_object_count": sum(len(items) for items in agents.values()),
            "semantic_rejections": dict(rejected)}


def recover(source, values, image_size, cap=DEFAULT_CAP):
    parsed = framed_scan(source, values, image_size, cap=cap, keep_rejected=True,
                         prefixes=('{"type"',))
    records = [record for record in parsed["development_format_inspection_private"]
               if core_record(record["payload"])]
    return {"method": "development: observed CLI core events, not public RPC packets",
            "ground_truth_supplied": False, "scope": "selected resident user-space mappings",
            "record_byte_cap": cap, "user_space_rows": parsed["user_space_rows"],
            "skipped_kernel_rows": parsed["skipped_kernel_rows"], "stats": parsed["stats"],
            "unique_complete_core_records": len(records), "records": records, "join": join_core(records)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--record-cap", type=int, default=DEFAULT_CAP)
    args = cli.parse_args()
    before = method_hashes()
    values = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    with args.image.open("rb") as source:
        result = recover(source, values, args.image.stat().st_size, args.record_cap)
    if method_hashes() != before:
        raise SystemExit("Method source changed during recovery; refusing to seal output")
    result["executed_method_sha256"] = before
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=True)
    print(json.dumps({key: value for key, value in result.items() if key not in ("records", "join")}, indent=2))
    print(json.dumps({"candidate_count": result["join"]["candidate_count"],
                      "unbound_agent_objects": result["join"]["unbound_agent_object_count"]}))


if __name__ == "__main__":
    main()
