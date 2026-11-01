"""Run fresh fixture joins, rather than compare two previously saved reports.

This verifies only joining selected synthetic records, not extraction from RAM.
Frozen code is hash-checked before execution. Byte comparisons are reported
separately because the frozen writer uses the platform's text newline convention.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / "FROZEN_METHOD_V2.json").read_text(encoding="utf-8"))
    frozen_files = dict(manifest["method_files"])
    frozen_files[manifest["runner_file"]] = manifest["runner_sha256"]
    checks = [{"file": name, "expected_sha256": expected,
               "actual_sha256": sha256(root / name)}
              for name, expected in frozen_files.items()]
    for check in checks:
        check["matches"] = check["actual_sha256"] == check["expected_sha256"]
    if not all(check["matches"] for check in checks):
        raise ValueError("Frozen file changed; refusing to execute the joiner")
    method = root / "method_v2/reconstruct_turns.py"
    cases = [("two_chats", "trial_iab_two_chats_004_results", 2),
             ("visible", "trial_iab_visible_005_results", 1)]
    results = []
    with tempfile.TemporaryDirectory(prefix="chatgpt-fixture-replay-") as temp:
        for label, folder, count in cases:
            fixture = root / folder / "synthetic_record_fixture.json"
            expected = root / folder / "fixture_reconstruction_v2.json"
            replay = Path(temp) / (label + ".json")
            subprocess.run([sys.executable, str(method), "--parsed", str(fixture),
                            "--output", str(replay)], check=True, capture_output=True)
            a = json.loads(expected.read_text(encoding="utf-8"))
            b = json.loads(replay.read_text(encoding="utf-8"))
            expected_bytes = expected.read_bytes()
            replay_bytes = replay.read_bytes()
            results.append({"case": label, "fresh_joiner_executed": True,
                            "expected_candidates": count,
                            "replay_candidates": len(b["candidate_turns"]),
                            "exact_json_match": a == b,
                            "exact_bytes_match": expected_bytes == replay_bytes,
                            "equal_after_crlf_to_lf": expected_bytes.replace(b"\r\n", b"\n") ==
                                                       replay_bytes.replace(b"\r\n", b"\n"),
                            "fixture_sha256": sha256(fixture),
                            "saved_result_sha256": sha256(expected),
                            "replay_sha256": sha256(replay)})
    return {"verified_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "Fresh joins of retained synthetic records; no RAM extraction",
            "method_sha256": sha256(method),
            "frozen_manifest_method_sha256": frozen_files["method_v2/reconstruct_turns.py"],
            "method_matches_frozen_manifest": True,
            "frozen_files": checks, "cases": results,
            "all_checks_pass": all(r["exact_json_match"] and
                                   r["replay_candidates"] == r["expected_candidates"]
                                   for r in results)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    cli.add_argument("--output", type=Path,
                     help="Optional new report path; existing reports are not overwritten")
    args = cli.parse_args()
    if args.output and args.output.exists():
        raise SystemExit("Refusing to overwrite an existing replay report")
    record = verify(args.root)
    rendered = json.dumps(record, indent=2)
    if args.output:
        with args.output.open("x", encoding="utf-8") as destination:
            destination.write(rendered)
    print(rendered)
    if not record["all_checks_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
