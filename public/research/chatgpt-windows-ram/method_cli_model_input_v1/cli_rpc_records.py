"""Development: recover framed native app-server RPC objects from resident RAM.

Inputs are a raw physical image and a matching Volatility memmap, never a known
prompt/answer/ID/offset. This is serialized-record carving, not Rust object-graph
reconstruction. Transport-relay copies must be analyzed separately.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from bounded_json import (DEFAULT_CAP, ENCODINGS, MappedReader, clipped_spans,
                          frame_end, normalize_rows, strict_json)

METHODS = {"item/started", "item/completed", "turn/started", "turn/completed", "thread/started"}
PREFIXES = ('{"method"', '{"params"', '{"jsonrpc"', '{"id"')


def valid_id(value):
    return isinstance(value, str) and 0 < len(value) <= 256


def relevant_rpc(value):
    if not isinstance(value, dict):
        return False
    if isinstance(value.get("method"), str) and value["method"] in METHODS and isinstance(value.get("params"), dict):
        return True
    result = value.get("result")
    return isinstance(result, dict) and isinstance(result.get("thread"), dict) and "turns" in result["thread"]


def scan(source, values, image_size, cap=DEFAULT_CAP, chunk_size=DEFAULT_CAP,
         keep_rejected=False, prefixes=PREFIXES):
    if cap <= 0 or chunk_size <= 0:
        raise ValueError("Caps must be positive")
    rows, skipped = normalize_rows(values, image_size)
    reader = MappedReader(source, rows)
    signatures = [(encoding, prefix.encode(encoding)) for encoding in ENCODINGS for prefix in prefixes]
    overlap = max(len(signature) for _, signature in signatures) - 1
    stats = Counter()
    records, seen, rejected_records = {}, set(), {}
    for run_start, run_size in reader.runs():
        tail = b""
        for position in range(run_start, run_start + run_size, chunk_size):
            block, _ = reader.read(position, min(chunk_size, run_start + run_size - position))
            window, base = tail + block, position - len(tail)
            for encoding, signature in signatures:
                offset = 0
                while (offset := window.find(signature, offset)) >= 0:
                    address = base + offset
                    offset += 1
                    if (address, encoding) in seen:
                        continue
                    seen.add((address, encoding))
                    stats["object_prefix_hits"] += 1
                    blob, spans = reader.read(address, cap)
                    try:
                        end = frame_end(blob, encoding)
                        if end is None:
                            stats["cap_limited_hits" if len(blob) == cap else "gap_or_end_truncated_hits"] += 1
                            continue
                        raw = blob[:end]
                        payload = strict_json(raw.decode(encoding, errors="strict"))
                        if not relevant_rpc(payload):
                            stats["format_rejected_hits"] += 1
                            if keep_rejected:
                                digest = hashlib.sha256(raw).hexdigest()
                                key = digest, encoding
                                if key not in rejected_records:
                                    rejected_records[key] = {"record_sha256": digest, "encoding": encoding,
                                        "raw_byte_length": len(raw), "payload": payload,
                                        "source_virtual_addresses": [], "source_spans": []}
                                rejected_records[key]["source_virtual_addresses"].append(address)
                                rejected_records[key]["source_spans"].append(clipped_spans(spans, end))
                            continue
                    except (ValueError, UnicodeError):
                        stats["invalid_json_or_encoding_hits"] += 1
                        continue
                    digest = hashlib.sha256(raw).hexdigest()
                    key = digest, encoding
                    if key not in records:
                        records[key] = {"record_sha256": digest, "encoding": encoding,
                                        "raw_byte_length": len(raw), "payload": payload,
                                        "source_virtual_addresses": [], "source_spans": []}
                    records[key]["source_virtual_addresses"].append(address)
                    records[key]["source_spans"].append(clipped_spans(spans, end))
                    stats["complete_rpc_occurrences"] += 1
            tail = window[-overlap:]
    result = {"method": "development: bounded native app-server RPC serialization",
              "scope": "selected resident user-space maps; not a native Rust object graph",
              "ground_truth_supplied": False, "record_byte_cap": cap,
              "user_space_rows": len(rows), "skipped_kernel_rows": skipped,
              "stats": dict(stats), "unique_complete_records": len(records),
              "records": list(records.values())}
    result["join"] = join(result["records"])
    if keep_rejected:
        result["development_format_inspection_private"] = list(rejected_records.values())
    return result


def join(records):
    """Join within this one process by thread/turn; keep conflicts as ambiguity."""
    turns = defaultdict(lambda: {"users": {}, "agents": {}, "completion": []})
    rejected = Counter()

    def item(thread_id, turn_id, entry, record, completed):
        if not (valid_id(thread_id) and valid_id(turn_id) and isinstance(entry, dict) and valid_id(entry.get("id"))):
            rejected["invalid_item_identity"] += 1
            return
        kind = entry.get("type")
        evidence = {"record_sha256": record["record_sha256"], "encoding": record["encoding"],
                    "source_virtual_addresses": record["source_virtual_addresses"]}
        if kind == "userMessage":
            content = entry.get("content")
            if (not isinstance(content, list) or not content or
                    any(not isinstance(part, dict) or part.get("type") != "text" or
                        not isinstance(part.get("text"), str) for part in content)):
                rejected["non_plaintext_user_item"] += 1
                return
            text = "".join(part["text"] for part in content)
            key = (entry["id"], text)
            target = turns[(thread_id, turn_id)]["users"]
        elif kind == "agentMessage" and completed:
            text = entry.get("text")
            if not isinstance(text, str) or not text:
                rejected["empty_agent_item"] += 1
                return
            if entry.get("phase") not in (None, "final_answer"):
                rejected["non_final_agent_item"] += 1
                return
            key = (entry["id"], text)
            target = turns[(thread_id, turn_id)]["agents"]
        else:
            return
        target.setdefault(key, []).append(evidence)

    def turn(thread_id, value, record, terminal):
        if not isinstance(value, dict) or not (valid_id(thread_id) and valid_id(value.get("id"))):
            rejected["invalid_turn_identity"] += 1
            return
        turn_id = value["id"]
        completed = terminal and value.get("status") == "completed" and value.get("error") is None
        if completed:
            turns[(thread_id, turn_id)]["completion"].append({
                "record_sha256": record["record_sha256"], "encoding": record["encoding"],
                "started_at": value.get("startedAt"), "completed_at": value.get("completedAt"),
                "duration_ms": value.get("durationMs"),
                "source_virtual_addresses": record["source_virtual_addresses"]})
        for entry in value.get("items", []) if isinstance(value.get("items"), list) else []:
            item(thread_id, turn_id, entry, record, completed)

    for record in records:
        value = record["payload"]
        method, params = value.get("method"), value.get("params", {})
        if method in ("item/started", "item/completed"):
            item(params.get("threadId"), params.get("turnId"), params.get("item"), record, method == "item/completed")
        elif method in ("turn/started", "turn/completed"):
            turn(params.get("threadId"), params.get("turn"), record, method == "turn/completed")
        elif isinstance(value.get("result"), dict) and isinstance(value["result"].get("thread"), dict):
            thread = value["result"]["thread"]
            for entry in thread.get("turns", []) if isinstance(thread.get("turns"), list) else []:
                turn(thread.get("id"), entry, record, True)

    candidates, incomplete = [], []
    for (thread_id, turn_id), evidence in sorted(turns.items()):
        summary = {"thread_id": thread_id, "turn_id": turn_id, "user_variants": len(evidence["users"]),
                   "final_agent_variants": len(evidence["agents"]), "completion_records": len(evidence["completion"])}
        if len(evidence["users"]) != 1 or len(evidence["agents"]) != 1 or not evidence["completion"]:
            incomplete.append(summary)
            continue
        (user_id, prompt), user_support = next(iter(evidence["users"].items()))
        (agent_id, response), agent_support = next(iter(evidence["agents"].items()))
        candidates.append({**summary, "user_message_id": user_id, "agent_message_id": agent_id,
                           "prompt": prompt, "response": response, "completion": evidence["completion"],
                           "user_support": user_support, "agent_support": agent_support})
    return {"rule": "same process, exact thread/turn IDs, one user and final agent variant plus completed turn",
            "candidate_count": len(candidates), "candidates": candidates,
            "incomplete_or_ambiguous": incomplete, "rejected": dict(rejected)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--record-cap", type=int, default=DEFAULT_CAP)
    cli.add_argument("--inspect-formats", action="store_true",
                     help="Development only: retain other complete JSON objects privately; no GT filter")
    args = cli.parse_args()
    values = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    with args.image.open("rb") as source:
        result = scan(source, values, args.image.stat().st_size, args.record_cap,
                      keep_rejected=args.inspect_formats,
                      prefixes=PREFIXES + ('{"type"', '{"role"', '{"content"', '{"timestamp"', '{"model"')
                      if args.inspect_formats else PREFIXES)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=True)
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ("records", "join", "development_format_inspection_private")}, indent=2))
    print(json.dumps({"candidate_count": result["join"]["candidate_count"]}))


if __name__ == "__main__":
    main()
