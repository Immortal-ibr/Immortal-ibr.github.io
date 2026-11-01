"""Replay exact synthetic record bytes through the frozen framing and join stages.

The tiny in-memory image and page map below are artificial. This checks record
framing/joining, not the original full-RAM extraction or process attribution.
"""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--method", required=True, type=Path)
    cli.add_argument("--fixture", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    manifest = json.loads((args.method / "FROZEN_METHOD.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        raw = (args.method / entry["path"]).read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise SystemExit("Frozen source mismatch; refusing to run")
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    image, rows = bytearray(), []
    for index, entry in enumerate(fixture["records"]):
        raw = bytes.fromhex(entry["raw_hex"])
        if len(raw) != entry["raw_byte_length"] or hashlib.sha256(raw).hexdigest() != entry["record_sha256"]:
            raise SystemExit("Record source-byte digest mismatch")
        # Deliberately non-adjacent virtual runs, no original-map claim.
        rows.append({"Virtual": 4096 + index * 8192, "Physical": len(image), "Size": len(raw)})
        image.extend(raw)
        image.extend(b"\0" * 13)
    sys.path.insert(0, str(args.method.resolve(strict=True)))
    from cli_core_events import recover
    replay = recover(io.BytesIO(image), rows, len(image), cap=manifest["record_cap_bytes"])
    candidates = replay["join"]["candidates"]
    expected_count = fixture.get("expected_candidate_count", 1)
    count_matches = len(candidates) == expected_count
    fields_match = (all(candidates[0].get(key) == value for key, value in fixture["expected"].items())
                    if expected_count == 1 and len(candidates) == 1 else None)
    matches = count_matches and (fields_match if expected_count else True)
    output = {"method_hashes_verified": True, "record_byte_hashes_verified": True,
              "source_records": len(fixture["records"]), "replayed_records": replay["unique_complete_core_records"],
              "candidate_count": len(candidates), "expected_candidate_count_matches": count_matches,
              "expected_fields_match": fields_match, "all_fixture_checks_pass": matches,
              "assistant_id_independently_bound": candidates[0]["agent_id_independently_bound"] if candidates else None,
              "original_image_replayed": False, "original_process_attribution_verified": False,
              "scope": "exact record-byte framing and join replay on an artificial tiny image/map"}
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(output, target, indent=2)
    print(json.dumps(output, indent=2))
    if not matches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
