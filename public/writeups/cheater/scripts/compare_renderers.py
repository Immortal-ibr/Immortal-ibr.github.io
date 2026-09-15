#!/usr/bin/env python3
"""Compare raw Chrome renderer dumps without searching for the prompt or answer."""

import argparse
import json
import mmap
import re
import struct
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID


COMPOSER_KEY = b"oai/apps/lightweight-web/composerDraft/v1"
TERMINAL = b'data-conversation-control="terminal-received"'
RESUME = b'data-conversation-control="resume-token"'
STARTED = b'data-conversation-control="assistant-content-started"'
STREAM = b'data-assistant-stream-block=""'
NOAUTH_ROUTE = b"chatgpt.com/unauth-mweb/conversation?lightweight_authenticated=0"
SUBMISSION_OWNER = b"conversationRetryOwner="

UUID_TEXT = rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
PENDING_FOR = re.compile(
    rb'for="assistant-pending-(' + UUID_TEXT + rb')-(committed-tail|pending)"'
)
TURN_STATE = re.compile(
    rb'\x22\x12conversationTurnId\x22\x24(' + UUID_TEXT +
    rb')\x22\x04kind\x22\x1cweb-mobile-conversation-turn'
    rb'\x22\x09streaming([FT])'
)


class FirstStartTag(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.name = None
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        if self.name is None:
            self.name = tag
            self.attrs = dict(attrs)


def offsets(data, needle):
    at = 0
    while (at := data.find(needle, at)) != -1:
        yield at
        at += 1


def canonical_uuid(value):
    try:
        parsed = str(UUID(value))
    except (ValueError, AttributeError):
        return None
    return parsed if parsed == value.lower() else None


def parse_start_tag(data, anchor, name, look_back=512, look_ahead=2048):
    start = data.rfind(b"<" + name.encode(), max(0, anchor - look_back), anchor + 1)
    end = data.find(b">", anchor, min(len(data), anchor + look_ahead))
    if start == -1 or end == -1:
        return None

    parser = FirstStartTag()
    try:
        parser.feed(data[start : end + 1].decode("latin-1"))
    except Exception:
        return None
    if parser.name != name:
        return None
    return start, end + 1, parser.attrs


def decode_storage_array(data, start):
    if start < 0 or start + 9 > len(data) or start % 8:
        return None
    num_bytes, num_elements = struct.unpack_from("<II", data, start)
    if num_elements < 1 or num_bytes != 8 + num_elements:
        return None
    end = start + num_bytes
    if end > len(data):
        return None

    payload = data[start + 8 : end]
    marker, raw = payload[0], payload[1:]
    try:
        if marker == 1:
            return raw.decode("latin-1"), start + 9
        if marker == 0 and len(raw) % 2 == 0:
            return raw.decode("utf-16le"), start + 9
    except UnicodeDecodeError:
        pass
    return None


def composer_pairs(data):
    hits = list(offsets(data, COMPOSER_KEY))
    pairs = []

    for hit in hits:
        key_array = hit - 9  # 8-byte array header + 1-byte encoding marker
        decoded_key = decode_storage_array(data, key_array)
        if not decoded_key or decoded_key[0].encode("latin-1") != COMPOSER_KEY:
            continue

        first_slot = max(8, key_array - 0x80)
        first_slot += (-first_slot) % 8
        for key_slot in range(first_slot, key_array, 8):
            key_relative = struct.unpack_from("<Q", data, key_slot)[0]
            if key_slot + key_relative != key_array:
                continue

            record = key_slot - 8
            num_bytes, version = struct.unpack_from("<II", data, record)
            if version != 0 or num_bytes < 0x18 or num_bytes % 8:
                continue
            if record + num_bytes != key_array:
                continue

            value_slot = key_slot + 8
            value_relative = struct.unpack_from("<Q", data, value_slot)[0]
            value_array = value_slot + value_relative
            decoded_value = decode_storage_array(data, value_array)
            if not decoded_value:
                continue

            value, value_offset = decoded_value
            pairs.append(
                {
                    "record_offset": hex(record),
                    "key_offset": hex(hit),
                    "value_offset": hex(value_offset),
                    "value_characters": len(value),
                    "value": value,
                }
            )
            break

    return hits, pairs


def printable_allocation(data, anchor, maximum=0x10000):
    """Bound one printable ASCII run around an anchor in raw memory."""
    start = anchor
    floor = max(0, anchor - maximum)
    while start > floor and 0x20 <= data[start - 1] <= 0x7E:
        start -= 1

    end = anchor
    ceiling = min(len(data), anchor + maximum)
    while end < ceiling and 0x20 <= data[end] <= 0x7E:
        end += 1
    return start, end


def submission_records(data):
    """Decode form fragments containing complete owner and message-ID fields."""
    grouped = {}

    for anchor in offsets(data, SUBMISSION_OWNER):
        start, end = printable_allocation(data, anchor)
        try:
            fields = parse_qs(
                data[start:end].decode("ascii"),
                keep_blank_values=True,
                strict_parsing=False,
            )
            owner_text = fields["conversationRetryOwner"][-1]
            assistant_text = fields["assistantMessageId"][-1]
            user_text = fields["userMessageId"][-1]
            owner = json.loads(owner_text)
        except (UnicodeDecodeError, KeyError, IndexError, json.JSONDecodeError):
            continue

        if not assistant_text.startswith("pending-"):
            continue
        pending_id = canonical_uuid(assistant_text.removeprefix("pending-"))
        user_message_id = canonical_uuid(user_text)
        if pending_id is None or user_message_id is None or not isinstance(owner, dict):
            continue
        if owner.get("mode") != "anonymous" or owner.get("sessionEpoch") is not None:
            continue

        key = (pending_id, user_message_id, json.dumps(owner, sort_keys=True))
        record = grouped.setdefault(
            key,
            {
                "allocation_offset": hex(start),
                "allocation_end": hex(end),
                "owner_field_offset": hex(anchor),
                "owner": owner,
                "pending_assistant_id": pending_id,
                "user_message_id": user_message_id,
                "copy_offsets": [],
            },
        )
        record["copy_offsets"].append(hex(anchor))

    return list(grouped.values())


def history_url_arrays(data, conversation_id):
    """Validate exact /uc/ URLs as length-delimited Mojo arrays."""
    if conversation_id is None:
        return []

    encoded = f"https://chatgpt.com/uc/{conversation_id}".encode("ascii")
    records = []
    for url_offset in offsets(data, encoded):
        header = url_offset - 8
        if header < 0 or header % 8:
            continue
        num_bytes, num_elements = struct.unpack_from("<II", data, header)
        if num_bytes != 8 + len(encoded) or num_elements != len(encoded):
            continue
        records.append(
            {
                "array_header_offset": hex(header),
                "url_offset": hex(url_offset),
                "conversation_id_offset": hex(url_offset + encoded.index(conversation_id.encode("ascii"))),
                "num_bytes": num_bytes,
                "num_elements": num_elements,
                "url": encoded.decode("ascii"),
            }
        )
    return records


def conversation_turn_states(data):
    """Parse serialized navigation-state records keyed by user message UUID."""
    grouped = {}
    for match in TURN_STATE.finditer(data):
        conversation_turn_id = canonical_uuid(match.group(1).decode("ascii"))
        if conversation_turn_id is None:
            continue
        state = "true" if match.group(2) == b"T" else "false"
        record = grouped.setdefault(
            conversation_turn_id,
            {
                "conversation_turn_id": conversation_turn_id,
                "kind": "web-mobile-conversation-turn",
                "streaming_true_offsets": [],
                "streaming_false_offsets": [],
            },
        )
        record[f"streaming_{state}_offsets"].append(hex(match.start()))
    return list(grouped.values())


def storage_page_links(url_arrays, pairs):
    """Keep only pages containing both the pivot URL and a valid composer pair."""
    links = []
    for url_record in url_arrays:
        page = int(url_record["array_header_offset"], 16) & ~0xFFF
        page_pairs = [
            pair
            for pair in pairs
            if page <= int(pair["record_offset"], 16) < page + 0x1000
        ]
        if page_pairs:
            links.append(
                {
                    "page": hex(page),
                    "url_array_header": url_record["array_header_offset"],
                    "composer_records": page_pairs,
                }
            )
    return links


def controls(data, needle, kind, required):
    parsed = []
    for anchor in offsets(data, needle):
        tag = parse_start_tag(data, anchor, "span")
        if not tag:
            continue
        start, end, attrs = tag
        if attrs.get("data-conversation-control") != kind:
            continue

        values = {}
        valid = True
        for attr in required:
            value = canonical_uuid(attrs.get(attr))
            if value is None:
                valid = False
                break
            values[attr.removeprefix("data-").replace("-", "_")] = value
        if valid:
            values.update({"anchor": anchor, "tag_start": start, "tag_end": end})
            parsed.append(values)
    return parsed


def stream_blocks(data):
    blocks = []
    for attr_offset in offsets(data, STREAM):
        tag = parse_start_tag(data, attr_offset, "p", 256, 1024)
        if not tag:
            continue
        start, open_end, attrs = tag
        try:
            index = int(attrs["data-assistant-stream-block-index"])
        except (KeyError, ValueError):
            continue

        close = data.find(b"</p>", open_end, min(len(data), open_end + 4096))
        if close == -1:
            continue
        body = data[open_end:close].split(b"<", 1)[0]
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            continue

        # The allocation boundary can cut off the beginning of <template>, so
        # use the last complete `for=` attribute before the paragraph.
        context_start = max(0, start - 2048)
        matches = list(PENDING_FOR.finditer(data[context_start:start]))
        if not matches:
            continue
        match = matches[-1]

        pending_id = canonical_uuid(match.group(1).decode("ascii"))
        state = match.group(2).decode("ascii")
        blocks.append(
            {
                "anchor": attr_offset,
                "end": close + 4,
                "block_index": index,
                "text": text,
                "pending_id": pending_id,
                "committed": state == "committed-tail",
            }
        )
    return blocks


def pending_target_after(data, control):
    end = min(len(data), control["tag_end"] + 4096)
    match = PENDING_FOR.search(data[control["tag_end"] : end])
    if not match or match.group(2) != b"pending":
        return None
    return canonical_uuid(match.group(1).decode("ascii"))


def linked_turns(data, terminals, blocks, resumes, started):
    turns = []
    for block in (item for item in blocks if item["committed"]):
        nearby_resumes = [r for r in resumes if 0 < r["anchor"] - block["end"] < 0x8000]
        for resume in nearby_resumes:
            nearby_started = [
                s for s in started if 0 < s["anchor"] - resume["anchor"] < 0x8000
            ]
            for began in nearby_started:
                if pending_target_after(data, began) != block["pending_id"]:
                    continue
                for terminal in terminals:
                    if not (0 < block["anchor"] - terminal["anchor"] < 0x10000):
                        continue
                    if not (
                        terminal["conversation_id"] == resume["conversation_id"]
                        and terminal["operation_id"] == resume["operation_id"]
                        and terminal["operation_id"] == began["operation_id"]
                        and terminal["message_id"] == began["message_id"]
                    ):
                        continue
                    turns.append(
                        {
                            "terminal_control": hex(terminal["anchor"]),
                            "committed_stream_block": hex(block["anchor"]),
                            "conversation_id": terminal["conversation_id"],
                            "pending_assistant_id": block["pending_id"],
                            "final_assistant_id": terminal["message_id"],
                            "operation_id": terminal["operation_id"],
                            "response_text": block["text"],
                        }
                    )
    return turns


def attach_submissions(turns, submissions):
    for turn in turns:
        matches = [
            record
            for record in submissions
            if record["pending_assistant_id"] == turn["pending_assistant_id"]
        ]
        if len(matches) == 1:
            turn["submission"] = matches[0]


def attach_turn_states(submissions, states):
    by_id = {state["conversation_turn_id"]: state for state in states}
    for submission in submissions:
        state = by_id.get(submission["user_message_id"])
        if state is not None:
            submission["navigation_state"] = state


def inspect_dump(pid, path, conversation_id=None):
    with path.open("rb") as stream, mmap.mmap(
        stream.fileno(), 0, access=mmap.ACCESS_READ
    ) as data:
        key_hits, pairs = composer_pairs(data)
        terminals = controls(
            data,
            TERMINAL,
            "terminal-received",
            ("data-conversation-id", "data-message-id", "data-operation-id"),
        )
        resumes = controls(
            data, RESUME, "resume-token", ("data-conversation-id", "data-operation-id")
        )
        started = controls(
            data, STARTED, "assistant-content-started", ("data-message-id", "data-operation-id")
        )
        blocks = stream_blocks(data)
        turns = linked_turns(data, terminals, blocks, resumes, started)
        submissions = submission_records(data)
        turn_states = conversation_turn_states(data)
        attach_turn_states(submissions, turn_states)
        attach_submissions(turns, submissions)
        url_arrays = history_url_arrays(data, conversation_id)
        page_links = storage_page_links(url_arrays, pairs)

        route_offsets = []
        for at in offsets(data, NOAUTH_ROUTE):
            route = urlsplit("https://" + NOAUTH_ROUTE.decode("ascii"))
            if (
                route.hostname == "chatgpt.com"
                and route.path == "/unauth-mweb/conversation"
                and parse_qs(route.query) == {"lightweight_authenticated": ["0"]}
            ):
                route_offsets.append(hex(at))

    matching_turns = [
        turn
        for turn in turns
        if conversation_id is None or turn["conversation_id"] == conversation_id
    ]

    return {
        "pid": pid,
        "history_pivot": {
            "conversation_id": conversation_id,
            "validated_url_arrays": url_arrays,
            "storage_page_links": page_links,
            "matching_completed_turn_count": len(matching_turns),
        },
        "composer_key_candidates": {
            "count": len(key_hits),
            "offsets": [hex(item) for item in key_hits],
        },
        "valid_mojo_composer_pairs": pairs,
        "terminal_controls": [
            {
                "anchor_offset": hex(item["anchor"]),
                "conversation_id": item["conversation_id"],
                "message_id": item["message_id"],
                "operation_id": item["operation_id"],
            }
            for item in terminals
        ],
        "assistant_stream_blocks": [
            {
                "anchor_offset": hex(item["anchor"]),
                "text_characters": len(item["text"]),
                "committed": item["committed"],
                "pending_assistant_id": item["pending_id"],
                "text": item["text"],
            }
            for item in blocks
        ],
        "submission_records": submissions,
        "conversation_turn_states": turn_states,
        "valid_noauth_route_literals": route_offsets,
        "linked_completed_turns": turns,
        "complete_turn": bool(matching_turns),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--conversation-id",
        help="conversation UUID recovered from Chrome History",
    )
    parser.add_argument("dump", nargs="+", metavar="PID=PATH")
    args = parser.parse_args()

    conversation_id = None
    if args.conversation_id is not None:
        conversation_id = canonical_uuid(args.conversation_id)
        if conversation_id is None:
            parser.error("--conversation-id must be a canonical UUID")

    renderers = []
    for item in args.dump:
        pid_text, separator, path_text = item.partition("=")
        if not separator:
            parser.error(f"expected PID=PATH, got {item!r}")
        renderers.append(
            inspect_dump(int(pid_text), Path(path_text), conversation_id)
        )

    completed = [r["pid"] for r in renderers if r["complete_turn"]]
    report = {
        "report": "Cheater Chrome renderer comparison",
        "source": "Volatility windows.memmap --dump output",
        "method": {
            "history_pivot": "Validate the supplied History conversation UUID in exact /uc/ URL arrays and typed terminal controls.",
            "response_join": "Join terminal, committed stream, resume-token, and assistant-content-started records by their named UUID fields.",
            "submission_join": "Match the committed stream's pending assistant UUID to assistantMessageId in a decoded form allocation.",
            "prompt_join": "Require the validated /uc/ URL array and a valid Mojo composer KeyValue record to occupy the same 4 KiB storage page.",
        },
        "history_conversation_id": conversation_id,
        "renderers": renderers,
        "selected_pid": completed[0] if len(completed) == 1 else None,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
