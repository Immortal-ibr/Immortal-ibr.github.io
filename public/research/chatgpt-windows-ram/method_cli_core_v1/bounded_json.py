"""Bounded stream-item framing for the clean-VM follow-up (development only).

Does not receive ground-truth values. Does not reconstruct a V8 object graph or
claim a recovered conversation. UTF-8/UTF-16LE complete JSON envelopes are scanned
through resident, virtually adjacent pages. Raw hashes cover exact source bytes.
"""

import argparse
import bisect
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

USER_LIMIT = 1 << 47
DEFAULT_CAP = 1024 * 1024
SIGNATURE_TEXT = '{"type":"stream-item"'
ENCODINGS = ("utf-8", "utf-16-le")


@dataclass(frozen=True)
class Row:
    virtual: int
    physical: int
    size: int


def integer(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a mapping address")
    return int(value, 0) if isinstance(value, str) else int(value)


def normalize_rows(values, image_size):
    rows = []
    skipped_kernel = 0
    for value in values:
        row = Row(*(integer(value[key]) for key in ("Virtual", "Physical", "Size")))
        if row.virtual >= USER_LIMIT:
            skipped_kernel += 1
            continue
        if (row.virtual < 0 or row.physical < 0 or row.size <= 0
                or row.virtual + row.size > USER_LIMIT
                or row.physical + row.size > image_size):
            raise ValueError(f"Invalid resident user mapping: {row}")
        rows.append(row)
    rows.sort(key=lambda row: row.virtual)
    for previous, current in zip(rows, rows[1:]):
        if current.virtual < previous.virtual + previous.size:
            raise ValueError("Overlapping virtual mappings cannot be joined unambiguously")
    return rows, skipped_kernel


class MappedReader:
    def __init__(self, source, rows):
        self.source = source
        self.rows = rows
        self.starts = [row.virtual for row in rows]

    def read(self, virtual, limit):
        """Return resident bytes and the exact spans; never bridge a virtual gap."""
        output = bytearray()
        spans = []
        position = virtual
        index = bisect.bisect_right(self.starts, position) - 1
        while 0 <= index < len(self.rows) and len(output) < limit:
            row = self.rows[index]
            end = row.virtual + row.size
            if not row.virtual <= position < end:
                break
            amount = min(end - position, limit - len(output))
            physical = row.physical + position - row.virtual
            self.source.seek(physical)
            block = self.source.read(amount)
            if block:
                spans.append({"virtual": position, "physical": physical, "size": len(block)})
                output.extend(block)
            position += len(block)
            if len(block) != amount:
                break
            if position == end:
                index += 1
                if index == len(self.rows) or self.rows[index].virtual != position:
                    break
        return bytes(output), spans

    def runs(self):
        start = end = None
        for row in self.rows:
            if start is not None and row.virtual != end:
                yield start, end - start
                start = None
            if start is None:
                start = row.virtual
            end = row.virtual + row.size
        if start is not None:
            yield start, end - start


def frame_end(blob, encoding):
    """Locate the closing brace without decoding unrelated bytes after the object."""
    step = 2 if encoding == "utf-16-le" else 1
    stack = []
    quoted = escaped = False
    for offset in range(0, len(blob) - step + 1, step):
        char = int.from_bytes(blob[offset:offset + step], "little")
        if quoted:
            if escaped:
                escaped = False
            elif char == 0x5C:
                escaped = True
            elif char == 0x22:
                quoted = False
            continue
        if char == 0x22:
            quoted = True
        elif char in (0x7B, 0x5B):
            stack.append(char)
        elif char in (0x7D, 0x5D):
            expected = 0x7B if char == 0x7D else 0x5B
            if not stack or stack.pop() != expected:
                raise ValueError("Mismatched JSON delimiter")
            if not stack:
                return offset + step
    return None


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def reject_constant(value):
    raise ValueError(f"Non-JSON constant: {value}")


def strict_json(text):
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)


