"""Development scan of bounded signed-in browser JSON envelopes in RAM.

This grammar is structural and receives no prompt, answer, identifier, or
offset. Unfiltered records may include unrelated signed-in activity and must
remain private. It frames exact bytes across virtually adjacent resident pages.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from bounded_json import (MappedReader, clipped_spans, frame_end,
                          normalize_rows, strict_json)


SIGNATURES = {
    "next-request": '{"action":"next","messages":',
    "message-event": '{"message":{',
    "typed-message": '{"type":"message",',
}
ENCODINGS = ("utf-8", "utf-16-le")
DEFAULT_CAP = 1024 * 1024
REPOSITORY = Path(__file__).resolve().parents[2]


def valid_envelope(payload, kind):
    if not isinstance(payload, dict):
        return False
    if kind == "next-request":
        return (payload.get("action") == "next"
                and isinstance(payload.get("messages"), list)
                and isinstance(payload.get("conversation_id"), str))
    if kind == "message-event":
        message = payload.get("message")
        return (isinstance(message, dict)
                and isinstance(message.get("id"), str)
                and isinstance(message.get("author"), dict)
                and isinstance(payload.get("conversation_id"), str))
    if kind == "typed-message":
        return payload.get("type") == "message" and isinstance(payload.get("id"), str)
    return False


def scan(source, values, image_size, cap=DEFAULT_CAP):
    if cap <= 0:
        raise ValueError("record cap must be positive")
    rows, skipped = normalize_rows(values, image_size)
    reader = MappedReader(source, rows)
    needles = [(kind, encoding, signature.encode(encoding))
               for kind, signature in SIGNATURES.items()
               for encoding in ENCODINGS]
    overlap = max(len(needle) for _, _, needle in needles) - 1
    stats = Counter()
    seen_locations = set()
    records = {}
    for run_start, run_size in reader.runs():
        tail = b""
        for position in range(run_start, run_start + run_size, 1024 * 1024):
            block, _ = reader.read(position, min(1024 * 1024,
                                                 run_start + run_size - position))
            window = tail + block
            base = position - len(tail)
            for kind, encoding, needle in needles:
                cursor = 0
                while (offset := window.find(needle, cursor)) != -1:
                    address = base + offset
                    cursor = offset + 1
                    location = (address, encoding, kind)
                    if location in seen_locations:
                        continue
                    seen_locations.add(location)
                    stats[f"{kind}/signature_hits"] += 1
                    blob, spans = reader.read(address, cap)
                    try:
                        end = frame_end(blob, encoding)
                        if end is None:
                            stats[f"{kind}/truncated_or_cap_limited"] += 1
                            continue
                        raw = blob[:end]
                        payload = strict_json(raw.decode(encoding, errors="strict"))
                    except (ValueError, UnicodeError):
                        stats[f"{kind}/invalid_json_or_encoding"] += 1
                        continue
                    if not valid_envelope(payload, kind):
                        stats[f"{kind}/schema_rejected"] += 1
                        continue
                    digest = hashlib.sha256(raw).hexdigest()
                    key = (kind, encoding, digest)
                    if key not in records:
                        records[key] = {
                            "kind": kind,
                            "encoding": encoding,
                            "record_sha256": digest,
                            "raw_byte_length": len(raw),
                            "payload": payload,
                            "source_virtual_addresses": [],
                            "source_spans": [],
                        }
                    records[key]["source_virtual_addresses"].append(address)
                    records[key]["source_spans"].append(clipped_spans(spans, end))
                    stats[f"{kind}/complete_occurrences"] += 1
            tail = window[-overlap:] if overlap else b""
    return {"method": "development bounded JSON envelopes in resident user mappings",
            "ground_truth_supplied": False, "record_byte_cap": cap,
            "resident_user_rows": len(rows), "skipped_kernel_rows": skipped,
            "stats": dict(stats), "unique_complete_records": len(records),
            "records": list(records.values())}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--memmap", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--record-cap", type=int, default=DEFAULT_CAP)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Unfiltered output must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    values = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    with args.image.open("rb", buffering=0) as source:
        result = scan(source, values, args.image.stat().st_size, args.record_cap)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n",
                      encoding="utf-8")
    print(json.dumps({"stats": result["stats"],
                      "unique_complete_records": result["unique_complete_records"]}))


if __name__ == "__main__":
    main()
