"""Exploratory known-marker scan. This is not the blind reconstruction parser."""

import gzip
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
IMAGE = ROOT / "pilot_iab_001.raw.gz"
OUTPUT = ROOT / "pilot_iab_001_known_marker_scan.json"
CHUNK = 16 * 1024 * 1024
OVERLAP = 4096

needles = {
    "prompt_marker": "142ed00e-0fb5-4557-a684-cdb527c037b8",
    "response": "Earth is the third planet from the Sun, and its natural satellite is the Moon.",
    "conversation_id": "6aaac975-a214-83ea-93ba-0b02f0acb35d",
    "provisional_web_id": "WEB:81f9bd0d-1a63-431a-8f75-d5c8de82e423",
    "user_message_id": "a1ff7827-ca1a-4b0f-a321-80a8132fe49f",
    "assistant_message_id": "3088c259-07e1-4422-89c4-258b45068e9e",
}
patterns = {}
for name, value in needles.items():
    patterns[name + "_ascii"] = value.encode("ascii")
    patterns[name + "_utf16le"] = value.encode("utf-16le")

hits = {name: [] for name in patterns}
contexts = []
start = datetime.now(timezone.utc).isoformat()
offset = 0
tail = b""
with gzip.open(IMAGE, "rb") as stream:
    while True:
        chunk = stream.read(CHUNK)
        if not chunk:
            break
        buffer = tail + chunk
        base = offset - len(tail)
        safe_end = len(buffer) - OVERLAP
        if safe_end < 0:
            safe_end = 0
        for name, needle in patterns.items():
            at = 0
            while True:
                at = buffer.find(needle, at)
                if at < 0 or at >= safe_end:
                    break
                absolute = base + at
                if not hits[name] or hits[name][-1] != absolute:
                    hits[name].append(absolute)
                    if name == "prompt_marker_ascii" and len(contexts) < 20:
                        before = max(0, at - 512)
                        after = min(len(buffer), at + len(needle) + 1024)
                        raw = buffer[before:after]
                        printable = "".join(chr(c) if 32 <= c <= 126 else "." for c in raw)
                        contexts.append({"offset": absolute, "printable_context": printable})
                at += len(needle)
        offset += len(chunk)
        tail = buffer[-OVERLAP:]

base = offset - len(tail)
for name, needle in patterns.items():
    at = 0
    while True:
        at = tail.find(needle, at)
        if at < 0:
            break
        absolute = base + at
        if not hits[name] or hits[name][-1] != absolute:
            hits[name].append(absolute)
        at += len(needle)

record = {
    "classification": "known-marker strings scan for pilot exploration only; not blind reconstruction",
    "start_utc": start,
    "end_utc": datetime.now(timezone.utc).isoformat(),
    "decompressed_bytes": offset,
    "hits": {name: {"count": len(v), "offsets": v[:100]} for name, v in hits.items()},
    "prompt_contexts_private": contexts,
}
OUTPUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in record.items() if k != "prompt_contexts_private"}, indent=2))
