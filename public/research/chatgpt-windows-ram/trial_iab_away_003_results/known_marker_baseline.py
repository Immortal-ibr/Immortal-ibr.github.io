"""Ground-truth-assisted raw string baseline; ineligible as a reconstruction."""

import json
import re
from pathlib import Path


TRIAL = Path(__file__).resolve().parent
PRIVATE = TRIAL / "private"
truth = json.loads((TRIAL / "ground_truth.json").read_text(encoding="utf-8"))
prompt_id = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", truth["prompt"]).group(0)
values = {
    "prompt_uuid": prompt_id,
    "prompt_exact": truth["prompt"],
    "response_exact": truth["actual_response"],
    "conversation_id": truth["conversation_id_from_url"],
    "user_message_id": truth["user_message_id_from_DOM"],
    "assistant_message_id": truth["assistant_message_id_from_DOM"],
}
needles = [(f"{key}_{encoding}", value.encode(codec)) for key, value in values.items() for encoding, codec in (("ascii", "utf-8"), ("utf16le", "utf-16le"))]
counts = {key: 0 for key, _ in needles}
CHUNK = 16 * 1024 * 1024
OVERLAP = max(len(value) for _, value in needles) - 1
carry = b""
scanned = 0
with (PRIVATE / "memory.raw").open("rb", buffering=0) as source:
    while True:
        block = source.read(CHUNK)
        final = not block
        data = carry + block
        limit = len(data) if final else max(0, len(data) - OVERLAP)
        for key, needle in needles:
            start = 0
            while True:
                index = data.find(needle, start, limit)
                if index < 0:
                    break
                counts[key] += 1
                start = index + 1
        if final:
            scanned += len(data)
            break
        scanned += limit
        carry = data[limit:]

result = {
    "trial_id": truth["trial_id"],
    "method": "ground-truth-assisted exact-string scan of full physical RAM; not blind or process-attributed",
    "scanned_bytes": scanned,
    "counts": counts,
    "interpretation": "Byte presence can come from the browser, browser-control runtime, Codex transcript/log copies, or other processes; counts do not identify a bounded linked turn."
}
(TRIAL / "known_marker_baseline.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
