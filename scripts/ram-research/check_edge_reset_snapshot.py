"""Post-hoc byte control for the saved VM state used before four Edge trials.

This is not the blind turn parser. Trial values are read from private, after-
capture observations. Only counts, never the values or memory bytes, are
written to the output. The input is the exact VMware .vmem file, not a WinPmem
image; a zero means the tested sequence was not found in that saved file.
"""

import argparse
import json
from pathlib import Path

from count_known_raw_gzip import SYNTHETIC_LABEL, UUID, count_stream, load


CASES = (
    ("visible_001", "edge-positive-submit-20261001.json", "edge_anonymous_cdp_visible_001/ids.json"),
    ("unicode_002", "edge-unicode-submit-20261001.json", "edge_anonymous_cdp_unicode_002/ids.json"),
    ("visible_003", "edge-repeat-submit-20261001.json", "edge_anonymous_cdp_visible_003/ids.json"),
    ("away_004", "edge-away-submit-20261001.json", "edge-away-ids-20261001.json"),
)


def control_values(private_root: Path) -> dict[str, str]:
    values = {}
    for name, submission_name, ids_name in CASES:
        submission = load(private_root / submission_name)
        ids = load(private_root / ids_name)
        prompt = submission["prompt"]
        marker = UUID.search(prompt) or SYNTHETIC_LABEL.search(prompt)
        conversation = UUID.search(ids["page"]["url"])
        if not marker or not conversation:
            raise ValueError(f"Missing prompt marker or URL conversation ID in {name}")
        li = [hit for hit in ids["page"]["uuid_attribute_hits"]
              if hit["tag"] == "LI" and hit["name"] == "id" and UUID.fullmatch(hit["value"])]
        user = [hit for hit in li if prompt in (hit.get("text") or "")]
        assistant = [hit for hit in li if hit not in user]
        if len(user) != 1 or len(assistant) != 1 or user[0]["value"] == assistant[0]["value"]:
            raise ValueError(f"Could not identify exactly one user/assistant pair in {name}")
        values.update({
            f"{name}/conversation_id": conversation.group(),
            f"{name}/prompt_marker": marker.group(),
            f"{name}/user_message_id": user[0]["value"],
            f"{name}/assistant_message_id": assistant[0]["value"],
        })
    return values


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--vmem", required=True, type=Path)
    cli.add_argument("--private-root", required=True, type=Path)
    cli.add_argument("--expected-bytes", required=True, type=int)
    cli.add_argument("--expected-sha256", required=True)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    values = control_values(args.private_root)
    needles = {f"{name}/{encoding}": value.encode(encoding)
               for name, value in values.items() for encoding in ("utf-8", "utf-16-le")}
    if len(set(needles.values())) != len(needles):
        raise ValueError("Trial markers must produce distinct encoded sequences")
    with args.vmem.open("rb") as source:
        counts, length, digest = count_stream(source, needles)
    if length != args.expected_bytes or digest != args.expected_sha256.upper():
        raise ValueError("VMware saved-memory length or SHA-256 does not match the supplied baseline")
    result = {
        "method": "Post-hoc exact-byte scan of the verified VMware saved-memory file",
        "snapshot_sha256_verified": True,
        "vmem_bytes": length,
        "cases": [name for name, _, _ in CASES],
        "encodings": ["UTF-8", "UTF-16LE"],
        "counts": counts,
        "interpretation": "A zero means the tested exact sequence was not found in this saved .vmem file; it does not establish that all RAM was zeroed or that a later live process could not inherit other residue.",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"vmem_bytes": length, "patterns": len(needles),
                      "nonzero_patterns": sum(count > 0 for count in counts.values())}))


if __name__ == "__main__":
    main()
