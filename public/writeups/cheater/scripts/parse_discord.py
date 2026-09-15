#!/usr/bin/env python3
"""Reconstruct Discord evidence from a dumped Chromium renderer.

The parser deliberately starts without a channel ID, username, message text, or
known offset.  It validates complete Discord Gateway ETF dispatches, correlates
the recovered DM channel with Discord's cached selected-channel state, and then
extracts DraftStore revisions for that same channel.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import mmap
import struct
from pathlib import Path
from typing import Any, Iterator


DISCORD_EPOCH_MS = 1_420_070_400_000
MAX_TERM_BYTES = 8 * 1024 * 1024
MAX_COLLECTION_ITEMS = 100_000
MAX_DEPTH = 64


class ETFError(Exception):
    """A candidate is not a complete, supported ETF term."""


class ETFReader:
    def __init__(self, data: mmap.mmap, pos: int, limit: int):
        self.data = data
        self.pos = pos
        self.limit = min(limit, len(data))

    def take(self, size: int) -> bytes:
        if size < 0 or self.pos + size > self.limit:
            raise ETFError("term runs outside the candidate bounds")
        value = self.data[self.pos : self.pos + size]
        self.pos += size
        return value

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return struct.unpack(">H", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack(">I", self.take(4))[0]

    def checked_count(self, count: int) -> int:
        if count > MAX_COLLECTION_ITEMS:
            raise ETFError(f"unreasonable collection length: {count}")
        return count

    def atom(self, size: int) -> Any:
        value = self.take(size).decode("utf-8", errors="strict")
        return {"true": True, "false": False, "nil": None}.get(value, value)

    def binary(self, size: int) -> Any:
        value = self.take(size)
        try:
            return value.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return {"$binary_hex": value.hex()}

    @staticmethod
    def map_key(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool, bytes, type(None))):
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def term(self, depth: int = 0) -> Any:
        if depth > MAX_DEPTH:
            raise ETFError("maximum ETF nesting depth exceeded")

        tag = self.u8()

        if tag == 70:  # NEW_FLOAT_EXT
            return struct.unpack(">d", self.take(8))[0]
        if tag == 97:  # SMALL_INTEGER_EXT
            return self.u8()
        if tag == 98:  # INTEGER_EXT
            return struct.unpack(">i", self.take(4))[0]
        if tag == 99:  # FLOAT_EXT (legacy, 31-byte string)
            raw = self.take(31).split(b"\x00", 1)[0]
            try:
                return float(raw.decode("ascii"))
            except ValueError as exc:
                raise ETFError("invalid FLOAT_EXT") from exc
        if tag in (100, 118):  # ATOM_EXT / ATOM_UTF8_EXT
            return self.atom(self.u16())
        if tag in (115, 119):  # SMALL_ATOM_EXT / SMALL_ATOM_UTF8_EXT
            return self.atom(self.u8())
        if tag == 104:  # SMALL_TUPLE_EXT
            return [self.term(depth + 1) for _ in range(self.checked_count(self.u8()))]
        if tag == 105:  # LARGE_TUPLE_EXT
            return [self.term(depth + 1) for _ in range(self.checked_count(self.u32()))]
        if tag == 106:  # NIL_EXT
            return []
        if tag == 107:  # STRING_EXT
            return self.take(self.u16()).decode("latin-1")
        if tag == 108:  # LIST_EXT
            count = self.checked_count(self.u32())
            values = [self.term(depth + 1) for _ in range(count)]
            tail = self.term(depth + 1)
            if tail != []:
                return {"items": values, "tail": tail}
            return values
        if tag == 109:  # BINARY_EXT
            return self.binary(self.u32())
        if tag == 77:  # BIT_BINARY_EXT
            size = self.u32()
            significant_bits = self.u8()
            value = self.binary(size)
            return {"bits_in_last_byte": significant_bits, "value": value}
        if tag in (110, 111):  # SMALL_BIG_EXT / LARGE_BIG_EXT
            size = self.u8() if tag == 110 else self.checked_count(self.u32())
            sign = self.u8()
            magnitude = int.from_bytes(self.take(size), "little")
            return -magnitude if sign else magnitude
        if tag == 116:  # MAP_EXT
            count = self.checked_count(self.u32())
            result = {}
            for _ in range(count):
                key = self.map_key(self.term(depth + 1))
                result[key] = self.term(depth + 1)
            return result

        raise ETFError(f"unsupported ETF tag {tag}")


def scan_gateway_events(data: mmap.mmap) -> list[dict[str, Any]]:
    """Find and validate uncompressed ETF maps beginning with version 131."""
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor = 0

    while True:
        offset = data.find(b"\x83\x74", cursor)
        if offset == -1:
            break
        cursor = offset + 1
        reader = ETFReader(data, offset + 1, offset + MAX_TERM_BYTES)

        try:
            event = reader.term()
        except (ETFError, UnicodeDecodeError, struct.error):
            continue

        if not (
            isinstance(event, dict)
            and event.get("op") == 0
            and isinstance(event.get("t"), str)
            and "d" in event
            and "s" in event
        ):
            continue

        fingerprint = json.dumps(event, ensure_ascii=False, sort_keys=True)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        events.append(
            {
                "offset": offset,
                "end_offset": reader.pos,
                "event": event,
            }
        )

    return events


def bounded_json_object(data: mmap.mmap, start: int, maximum: int = 1024 * 1024) -> tuple[Any, int]:
    """Return one balanced UTF-8 JSON object and its exclusive end offset."""
    if start < 0 or start >= len(data) or data[start] != ord("{"):
        raise ValueError("JSON object does not start with an opening brace")

    depth = 0
    in_string = False
    escaped = False
    end_limit = min(len(data), start + maximum)

    for pos in range(start, end_limit):
        byte = data[pos]
        if in_string:
            if escaped:
                escaped = False
            elif byte == ord("\\"):
                escaped = True
            elif byte == ord('"'):
                in_string = False
            continue

        if byte == ord('"'):
            in_string = True
        elif byte == ord("{"):
            depth += 1
        elif byte == ord("}"):
            depth -= 1
            if depth == 0:
                raw = data[start : pos + 1]
                return json.loads(raw.decode("utf-8")), pos + 1

    raise ValueError("unterminated JSON object")


def scan_selected_channels(data: mmap.mmap) -> list[dict[str, Any]]:
    marker = b'{"selectedChannelId"'
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor = 0

    while True:
        json_offset = data.find(marker, cursor)
        if json_offset == -1:
            break
        cursor = json_offset + 1

        if json_offset < 8:
            continue
        length, flag = struct.unpack("<II", data[json_offset - 8 : json_offset])
        if flag != 1 or length < len(marker) or length > 1024 * 1024:
            continue

        try:
            raw = data[json_offset : json_offset + length]
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or "selectedChannelId" not in value:
            continue

        fingerprint = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        records.append(
            {
                "record_offset": json_offset - 8,
                "json_offset": json_offset,
                "length": length,
                "string_flag": flag,
                "value": value,
            }
        )

    return records


def walk_draft_state(value: Any, path: tuple[str, ...] = ()) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get("timestamp"), int) and isinstance(value.get("draft"), str):
            yield {
                "path": list(path),
                "timestamp_ms": value["timestamp"],
                "draft": value["draft"],
            }
        for key, child in value.items():
            yield from walk_draft_state(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_draft_state(child, path + (str(index),))


def scan_draft_store(data: mmap.mmap) -> list[dict[str, Any]]:
    marker = b"DraftStore"
    drafts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int, str]] = set()
    cursor = 0

    while True:
        anchor = data.find(marker, cursor)
        if anchor == -1:
            break
        cursor = anchor + 1
        json_offset = data.find(b"{", anchor + len(marker), anchor + len(marker) + 32)
        if json_offset == -1:
            continue

        try:
            value, _ = bounded_json_object(data, json_offset)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or not isinstance(value.get("_state"), dict):
            continue

        for leaf in walk_draft_state(value["_state"]):
            path = leaf.pop("path")
            if len(path) < 2:
                continue
            user_id, channel_id = path[0], path[1]
            key = (user_id, channel_id, leaf["timestamp_ms"], leaf["draft"])
            if key in seen:
                continue
            seen.add(key)
            drafts.append(
                {
                    "record_offset": anchor,
                    "json_offset": json_offset,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    **leaf,
                }
            )

    drafts.sort(key=lambda item: (item["timestamp_ms"], item["record_offset"]))
    return drafts


def iso_from_ms(timestamp_ms: int) -> str:
    value = dt.datetime.fromtimestamp(timestamp_ms / 1000, tz=dt.timezone.utc)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def snowflake_ms(value: str | int) -> int:
    return (int(value) >> 22) + DISCORD_EPOCH_MS


def event_id(entry: dict[str, Any]) -> str | None:
    payload = entry["event"].get("d")
    if isinstance(payload, dict) and payload.get("id") is not None:
        return str(payload["id"])
    return None


def choose_dm_channel(
    events: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    drafts: list[dict[str, Any]],
) -> dict[str, Any]:
    messages_per_channel: collections.Counter[str] = collections.Counter()
    for entry in events:
        event = entry["event"]
        payload = event.get("d")
        if event.get("t") == "MESSAGE_CREATE" and isinstance(payload, dict):
            if payload.get("channel_id") is not None:
                messages_per_channel[str(payload["channel_id"])] += 1

    selected_ids = {
        str(record["value"].get("selectedChannelId"))
        for record in selected
        if record["value"].get("selectedChannelId") is not None
    }
    draft_counts: collections.Counter[str] = collections.Counter(
        draft["channel_id"] for draft in drafts
    )

    candidates = []
    for entry in events:
        event = entry["event"]
        payload = event.get("d")
        if event.get("t") != "CHANNEL_CREATE" or not isinstance(payload, dict):
            continue
        if payload.get("type") != 1 or payload.get("id") is None:
            continue
        channel_id = str(payload["id"])
        candidates.append(
            {
                "entry": entry,
                "channel_id": channel_id,
                "message_count": messages_per_channel[channel_id],
                "selected": channel_id in selected_ids,
                "draft_count": draft_counts[channel_id],
            }
        )

    if not candidates:
        raise RuntimeError("no validated type-1 CHANNEL_CREATE dispatch was recovered")

    corroborated = [
        candidate
        for candidate in candidates
        if candidate["message_count"] > 0
        and candidate["selected"]
        and candidate["draft_count"] > 0
    ]
    if len(corroborated) != 1:
        details = ", ".join(
            f"{candidate['channel_id']} "
            f"(messages={candidate['message_count']}, selected={candidate['selected']}, "
            f"drafts={candidate['draft_count']})"
            for candidate in candidates
        )
        raise RuntimeError(f"expected one fully corroborated DM channel; recovered: {details}")
    return corroborated[0]["entry"]


def compact_channel(payload: dict[str, Any]) -> dict[str, Any]:
    recipients = []
    for recipient in payload.get("recipients", []):
        if isinstance(recipient, dict):
            recipients.append(
                {
                    key: recipient.get(key)
                    for key in ("id", "username", "global_name")
                    if recipient.get(key) is not None
                }
            )
    return {"id": str(payload["id"]), "type": payload.get("type"), "recipients": recipients}


def compact_message(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry["event"]["d"]
    author = payload.get("author") if isinstance(payload.get("author"), dict) else {}
    identifier = str(payload["id"])
    derived_ms = snowflake_ms(identifier)
    supplied = str(payload.get("timestamp", ""))
    supplied_ms = int(dt.datetime.fromisoformat(supplied.replace("Z", "+00:00")).timestamp() * 1000)
    return {
        "event_offset": f"0x{entry['offset']:x}",
        "id": identifier,
        "channel_id": str(payload.get("channel_id")),
        "timestamp": supplied,
        "snowflake_timestamp": iso_from_ms(derived_ms),
        "snowflake_delta_ms": derived_ms - supplied_ms,
        "author": {
            key: author.get(key)
            for key in ("id", "username", "global_name")
            if author.get(key) is not None
        },
        "content": payload.get("content"),
    }


def final_draft_before(
    drafts: list[dict[str, Any]], timestamp_ms: int, user_id: str
) -> dict[str, Any] | None:
    candidates = [
        draft
        for draft in drafts
        if draft["user_id"] == user_id and draft["timestamp_ms"] <= timestamp_ms
    ]
    if not candidates:
        return None
    candidate = max(candidates, key=lambda item: item["timestamp_ms"])
    if timestamp_ms - candidate["timestamp_ms"] > 60_000:
        return None
    return candidate


def build_report(path: Path, data: mmap.mmap) -> dict[str, Any]:
    events = scan_gateway_events(data)
    selected = scan_selected_channels(data)
    drafts = scan_draft_store(data)
    channel_entry = choose_dm_channel(events, selected, drafts)
    channel = compact_channel(channel_entry["event"]["d"])
    channel_id = channel["id"]

    channel_messages = [
        compact_message(entry)
        for entry in events
        if entry["event"].get("t") == "MESSAGE_CREATE"
        and isinstance(entry["event"].get("d"), dict)
        and str(entry["event"]["d"].get("channel_id")) == channel_id
    ]
    channel_messages.sort(key=lambda item: item["timestamp"])

    selected_matches = [
        record for record in selected if str(record["value"].get("selectedChannelId")) == channel_id
    ]
    relevant_drafts = [draft for draft in drafts if draft["channel_id"] == channel_id]

    draft_user_counts = collections.Counter(draft["user_id"] for draft in relevant_drafts)
    message_author_ids = {str(item["author"].get("id")) for item in channel_messages}
    local_user_id = next(
        (user_id for user_id, _ in draft_user_counts.most_common() if user_id in message_author_ids),
        None,
    )

    message_comparisons = []
    for message in channel_messages:
        if local_user_id is None or str(message["author"].get("id")) != local_user_id:
            continue
        message_ms = int(
            dt.datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00")).timestamp() * 1000
        )
        draft = final_draft_before(relevant_drafts, message_ms, local_user_id)
        if draft is None:
            continue
        draft_words = draft["draft"].split()
        sent_words = str(message["content"]).split()
        removed = [word for word in draft_words if word not in sent_words]
        message_comparisons.append(
            {
                "message_id": message["id"],
                "final_draft": draft["draft"],
                "sent_content": message["content"],
                "removed_words": removed,
                "draft_to_send_ms": message_ms - draft["timestamp_ms"],
            }
        )

    event_counts = collections.Counter(entry["event"]["t"] for entry in events)
    recipient_ids = [str(item["id"]) for item in channel["recipients"] if item.get("id")]

    return {
        "report": "Cheater Discord renderer reconstruction",
        "source": {"file": path.name, "size_bytes": path.stat().st_size},
        "method": {
            "gateway": "complete ETF terms beginning with VERSION_MAGIC + MAP_EXT",
            "selected_channel": "complete little-endian length-prefixed JSON records",
            "drafts": "complete DraftStore JSON states",
            "deduplication": "identical decoded Gateway events and identical draft revisions",
        },
        "gateway": {
            "validated_dispatch_count": len(events),
            "event_type_counts": dict(sorted(event_counts.items())),
            "dm_channel": {
                "event_offset": f"0x{channel_entry['offset']:x}",
                **channel,
            },
            "messages": channel_messages,
        },
        "client_state": {
            "selected_channel_records": [
                {
                    "record_offset": f"0x{record['record_offset']:x}",
                    "json_offset": f"0x{record['json_offset']:x}",
                    "length": record["length"],
                    "string_flag": record["string_flag"],
                    "value": record["value"],
                }
                for record in selected_matches
            ],
            "draft_revisions": [
                {
                    "record_offset": f"0x{draft['record_offset']:x}",
                    "user_id": draft["user_id"],
                    "channel_id": draft["channel_id"],
                    "timestamp": iso_from_ms(draft["timestamp_ms"]),
                    "timestamp_ms": draft["timestamp_ms"],
                    "draft": draft["draft"],
                }
                for draft in relevant_drafts
            ],
        },
        "correlation": {
            "channel_id": channel_id,
            "local_user_id": local_user_id,
            "recipient_ids": recipient_ids,
            "message_count": len(channel_messages),
            "all_messages_match_channel": all(
                message["channel_id"] == channel_id for message in channel_messages
            ),
            "all_snowflake_checks_zero_delta": all(
                message["snowflake_delta_ms"] == 0 for message in channel_messages
            ),
            "draft_to_sent": message_comparisons,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("renderer", type=Path, help="renderer dump, for example pid.4080.dmp")
    parser.add_argument("-o", "--output", type=Path, help="write the JSON report here")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.renderer.open("rb") as stream:
        data = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            report = build_report(args.renderer, data)
        finally:
            data.close()

    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    print(
        f"Recovered {report['gateway']['validated_dispatch_count']} Gateway dispatches, "
        f"{report['correlation']['message_count']} messages, and "
        f"{len(report['client_state']['draft_revisions'])} draft revisions "
        f"for channel {report['correlation']['channel_id']}."
    )


if __name__ == "__main__":
    main()
