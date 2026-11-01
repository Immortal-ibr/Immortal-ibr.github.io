"""Classify known-marker surroundings in the pilot image; exploratory only."""

import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGE = ROOT / "pilot_iab_001.raw.gz"
OUTPUT = ROOT / "pilot_iab_001_contexts_private.json"
MARKER = b"142ed00e-0fb5-4557-a684-cdb527c037b8"
CHUNK = 16 * 1024 * 1024
OVERLAP = 4096

def classify(context):
    lower = context.lower()
    if b"pilot_iab_001_ground_truth" in lower or b'"clean_vm_reset"' in lower:
        return "ground_truth_copy"
    if any(x in lower for x in (b"mcp__cua_repl", b"internal_chat_message_metadata", b"browser tab:", b"axwebarea", b"unifiedexecstartup", b"commandexecution")):
        return "codex_tool_or_transcript"
    if b'"author":"user"' in lower and b'"author":"assistant"' in lower:
        return "dom_capture_copy"
    if any(x in lower for x in (b'"conversation_id"', b'"create_time"', b'"parent_id"', b'"message"')):
        return "record_like_unattributed"
    return "unclassified"

records = []
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
        safe_end = max(0, len(buffer) - OVERLAP)
        at = 0
        while True:
            at = buffer.find(MARKER, at)
            if at < 0 or at >= safe_end:
                break
            before = max(0, at - 1024)
            after = min(len(buffer), at + len(MARKER) + 2048)
            context = buffer[before:after]
            rendered = "".join(chr(c) if 32 <= c <= 126 else "." for c in context)
            records.append({"offset": base + at, "class": classify(context), "context": rendered})
            at += len(MARKER)
        offset += len(chunk)
        tail = buffer[-OVERLAP:]

for name, value in Counter(x["class"] for x in records).items():
    print(name, value)
print("total", len(records), "decompressed_bytes", offset)
OUTPUT.write_text(json.dumps({"classification": "private exploratory contexts; may contain sensitive data", "start_utc": start, "end_utc": datetime.now(timezone.utc).isoformat(), "records": records}, indent=2), encoding="utf-8")
