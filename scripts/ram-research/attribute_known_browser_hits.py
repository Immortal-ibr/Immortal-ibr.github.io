"""Post-hoc exact-value counts in selected processes' acquired user mappings.

The values are read from private synthetic trial observations, never printed.
These counts diagnose physical residue; they are not a blind turn parser.
"""

import argparse
import json
from pathlib import Path

from count_known_raw_gzip import known_values, load


USER_LIMIT = 1 << 47


def count_occurrences(data: bytes, needle: bytes) -> int:
    count = 0
    cursor = 0
    while (offset := data.find(needle, cursor)) != -1:
        count += 1
        cursor = offset + 1
    return count


def scan_map(image: Path, mapfile: Path, needles: dict[str, bytes]) -> dict:
    rows = load(mapfile)
    counts = dict.fromkeys(needles, 0)
    first_hits = {}
    scanned_rows = 0
    scanned_bytes = 0
    image_length = image.stat().st_size
    with image.open("rb", buffering=0) as source:
        for row in rows:
            physical, virtual, size = (int(row[name]) for name in ("Physical", "Virtual", "Size"))
            if virtual >= USER_LIMIT or size <= 0 or physical < 0 or physical + size > image_length:
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
            "mapped_occurrence_counts": counts,
            "first_hits_private": first_hits}


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, action="append", required=True)
    cli.add_argument("--submission", type=Path, required=True)
    cli.add_argument("--observation", type=Path, required=True)
    cli.add_argument("--ids", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    values = known_values(load(args.submission), load(args.observation), load(args.ids))
    needles = {f"{name}/{encoding}": value.encode(encoding)
               for name, value in values.items() for encoding in ("utf-8", "utf-16-le")}
    result = {
        "method": "Post-hoc known-value scan of selected image-derived user mappings; not blind reconstruction",
        "raw_image_length": args.image.stat().st_size,
        "note": "Counts may duplicate aliased physical pages and do not prove a process originated the bytes",
        "process_maps": [scan_map(args.image, mapfile, needles) for mapfile in args.memmap],
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
