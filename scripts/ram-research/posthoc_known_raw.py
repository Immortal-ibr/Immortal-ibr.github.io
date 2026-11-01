"""Private post-capture check for independently observed synthetic UI values.

This deliberately receives ground truth and therefore cannot reconstruct a
conversation. It only checks whether exact bytes still exist in the image and
which image-selected resident renderer maps contain them.
"""

import argparse
import json
from pathlib import Path

from attribute_known_browser_hits import scan_map
from count_known_raw_gzip import count_stream


REPOSITORY = Path(__file__).resolve().parents[2]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, action="append", required=True)
    cli.add_argument("--known-values", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Known-value first-hit addresses stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    known = json.loads(args.known_values.read_text(encoding="utf-8-sig"))
    values = {key: known[key] for key in ("conversation_id", "prompt", "response")}
    if any(not isinstance(value, str) or not value for value in values.values()):
        raise ValueError("Independent ground truth is incomplete")
    needles = {f"{name}/{encoding}": value.encode(encoding)
               for name, value in values.items()
               for encoding in ("utf-8", "utf-16-le")}
    with args.image.open("rb", buffering=0) as source:
        physical_counts, raw_bytes, raw_sha256 = count_stream(source, needles)
    maps = [scan_map(args.image, memmap, needles) for memmap in args.memmap]
    result = {
        "method": "post-hoc exact synthetic-value diagnostic; not a turn reconstruction",
        "ground_truth_supplied": True,
        "raw_bytes": raw_bytes,
        "raw_sha256": raw_sha256,
        "physical_counts": physical_counts,
        "renderer_maps": maps,
        "warning": "Physical hits lack process attribution; mapped counts can alias physical pages.",
    }
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(json.dumps({"raw_sha256": raw_sha256,
                      "physical_counts": physical_counts,
                      "renderer_counts": [{"mapfile": row["mapfile"],
                                           "counts": row["mapped_occurrence_counts"]}
                                          for row in maps]}))


if __name__ == "__main__":
    main()
