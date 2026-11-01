"""Parse bounded ChatGPT stream-item JSON records from mapped user-space RAM.

Inputs are a raw physical-memory image and a Volatility windows.memmap JSON file.
This parser receives no known prompt, answer, conversation ID, message ID, or
offset. It scans only user virtual addresses and records complete JSON objects
with type=stream-item and an encoded_item string. The output is private because
it can contain unrelated conversation content. It is a pilot parser, not yet a
validated held-out method.
"""

import argparse
import bisect
import hashlib
import json
from pathlib import Path


SIGNATURE = b'{"type":"stream-item"'
USER_LIMIT = 1 << 47
MAX_RECORD_BYTES = 131072


def mapped_bytes(source, rows, starts, virtual, limit):
    """Read forward through physically resident, virtually adjacent rows."""
    output = bytearray()
    position = virtual
    while len(output) < limit:
        index = bisect.bisect_right(starts, position) - 1
        if index < 0:
            break
        row = rows[index]
        row_start = int(row["Virtual"])
        row_end = row_start + int(row["Size"])
        if not row_start <= position < row_end:
            break
        amount = min(row_end - position, limit - len(output))
        source.seek(int(row["Physical"]) + position - row_start)
        block = source.read(amount)
        output.extend(block)
        if len(block) < amount:
            break
        position += amount
        if position == row_end and (index + 1 >= len(rows) or int(rows[index + 1]["Virtual"]) != position):
            break
    return bytes(output)


def parse_sse(encoded):
    events = []
    event_name = None
    for line in encoded.splitlines():
        if line.startswith("event: "):
            event_name = line[7:]
        elif line.startswith("data: "):
            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            events.append({"event": event_name, "data": data})
    return events


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()

    rows_all = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    rows = sorted((row for row in rows_all if int(row["Virtual"]) < USER_LIMIT), key=lambda row: int(row["Virtual"]))
    starts = [int(row["Virtual"]) for row in rows]
    decoder = json.JSONDecoder()
    candidates = {}
    signature_hits = 0
    incomplete_or_invalid = 0

    with args.image.open("rb", buffering=0) as source:
        for row in rows:
            physical = int(row["Physical"])
            virtual = int(row["Virtual"])
            size = int(row["Size"])
            if size <= 0 or physical < 0 or physical + size > args.image.stat().st_size:
                continue
            source.seek(physical)
            data = source.read(size)
            index = 0
            while True:
                index = data.find(SIGNATURE, index)
                if index < 0:
                    break
                signature_hits += 1
                address = virtual + index
                blob = mapped_bytes(source, rows, starts, address, MAX_RECORD_BYTES)
                try:
                    record, consumed = decoder.raw_decode(blob.decode("utf-8", errors="replace"))
                except (json.JSONDecodeError, UnicodeError):
                    incomplete_or_invalid += 1
                    index += 1
                    continue
                if not isinstance(record, dict) or record.get("type") != "stream-item" or not isinstance(record.get("encoded_item"), str):
                    index += 1
                    continue
                digest = hashlib.sha256(blob[:consumed].strip()).hexdigest()
                if digest not in candidates:
                    candidates[digest] = {
                        "record_sha256": digest,
                        "source_virtual_addresses": [],
                        "payload": record,
                        "decoded_events": parse_sse(record["encoded_item"]),
                    }
                candidates[digest]["source_virtual_addresses"].append(address)
                index += 1

    result = {
        "method": "bounded stream-item JSON from user-space mapped physical pages; no known turn values supplied",
        "image": str(args.image),
        "memmap": str(args.memmap),
        "user_space_rows": len(rows),
        "signature_hits": signature_hits,
        "incomplete_or_invalid_hits": incomplete_or_invalid,
        "unique_complete_records": len(candidates),
        "records": list(candidates.values()),
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))


if __name__ == "__main__":
    main()
