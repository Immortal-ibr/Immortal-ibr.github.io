"""Classify raw stream-item signature neighborhoods without known turn values."""

import json
from pathlib import Path


TRIAL = Path(__file__).resolve().parent
IMAGE = TRIAL / "private" / "memory.raw"
SIGNATURE = b'{"type":"stream-item"'
CHUNK = 16 * 1024 * 1024
OVERLAP = 4096
base = 0
carry = b""
contexts = []

with IMAGE.open("rb", buffering=0) as source:
    while True:
        block = source.read(CHUNK)
        final = not block
        data = carry + block
        limit = len(data) if final else max(0, len(data) - OVERLAP)
        position = 0
        while True:
            position = data.find(SIGNATURE, position, limit)
            if position < 0:
                break
            snippet = data[max(0, position - 128) : min(len(data), position + 2048)]
            after = data[position : min(len(data), position + 2048)]
            label = (
                "record_like" if b'"conversation_id"' in after and b'"encoded_item"' in after
                else "code_or_log_like" if b"SIGNATURE" in snippet or b"parse_stream_items.py" in snippet
                else "unclassified"
            )
            contexts.append({
                "physical_offset": base + position,
                "label": label,
                "context_ascii": "".join(chr(c) if 32 <= c < 127 else "." for c in snippet),
            })
            position += 1
        if final:
            break
        base += limit
        carry = data[limit:]

summary = {
    "signature_count": len(contexts),
    "label_counts": {label: sum(row["label"] == label for row in contexts) for label in ("record_like", "code_or_log_like", "unclassified")},
    "interpretation": "Heuristic classification of raw physical neighborhoods only; neither complete JSON nor process attribution."
}
(TRIAL / "private" / "raw_signature_contexts_private.json").write_text(json.dumps(contexts, indent=2), encoding="utf-8")
(TRIAL / "raw_signature_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
