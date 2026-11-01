"""Frame and join exact model-input fixture bytes using the frozen method.

The artificial image/map is NOT the original capture or a process-attribution
test. No known text, IDs or offsets are passed to the recovery function.
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
    for name in ("method", "fixture", "output"):
        cli.add_argument("--" + name, required=True, type=Path)
    args = cli.parse_args()
    manifest = json.loads((args.method / "FROZEN_METHOD.json").read_text(encoding="utf-8"))
    if manifest["method_version"] != "cli-model-input-v1":
        raise SystemExit("Not the model-input method")
    for entry in manifest["files"]:
        raw = (args.method / entry["path"]).read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise SystemExit("Frozen source mismatch")
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    image, rows = bytearray(), []
    for index, entry in enumerate(fixture["records"]):
        raw = bytes.fromhex(entry["raw_hex"])
        if len(raw) != entry["raw_byte_length"] or hashlib.sha256(raw).hexdigest() != entry["record_sha256"]:
            raise SystemExit("Record-byte digest mismatch")
        rows.append({"Virtual": 4096 + index * 8192, "Physical": len(image), "Size": len(raw)})
        image.extend(raw)
        image.extend(b"\0" * 13)
    sys.path.insert(0, str(args.method.resolve(strict=True)))
    from cli_model_turns import recover
    result = recover(io.BytesIO(image), rows, len(image), cap=manifest["record_cap_bytes"])
    candidates = result["join"]["candidates"]
    count_matches = len(candidates) == fixture["expected_candidate_count"]
    fields_match = (all(candidates[0].get(k) == v for k, v in fixture["expected"].items())
                    if fixture["expected_candidate_count"] == 1 and len(candidates) == 1 else None)
    matches = count_matches and (fields_match if fixture["expected_candidate_count"] else True)
    output = {"method_hashes_verified": True, "record_byte_hashes_verified": True,
              "source_records": len(fixture["records"]), "replayed_records": result["unique_complete_records"],
              "candidate_count": len(candidates), "expected_candidate_count_matches": count_matches,
              "expected_fields_match": fields_match, "all_fixture_checks_pass": matches,
              "original_image_replayed": False, "original_process_attribution_verified": False,
              "scope": "Framing and joining reviewed bytes on an artificial tiny image/map"}
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(output, target, indent=2)
    print(json.dumps(output, indent=2))
    if not output["all_fixture_checks_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
