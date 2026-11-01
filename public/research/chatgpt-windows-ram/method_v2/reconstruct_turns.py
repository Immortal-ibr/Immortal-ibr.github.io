"""Join parsed stream-item records into candidate ChatGPT turns (v2).

Uses conversation/turn IDs and parent-stream ancestry found in RAM. It receives
no ground-truth content or identifiers. A candidate needs a user input message,
an assistant message, a nonempty response, and a completion event on the same
parent chain. Accepts user messages in both input_message events and v.message
events, the latter observed during the two-chat development pilot. All
candidates are retained so ambiguous joins remain visible.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path


def data_events(record):
    for event in record["decoded_events"]:
        data = event.get("data")
        if isinstance(data, dict):
            yield data


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--parsed", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    parsed = json.loads(args.parsed.read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for record in parsed["records"]:
        payload = record["payload"]
        conversation_id = payload.get("conversation_id")
        turn_id = payload.get("turn_id")
        if isinstance(conversation_id, str) and isinstance(turn_id, str):
            groups[(conversation_id, turn_id)].append(record)

    candidates = []
    group_audit = []
    for (conversation_id, turn_id), records in groups.items():
        by_id = {r["payload"].get("stream_item_id"): r for r in records if isinstance(r["payload"].get("stream_item_id"), str)}

        def ancestor_ids(stream_id):
            result = []
            seen = set()
            current = stream_id
            while current in by_id and current not in seen:
                seen.add(current)
                result.append(current)
                current = by_id[current]["payload"].get("parent_stream_item_id")
            return result

        def is_ancestor(ancestor_id, child_id):
            return ancestor_id in ancestor_ids(child_id)

        users = []
        assistants = []
        patches = []
        markers = []
        completions = []
        for record in records:
            stream_id = record["payload"].get("stream_item_id")
            for data in data_events(record):
                if data.get("type") == "input_message":
                    message = data.get("input_message")
                    if isinstance(message, dict) and (message.get("author") or {}).get("role") == "user":
                        users.append((record, message))
                value = data.get("v")
                if isinstance(value, dict):
                    message = value.get("message")
                    if isinstance(message, dict):
                        role = (message.get("author") or {}).get("role")
                        if role == "assistant":
                            assistants.append((record, message))
                        elif role == "user":
                            users.append((record, message))
                if data.get("o") == "patch" and isinstance(value, list):
                    patches.append((record, value))
                if data.get("type") == "message_marker" and isinstance(data.get("message_id"), str):
                    markers.append((record, data["message_id"]))
                if data.get("type") == "message_stream_complete":
                    completions.append(record)

        group_audit.append({
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "complete_records": len(records),
            "user_inputs": len(users),
            "assistant_message_starts": len(assistants),
            "patch_records": len(patches),
            "completion_events": len(completions),
        })

        assistant_stream_ids = {r["payload"].get("stream_item_id") for r, _ in assistants}

        def closest_assistant_origin(stream_id):
            for ancestor in ancestor_ids(stream_id):
                if ancestor in assistant_stream_ids:
                    return ancestor
            return None

        for assistant_record, assistant in assistants:
            assistant_sid = assistant_record["payload"].get("stream_item_id")
            assistant_id = assistant.get("id")
            if not isinstance(assistant_sid, str) or not isinstance(assistant_id, str):
                continue
            parent_users = [(r, m) for r, m in users if is_ancestor(r["payload"].get("stream_item_id"), assistant_sid)]
            descendant_patches = [(r, operations) for r, operations in patches if closest_assistant_origin(r["payload"].get("stream_item_id")) == assistant_sid]
            descendant_patches.sort(key=lambda item: len(ancestor_ids(item[0]["payload"].get("stream_item_id"))))
            completion_records = [r for r in completions if closest_assistant_origin(r["payload"].get("stream_item_id")) == assistant_sid]
            marker_records = [r for r, message_id in markers if message_id == assistant_id and closest_assistant_origin(r["payload"].get("stream_item_id")) == assistant_sid]
            initial_parts = (assistant.get("content") or {}).get("parts") or [""]
            response = initial_parts[0] if isinstance(initial_parts[0], str) else ""
            used_patches = []
            for patch_record, operations in descendant_patches:
                for operation in operations:
                    if operation.get("p") != "/message/content/parts/0" or not isinstance(operation.get("v"), str):
                        continue
                    if operation.get("o") == "append":
                        response += operation["v"]
                        used_patches.append(patch_record)
                    elif operation.get("o") == "replace":
                        response = operation["v"]
                        used_patches.append(patch_record)
            if not response or not completion_records or not marker_records:
                continue
            for user_record, user in parent_users:
                parts = (user.get("content") or {}).get("parts") or []
                prompt = parts[0] if parts and isinstance(parts[0], str) else None
                if prompt is None:
                    continue
                candidates.append({
                    "conversation_id": conversation_id,
                    "turn_id": turn_id,
                    "user_message_id": user.get("id"),
                    "assistant_message_id": assistant_id,
                    "prompt": prompt,
                    "response": response,
                    "user_create_time_unix": user.get("create_time"),
                    "assistant_create_time_unix": assistant.get("create_time"),
                    "support": {
                        "user_input_record_sha256": user_record["record_sha256"],
                        "assistant_start_record_sha256": assistant_record["record_sha256"],
                        "response_patch_record_sha256": sorted({r["record_sha256"] for r in used_patches}),
                        "assistant_marker_record_sha256": sorted({r["record_sha256"] for r in marker_records}),
                        "completion_record_sha256": sorted({r["record_sha256"] for r in completion_records}),
                        "user_stream_item_id": user_record["payload"].get("stream_item_id"),
                        "assistant_stream_item_id": assistant_sid,
                    },
                    "ambiguous_user_ancestors": len(parent_users) != 1,
                })

    output = {
        "method": "bounded stream item parsing; parent-stream ancestry; user input, assistant start, response patch, marker, completion",
        "ground_truth_supplied": False,
        "groups": group_audit,
        "candidate_turns": candidates,
    }
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"groups": len(groups), "candidate_turns": len(candidates)}, indent=2))


if __name__ == "__main__":
    main()
