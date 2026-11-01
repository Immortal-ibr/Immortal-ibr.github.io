"""Development-only scan for complete SSE data events in resident RAM pages.

The scan is structural: no prompt, answer, URL ID or offset is supplied. It
accepts only a complete event ending at a blank line and a strict JSON object
in its data field. Unfiltered event data must remain private.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from bounded_json import MappedReader, clipped_spans, normalize_rows, parse_sse


ENCODINGS = ("utf-8", "utf-16-le")
SIGNATURE = "data: {"
DEFAULT_CAP = 128 * 1024
REPOSITORY = Path(__file__).resolve().parents[2]
CONTROL_GAP = re.compile(rb"(?:event: [A-Za-z0-9_-]+(?:\r\n|\n|\r))*\Z")


def event_end(blob, encoding):
    for marker in ("\r\n\r\n", "\n\n", "\r\r"):
        encoded = marker.encode(encoding)
        offset = blob.find(encoded)
        if offset >= 0:
            yield offset + len(encoded)


def contiguous_segments(reader, records):
    """Prove sequence adjacency using actual bytes between framed events."""
    occurrences = sorted(
        (address, address + record["raw_byte_length"], index)
        for index, record in enumerate(records)
        for address in record["source_virtual_addresses"]
    )
    groups = []
    current = []
    gaps = []
    prior_end = None
    for address, end, index in occurrences:
        gap = None
        if prior_end is not None and 0 <= address - prior_end <= 256:
            gap, _ = reader.read(prior_end, address - prior_end)
            if len(gap) != address - prior_end or not CONTROL_GAP.fullmatch(gap):
                gap = None
        if gap is None:
            if current:
                groups.append((current, gaps))
            current, gaps = [], []
        else:
            gaps.append({"bytes": len(gap),
                         "control_line": gap.decode("ascii") if gap else ""})
        current.append((address, end, index))
        prior_end = end
    if current:
        groups.append((current, gaps))
    segments = []
    for group, control_gaps in groups:
        start, end = group[0][0], group[-1][1]
        raw, spans = reader.read(start, end - start)
        if len(raw) != end - start:
            raise ValueError("Contiguous event sequence has a virtual gap")
        segments.append({"start_virtual": start, "end_virtual": end,
                         "byte_length": len(raw), "stream_sha256": hashlib.sha256(raw).hexdigest(),
                         "record_indices": [item[2] for item in group],
                         "control_gaps": control_gaps,
                         "source_spans": clipped_spans(spans, len(raw))})
    return segments


def scan(source, values, image_size, cap=DEFAULT_CAP):
    if cap <= 0:
        raise ValueError("Event cap must be positive")
    rows, skipped = normalize_rows(values, image_size)
    reader = MappedReader(source, rows)
    needles = [(encoding, SIGNATURE.encode(encoding)) for encoding in ENCODINGS]
    overlap = max(map(lambda entry: len(entry[1]), needles)) - 1
    stats = Counter()
    seen = set()
    records = {}
    for run_start, run_size in reader.runs():
        tail = b""
        for position in range(run_start, run_start + run_size, 1024 * 1024):
            block, _ = reader.read(position, min(1024 * 1024,
                                                 run_start + run_size - position))
            window = tail + block
            base = position - len(tail)
            for encoding, needle in needles:
                cursor = 0
                while (offset := window.find(needle, cursor)) != -1:
                    address = base + offset
                    cursor = offset + 1
                    if (address, encoding) in seen:
                        continue
                    seen.add((address, encoding))
                    stats["signature_hits"] += 1
                    blob, spans = reader.read(address, cap)
                    end = min(event_end(blob, encoding), default=None)
                    if end is None:
                        stats["truncated_or_cap_limited"] += 1
                        continue
                    raw = blob[:end]
                    try:
                        events = parse_sse(raw.decode(encoding, errors="strict"))
                    except UnicodeError:
                        stats["invalid_encoding"] += 1
                        continue
                    if len(events) != 1 or not isinstance(events[0].get("data"), dict):
                        stats["invalid_or_non_object_event"] += 1
                        continue
                    digest = hashlib.sha256(raw).hexdigest()
                    key = (encoding, digest)
                    if key not in records:
                        records[key] = {
                            "encoding": encoding, "record_sha256": digest,
                            "raw_byte_length": len(raw), "event": events[0],
                            "source_virtual_addresses": [], "source_spans": [],
                        }
                    records[key]["source_virtual_addresses"].append(address)
                    records[key]["source_spans"].append(clipped_spans(spans, end))
                    stats["complete_event_occurrences"] += 1
            tail = window[-overlap:] if overlap else b""
    record_list = list(records.values())
    return {"method": "development complete SSE data event scan in resident user mappings",
            "ground_truth_supplied": False, "record_byte_cap": cap,
            "resident_user_rows": len(rows), "skipped_kernel_rows": skipped,
            "stats": dict(stats), "unique_complete_records": len(records),
            "records": record_list,
            "contiguous_segments": contiguous_segments(reader, record_list)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Unfiltered events must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    rows = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    with args.image.open("rb", buffering=0) as source:
        result = scan(source, rows, args.image.stat().st_size)
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, ensure_ascii=True)
        target.write("\n")
    print(json.dumps({"stats": result["stats"],
                      "unique_complete_records": result["unique_complete_records"]}))


if __name__ == "__main__":
    main()