def parse_sse(text):
    """Dispatch complete SSE events, including multiline data and default names.

    An unterminated final event is deliberately not dispatched. This follows the
    event-stream framing rule; it is not a repair heuristic for truncated RAM.
    """
    events = []
    data_lines = []
    event_name = ""
    last_id = None
    for line in text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n").split("\n")[:-1]:
        if not line:
            if data_lines:
                data_text = "\n".join(data_lines)
                event = {"event": event_name or "message", "data_text": data_text}
                if last_id is not None:
                    event["id"] = last_id
                if data_text == "[DONE]":
                    event["done"] = True
                else:
                    try:
                        event["data"] = strict_json(data_text)
                    except ValueError:
                        event["json_valid"] = False
                events.append(event)
            data_lines = []
            event_name = ""
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "data":
            data_lines.append(value)
        elif field == "event":
            event_name = value
        elif field == "id" and "\x00" not in value:
            last_id = value
    return events


def clipped_spans(spans, amount):
    result = []
    for span in spans:
        if amount <= 0:
            break
        size = min(amount, span["size"])
        result.append({**span, "size": size})
        amount -= size
    if amount:
        raise ValueError("Record bytes are not completely covered by provenance")
    return result


def scan(source, values, image_size, cap=DEFAULT_CAP, chunk_size=1024 * 1024):
    if cap <= 0 or chunk_size <= 0:
        raise ValueError("Caps and chunk sizes must be positive")
    rows, skipped = normalize_rows(values, image_size)
    reader = MappedReader(source, rows)
    stats = Counter()
    candidates = {}
    seen_hits = set()
    signatures = [(encoding, SIGNATURE_TEXT.encode(encoding)) for encoding in ENCODINGS]
    overlap = max(len(signature) for _, signature in signatures) - 1
    for run_start, run_size in reader.runs():
        tail = b""
        for position in range(run_start, run_start + run_size, chunk_size):
            block, _ = reader.read(position, min(chunk_size, run_start + run_size - position))
            window = tail + block
            base = position - len(tail)
            for encoding, signature in signatures:
                offset = 0
                while True:
                    offset = window.find(signature, offset)
                    if offset < 0:
                        break
                    address = base + offset
                    offset += 1
                    if (address, encoding) in seen_hits:
                        continue
                    seen_hits.add((address, encoding))
                    stats["signature_hits"] += 1
                    blob, spans = reader.read(address, cap)
                    try:
                        end = frame_end(blob, encoding)
                        if end is None:
                            stats["cap_limited_hits" if len(blob) == cap else "gap_or_end_truncated_hits"] += 1
                            continue
                        raw = blob[:end]
                        payload = strict_json(raw.decode(encoding, errors="strict"))
                        if (not isinstance(payload, dict) or payload.get("type") != "stream-item"
                                or not isinstance(payload.get("encoded_item"), str)):
                            stats["schema_rejected_hits"] += 1
                            continue
                    except (ValueError, UnicodeError):
                        stats["invalid_json_or_encoding_hits"] += 1
                        continue
                    digest = hashlib.sha256(raw).hexdigest()
                    key = (digest, encoding)
                    if key not in candidates:
                        candidates[key] = {
                            "record_sha256": digest,
                            "encoding": encoding,
                            "raw_byte_length": len(raw),
                            "source_virtual_addresses": [],
                            "source_spans": [],
                            "payload": payload,
                            "decoded_events": parse_sse(payload["encoded_item"]),
                        }
                    candidates[key]["source_virtual_addresses"].append(address)
                    candidates[key]["source_spans"].append(clipped_spans(spans, end))
                    stats["complete_record_occurrences"] += 1
            tail = window[-overlap:]
    return {
        "method": "development: exact bounded stream-item JSON; UTF-8/UTF-16LE; resident virtual adjacency",
        "ground_truth_supplied": False,
        "scope": "envelope recovery only; not a V8 graph or a proven turn",
        "record_byte_cap": cap,
        "user_space_rows": len(rows),
        "skipped_kernel_rows": skipped,
        "stats": dict(stats),
        "unique_complete_records": len(candidates),
        "records": list(candidates.values()),
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--record-cap", type=int, default=DEFAULT_CAP)
    args = cli.parse_args()
    values = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    with args.image.open("rb") as source:
        result = scan(source, values, args.image.stat().st_size, cap=args.record_cap)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=True)
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))


if __name__ == "__main__":
    main()
