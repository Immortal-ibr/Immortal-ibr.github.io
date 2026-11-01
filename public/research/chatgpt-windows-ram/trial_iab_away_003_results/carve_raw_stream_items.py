"""Exploratory full-physical-RAM stream-item carving after the frozen test.

This extends the frozen method's search scope from mapped user-space pages to
every raw physical byte. It receives no ground-truth values and reuses the
frozen parser's syntax and SSE decoder. It cannot attribute hits to a process.
"""

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(r"C:\Users\Win10\Desktop\cheater_ram_research_2026-09-16")
TRIAL = Path(__file__).resolve().parent
PRIVATE = TRIAL / "private"
IMAGE = PRIVATE / "memory.raw"
sys.path.insert(0, str(ROOT / "trial_iab_visible_002"))
from parse_stream_items import MAX_RECORD_BYTES, SIGNATURE, parse_sse  # noqa: E402


CHUNK = 16 * 1024 * 1024
OVERLAP = MAX_RECORD_BYTES
decoder = json.JSONDecoder()
candidates = {}
signature_hits = 0
invalid_hits = 0
base = 0
carry = b""

with IMAGE.open("rb", buffering=0) as source:
    while True:
        block = source.read(CHUNK)
        final = not block
        data = carry + block
        limit = len(data) if final else max(0, len(data) - OVERLAP)
        index = 0
        while True:
            index = data.find(SIGNATURE, index, limit)
            if index < 0:
                break
            signature_hits += 1
            blob = data[index : index + MAX_RECORD_BYTES]
            try:
                record, _ = decoder.raw_decode(blob.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                invalid_hits += 1
                index += 1
                continue
            if isinstance(record, dict) and record.get("type") == "stream-item" and isinstance(record.get("encoded_item"), str):
                canonical = json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")
                digest = hashlib.sha256(canonical).hexdigest()
                if digest not in candidates:
                    candidates[digest] = {
                        "record_sha256": digest,
                        "source_physical_addresses": [],
                        "payload": record,
                        "decoded_events": parse_sse(record["encoded_item"]),
                    }
                candidates[digest]["source_physical_addresses"].append(base + index)
            else:
                invalid_hits += 1
            index += 1
        if final:
            base += len(data)
            break
        base += limit
        carry = data[limit:]
        if base % (2 * 1024 * 1024 * 1024) < CHUNK:
            print(f"Scanned {base // (1024 * 1024 * 1024)} GiB; {len(candidates)} unique bounded records", flush=True)

result = {
    "method": "unfrozen exploratory raw physical scan for frozen stream-item syntax; no process attribution",
    "ground_truth_supplied": False,
    "image": str(IMAGE),
    "scanned_bytes": base,
    "signature_hits": signature_hits,
    "invalid_or_incomplete_hits": invalid_hits,
    "unique_complete_records": len(candidates),
    "records": list(candidates.values()),
}
(PRIVATE / "raw_carved_stream_items_private.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
