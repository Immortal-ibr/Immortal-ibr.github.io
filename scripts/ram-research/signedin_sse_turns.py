"""Join one complete signed-in ChatGPT SSE turn without known turn values.

Input is the private output of sse_event_records.py, including a byte-verified
contiguous segment. User -> optional system message(s) -> assistant ancestry,
assistant message markers, incremental content patches, final status and stream
completion must all agree. Unknown or conflicting shapes are rejected, not
filled with nearby strings. Full output must remain private.
"""

import argparse
import hashlib
import json
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
CONTENT_PATH = "/message/content/parts/0"


def text_message(value, role):
    if not isinstance(value, dict) or value.get("author", {}).get("role") != role:
        return False
    content = value.get("content")
    return (isinstance(value.get("id"), str) and bool(value["id"])
            and isinstance(content, dict) and content.get("content_type") == "text"
            and isinstance(content.get("parts"), list) and len(content["parts"]) == 1
            and isinstance(content["parts"][0], str))


def parent_of(message):
    metadata = message.get("metadata")
    return metadata.get("parent_id") if isinstance(metadata, dict) else None


def ancestry_reaches_user(assistant, user, messages):
    """Require a unique, acyclic ID chain through any intermediate messages."""
    current = assistant
    seen = {assistant["id"]}
    while True:
        parent = parent_of(current)
        if parent == user["id"]:
            return True
        if not isinstance(parent, str) or parent in seen or parent not in messages:
            return False
        seen.add(parent)
        current = messages[parent]


def reconstruct_segment(segment, records):
    indices = segment.get("record_indices")
    if not isinstance(indices, list) or not indices or len(indices) != len(set(indices)):
        return None, "invalid_segment_indices"
    if len(segment.get("control_gaps", [])) != len(indices) - 1:
        return None, "unverified_contiguity"
    try:
        events = [records[index]["event"]["data"] for index in indices]
    except (IndexError, KeyError, TypeError):
        return None, "invalid_event_reference"
    if any(not isinstance(event, dict) for event in events):
        return None, "non_object_event"

    inputs = [(index, event) for index, event in enumerate(events)
              if event.get("type") == "input_message"]
    completions = [(index, event) for index, event in enumerate(events)
                   if event.get("type") == "message_stream_complete"]
    if len(inputs) != 1 or len(completions) != 1:
        return None, "input_or_completion_cardinality"
    input_index, input_event = inputs[0]
    complete_index, complete = completions[0]
    user = input_event.get("input_message")
    conversation = input_event.get("conversation_id")
    if (not text_message(user, "user") or not user["content"]["parts"][0]
            or not isinstance(conversation, str) or not conversation
            or complete.get("conversation_id") != conversation
            or complete_index <= input_index):
        return None, "invalid_user_or_conversation"

    messages = {user["id"]: user}
    assistants = []
    for index, event in enumerate(events):
        if "v" not in event or not isinstance(event["v"], dict):
            continue
        wrapped = event["v"]
        message = wrapped.get("message")
        if not isinstance(message, dict):
            continue
        message_id = message.get("id")
        if (not isinstance(message_id, str) or not message_id
                or wrapped.get("conversation_id") != conversation
                or (message_id in messages and messages[message_id] != message)):
            return None, "conflicting_message_or_conversation"
        messages[message_id] = message
        if message.get("author", {}).get("role") == "assistant":
            assistants.append((index, message))
    if len(assistants) != 1:
        return None, "assistant_cardinality"
    assistant_index, assistant = assistants[0]
    if (not text_message(assistant, "assistant")
            or assistant["content"]["parts"][0] != ""
            or assistant_index <= input_index or assistant_index >= complete_index
            or not ancestry_reaches_user(assistant, user, messages)):
        return None, "assistant_ancestry_or_initial_content"

    markers = [(index, event) for index, event in enumerate(events)
               if event.get("type") == "message_marker"]
    required = {"user_visible_token", "final_channel_token", "last_token"}
    observed = {event.get("marker") for _, event in markers}
    if (not required.issubset(observed)
            or any(event.get("conversation_id") != conversation
                   or event.get("message_id") != assistant["id"]
                   for _, event in markers)
            or not all(assistant_index < index < complete_index for index, _ in markers)):
        return None, "assistant_markers"

    response = ""
    explicit_append = False
    finished = end_turn = False
    patch_indices = []
    for index in range(assistant_index + 1, complete_index):
        event = events[index]
        if event.get("p") == CONTENT_PATH and event.get("o") == "append":
            value = event.get("v")
            if not isinstance(value, str):
                return None, "invalid_explicit_content_patch"
            response += value
            explicit_append = True
            patch_indices.append(index)
        elif set(event) == {"v"} and isinstance(event["v"], str):
            if not explicit_append:
                return None, "unbound_implicit_content_patch"
            response += event["v"]
            patch_indices.append(index)
        elif event.get("o") == "patch" and isinstance(event.get("v"), list):
            explicit_append = False
            for patch in event["v"]:
                if not isinstance(patch, dict):
                    return None, "invalid_patch_batch"
                path, operation, value = patch.get("p"), patch.get("o"), patch.get("v")
                if path == CONTENT_PATH and operation == "append" and isinstance(value, str):
                    response += value
                    patch_indices.append(index)
                elif path == "/message/status" and operation == "replace":
                    finished = value == "finished_successfully"
                elif path == "/message/end_turn" and operation == "replace":
                    end_turn = value is True
                elif path in ("/message/metadata",) and operation == "append":
                    continue
                else:
                    return None, "unsupported_patch"
        elif event.get("type") == "message_marker":
            explicit_append = False
        elif (isinstance(event.get("p"), str)
              and event["p"].startswith("/message/metadata/")
              and event.get("o") in ("replace", "add", "append")):
            explicit_append = False
        elif any(key in event for key in ("p", "o")):
            return None, "unsupported_stream_operation"
    if (not response or not patch_indices or not finished or not end_turn
            or not any(event.get("marker") == "last_token" and index > max(patch_indices)
                       for index, event in markers)):
        return None, "incomplete_assistant_turn"
    if any(event.get("conversation_id") not in (None, conversation)
           for event in events[input_index:complete_index + 1]):
        return None, "conflicting_conversation_id"
    return {
        "conversation_id": conversation,
        "user_message_id": user["id"],
        "assistant_message_id": assistant["id"],
        "prompt": user["content"]["parts"][0],
        "response": response,
        "user_create_time": user.get("create_time"),
        "assistant_create_time": assistant.get("create_time"),
        "ancestry_message_ids": list(messages),
        "stream_sha256": segment["stream_sha256"],
        "stream_byte_length": segment["byte_length"],
        "stream_start_virtual": segment["start_virtual"],
        "stream_end_virtual": segment["end_virtual"],
        "stream_source_spans": segment["source_spans"],
        "event_record_sha256": [records[index]["record_sha256"] for index in indices],
        "response_patch_event_indices": [indices[index] for index in patch_indices],
        "completed": True,
    }, None


