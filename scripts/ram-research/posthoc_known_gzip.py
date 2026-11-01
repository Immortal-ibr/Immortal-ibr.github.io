"""Count separately observed values in verified gzip RAM, after blind parsing.

This is a ground-truth-assisted residue diagnostic, not a reconstruction.
The output includes private first-hit addresses and must stay out of the repo.
"""

import argparse
import gzip
import json
from pathlib import Path

from attribute_known_browser_hits import USER_LIMIT, count_occurrences
from count_known_raw_gzip import count_stream
from scan_verified_gzip import InMemoryRaw, REPOSITORY, sha256_file


def scan_map(source, image_size, mapfile, needles):
    rows = json.loads(mapfile.read_text(encoding="utf-8-sig"))
    counts = dict.fromkeys(needles, 0)
    first_hits = {}
    scanned_rows = 0
    scanned_bytes = 0
    for row in rows:
        physical, virtual, size = (int(row[name]) for name in ("Physical", "Virtual", "Size"))
        if virtual >= USER_LIMIT or size <= 0 or physical < 0 or physical + size > image_size:
            continue
        source.seek(physical)
        data = source.read(size)
        if len(data) != size:
            raise IOError(f"Short physical read in {mapfile.name}")
        scanned_rows += 1
        scanned_bytes += size
        for label, needle in needles.items():
            occurrences = count_occurrences(data, needle)
            counts[label] += occurrences
            if occurrences and label not in first_hits:
                offset = data.find(needle)
                first_hits[label] = {"virtual": virtual + offset,
                                     "physical": physical + offset,
                                     "byte_length": len(needle)}
    return {"mapfile": mapfile.name, "scanned_rows": scanned_rows,
            "scanned_mapped_bytes_with_possible_aliases": scanned_bytes,
            "mapped_occurrence_counts": counts, "first_hits_private": first_hits}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--acquisition", type=Path, required=True)
    cli.add_argument("--archive-sha256", required=True)
    cli.add_argument("--memmap", type=Path, action="append", required=True)
    cli.add_argument("--known-values", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY) or output.exists():
        raise ValueError("Private diagnostic output must be a new file outside the repository")
    acquisition = json.loads(args.acquisition.read_text(encoding="utf-8-sig"))
    expected_size = int(acquisition["raw_logical_bytes"])
    expected_raw_sha = str(acquisition["raw_sha256"]).upper()
    expected_archive_sha = args.archive_sha256.upper()
    if sha256_file(args.archive) != expected_archive_sha:
        raise ValueError("Archive SHA-256 does not match")
    known = json.loads(args.known_values.read_text(encoding="utf-8-sig"))
    values = {key: known[key] for key in ("conversation_id", "prompt", "response")}
    if any(not isinstance(value, str) or not value for value in values.values()):
        raise ValueError("Independent ground truth is incomplete")
    needles = {f"{name}/{encoding}": value.encode(encoding)
               for name, value in values.items()
               for encoding in ("utf-8", "utf-16-le")}

    raw = bytearray(expected_size)
    position = 0
    with gzip.open(args.archive, "rb") as source:
        while block := source.read(8 * 1024 * 1024):
            end = position + len(block)
            if end > expected_size:
                raise ValueError("Decompressed image exceeds acquisition size")
            raw[position:end] = block
            position = end
    if position != expected_size:
        raise ValueError("Decompressed image size does not match")
    source = InMemoryRaw(raw)
    physical_counts, actual_size, actual_raw_sha = count_stream(source, needles)
    if actual_size != expected_size or actual_raw_sha != expected_raw_sha:
        raise ValueError("Decompressed image SHA-256 does not match")
    maps = [scan_map(source, expected_size, path.resolve(strict=True), needles)
            for path in args.memmap]
    result = {
        "method": "post-hoc exact synthetic-value diagnostic; not blind turn reconstruction",
        "ground_truth_supplied": True,
        "archive_sha256": expected_archive_sha,
        "raw_sha256": actual_raw_sha,
        "raw_bytes": actual_size,
        "physical_counts": physical_counts,
        "renderer_maps": maps,
        "warning": "Physical hits lack process attribution; mapped counts can alias pages."
    }
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(json.dumps({"physical_counts": physical_counts,
                      "renderer_counts": [{"mapfile": row["mapfile"],
                                           "counts": row["mapped_occurrence_counts"]}
                                          for row in maps],
                      "archive_and_raw_verified": True}))


if __name__ == "__main__":
    main()
