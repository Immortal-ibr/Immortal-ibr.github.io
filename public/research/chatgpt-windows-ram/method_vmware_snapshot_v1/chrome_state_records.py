"""Development parser for bounded ChatGPT web-client state objects in Chrome RAM.

It uses a structural JSON key, never a known prompt, response, or ID. The source
is each renderer's resident user-space map, not a whole-image string search.
The output is private because other conversations may also match this schema.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from bounded_json import (
    MappedReader,
    clipped_spans,
    frame_end,
    normalize_rows,
    strict_json,
)


SIGNATURE = '{"backendConversationId":"'
ENCODINGS = ("utf-8", "utf-16-le")
DEFAULT_CAP = 1024 * 1024


def valid_state(payload):
    if not isinstance(payload, dict):
        return False
    if not isinstance(payload.get("backendConversationId"), str):
        return False
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return False
    return all(
        isinstance(message, dict)
        and isinstance(message.get("id"), str)
        and isinstance(message.get("role"), str)
        and isinstance(message.get("content"), str)
        for message in messages
    )


def scan(source, values, image_size, cap=DEFAULT_CAP):
    rows, skipped = normalize_rows(values, image_size)
    reader = MappedReader(source, rows)
    signatures = [(encoding, SIGNATURE.encode(encoding)) for encoding in ENCODINGS]
    overlap = max(len(signature) for _, signature in signatures) - 1
    stats = Counter()
    seen = set()
    records = {}
    for run_start, run_size in reader.runs():
        tail = b""
        for position in range(run_start, run_start + run_size, 1024 * 1024):
            block, _ = reader.read(position, min(1024 * 1024, run_start + run_size - position))
            window = tail + block
            base = position - len(tail)
            for encoding, signature in signatures:
                cursor = 0
                while (offset := window.find(signature, cursor)) != -1:
                    address = base + offset
                    cursor = offset + 1
                    if (address, encoding) in seen:
                        continue
                    seen.add((address, encoding))
                    stats["signature_hits"] += 1
                    blob, spans = reader.read(address, cap)
                    try:
                        end = frame_end(blob, encoding)
                        if end is None:
                            stats["cap_limited" if len(blob) == cap else "gap_or_end_truncated"] += 1
                            continue
                        raw = blob[:end]
                        payload = strict_json(raw.decode(encoding, errors="strict"))
                    except (ValueError, UnicodeError):
                        stats["invalid_json_or_encoding"] += 1
                        continue
                    if not valid_state(payload):
                        stats["schema_rejected"] += 1
                        continue
                    digest = hashlib.sha256(raw).hexdigest()
                    key = (digest, encoding)
                    if key not in records:
                        records[key] = {
                            "sha256": digest,
                            "encoding": encoding,
                            "byte_length": len(raw),
                            "virtual_addresses": [],
                            "source_spans": [],
                            "state": payload,
                        }
                    records[key]["virtual_addresses"].append(address)
                    records[key]["source_spans"].append(clipped_spans(spans, end))
                    stats["complete_record_occurrences"] += 1
            tail = window[-overlap:]
    return {
        "method": "development: bounded Chrome state JSON; user-space resident maps; no known turn values",
        "ground_truth_supplied": False,
        "record_byte_cap": cap,
        "user_space_rows": len(rows),
        "skipped_kernel_rows": skipped,
        "stats": dict(stats),
        "unique_complete_records": len(records),
        "records": list(records.values()),
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--record-cap", type=int, default=DEFAULT_CAP)
    args = cli.parse_args()
    if args.record_cap <= 0:
        raise ValueError("record cap must be positive")
    values = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    with args.image.open("rb", buffering=0) as source:
        result = scan(source, values, args.image.stat().st_size, cap=args.record_cap)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=True)
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))


if __name__ == "__main__":
    main()