def join(parsed):
    if parsed.get("ground_truth_supplied") is not False:
        raise ValueError("SSE parser input must not contain ground truth")
    records = parsed.get("records")
    segments = parsed.get("contiguous_segments")
    if not isinstance(records, list) or not isinstance(segments, list):
        raise ValueError("Complete SSE event records and verified segments required")
    candidates = []
    rejected = []
    for segment in segments:
        candidate, reason = reconstruct_segment(segment, records)
        if candidate is None:
            rejected.append({"stream_sha256": segment["stream_sha256"], "reason": reason})
        else:
            candidates.append(candidate)
    by_identity = {}
    ambiguous = []
    for candidate in candidates:
        key = (candidate["conversation_id"], candidate["user_message_id"],
               candidate["assistant_message_id"])
        if key in by_identity:
            previous = by_identity[key]
            if (previous["prompt"], previous["response"]) != (candidate["prompt"], candidate["response"]):
                ambiguous.append(key)
            else:
                previous.setdefault("duplicate_stream_sha256", []).append(candidate["stream_sha256"])
        else:
            by_identity[key] = candidate
    for key in ambiguous:
        by_identity.pop(key, None)
    return {"method": "development signed-in SSE ancestry and patch join",
            "ground_truth_supplied": False,
            "input_process_name": parsed.get("process_name"), "input_pid": parsed.get("pid"),
            "scanned_segments": len(segments), "rejected_segments": rejected,
            "ambiguous_identity_count": len(set(ambiguous)),
            "candidate_count": len(by_identity),
            "candidate_turns": list(by_identity.values())}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--parsed", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Unfiltered signed-in turns must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    parsed = json.loads(args.parsed.read_text(encoding="utf-8-sig"))
    result = join(parsed)
    result["parsed_sha256"] = hashlib.sha256(args.parsed.read_bytes()).hexdigest()
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, ensure_ascii=True)
        target.write("\n")
    print(json.dumps({"candidate_count": result["candidate_count"],
                      "scanned_segments": result["scanned_segments"],
                      "rejected_reasons": [entry["reason"] for entry in result["rejected_segments"]]}))


if __name__ == "__main__":
    main()
