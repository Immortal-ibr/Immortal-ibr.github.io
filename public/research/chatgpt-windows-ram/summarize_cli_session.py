"""Summarize one synthetic CLI turn in the local Codex session JSONL.

The raw session is read in place and never copied into the research folder.
Only event counts, exact-value hit counts, the synthetic session ID, and a
file hash are emitted.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial", required=True, type=Path)
    parser.add_argument("--session-file", required=True, type=Path)
    args = parser.parse_args()

    trial = args.trial.resolve()
    session = args.session_file.resolve()
    truth = json.loads((trial / "ground_truth.json").read_text(encoding="utf-8-sig"))
    raw = session.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    event_types = Counter(row.get("type") for row in rows)
    hits = {"prompt": Counter(), "response": Counter(), "marker": Counter()}
    values = {"prompt": truth["prompt"],
              "response": truth["actual_response"],
              "marker": truth["marker"]}
    session_ids = set()
    for row in rows:
        payload = row.get("payload", {})
        if row.get("type") == "session_meta" and payload.get("id"):
            session_ids.add(payload["id"])
        bucket = f"{row.get('type')}:{payload.get('role')}"
        serialized = json.dumps(payload, ensure_ascii=False)
        for name, value in values.items():
            if value in serialized:
                hits[name][bucket] += serialized.count(value)

    out = {
        "trial_id": truth["trial_id"],
        "normal_session_jsonl_present": True,
        "session_ids": sorted(session_ids),
        "local_session_jsonl_bytes": len(raw),
        "local_session_jsonl_sha256": hashlib.sha256(raw).hexdigest().upper(),
        "jsonl_lines": len(rows),
        "event_types": dict(event_types),
        "exact_value_hits_by_event_and_role": {name: dict(counter) for name, counter in hits.items()},
        "source": "local Codex session JSONL on disk; separate from RAM evidence",
        "private_transcript_copied": False,
    }
    (trial / "local_file_baseline.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
