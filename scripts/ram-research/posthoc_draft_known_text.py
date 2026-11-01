"""Post-hoc exact-byte diagnostic for a verified, never-submitted draft.

The independently observed prompt is supplied only after the frozen browser
parser has produced and sealed its result. Physical hits do not prove process
origin; mapped hits do not prove that a ChatGPT message was submitted.
"""

import argparse
import json
from pathlib import Path

from attribute_known_browser_hits import scan_map
from count_known_raw_gzip import count_stream


REPOSITORY = Path(__file__).resolve().parents[2]


def draft_prompt(record):
    page = record.get("page_after") or {}
    prompt = record.get("prompt")
    if (record.get("status") != "ok" or record.get("draft_exact_match") is not True
            or record.get("submission_attempted") is not False
            or page.get("url") != "https://chatgpt.com/"
            or page.get("message_li_count") != 0
            or not isinstance(prompt, str) or not prompt
            or page.get("draft") != prompt):
        raise ValueError("Input is not an independently observed unsent draft")
    return prompt


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, action="append", required=True)
    cli.add_argument("--draft-observation", type=Path, required=True)
    cli.add_argument("--expected-raw-sha256", required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Known-value locations stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    record = json.loads(args.draft_observation.read_text(encoding="utf-8-sig"))
    prompt = draft_prompt(record)
    needles = {f"prompt/{encoding}": prompt.encode(encoding)
               for encoding in ("utf-8", "utf-16-le")}
    with args.image.open("rb") as source:
        physical_counts, raw_bytes, raw_sha256 = count_stream(source, needles)
    if raw_sha256.upper() != args.expected_raw_sha256.upper():
        raise ValueError("Raw image digest differs from the verified acquisition")
    maps = [scan_map(args.image, mapfile, needles) for mapfile in args.memmap]
    result = {
        "method": "post-hoc known-draft exact-byte diagnostic; not blind reconstruction",
        "ground_truth_supplied": True,
        "submission_attempted": False,
        "raw_bytes": raw_bytes,
        "raw_sha256": raw_sha256,
        "physical_counts": physical_counts,
        "process_maps": maps,
        "warning": "Physical hits lack process attribution; mapped bytes do not prove submission or exclusive ownership.",
    }
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"raw_sha256": raw_sha256,
                      "physical_counts": physical_counts,
                      "map_counts": [{"mapfile": row["mapfile"],
                                      "counts": row["mapped_occurrence_counts"]}
                                     for row in maps]}))


if __name__ == "__main__":
    main()
