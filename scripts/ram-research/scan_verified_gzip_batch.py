"""Verify one private gzip image once, then run unchanged parsers on many maps.

Each --scan is PARSER MEMMAP OUTPUT. Only the seekable physical-image adapter
and scheduling are shared; no parser receives a known prompt, answer or ID.
Unfiltered output must stay outside the repository.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from scan_verified_gzip import InMemoryRaw, PARSERS, REPOSITORY, sha256_file


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--acquisition", type=Path, required=True)
    cli.add_argument("--archive-sha256", required=True)
    cli.add_argument("--scan", action="append", nargs=3, required=True,
                     metavar=("PARSER", "MEMMAP", "OUTPUT"))
    args = cli.parse_args()

    archive = args.archive.resolve(strict=True)
    acquisition = json.loads(args.acquisition.read_text(encoding="utf-8-sig"))
    expected_size = int(acquisition["raw_logical_bytes"])
    expected_raw_sha = str(acquisition["raw_sha256"]).upper()
    expected_archive_sha = args.archive_sha256.upper()
    if len(expected_raw_sha) != 64 or len(expected_archive_sha) != 64:
        raise ValueError("Expected digests must be SHA-256 hex strings")
    if sha256_file(archive) != expected_archive_sha:
        raise ValueError("Archive SHA-256 does not match")

    scans = []
    seen_outputs = set()
    for parser, memmap, output in args.scan:
        if parser not in PARSERS:
            raise ValueError(f"Unknown parser {parser}")
        map_path = Path(memmap).resolve(strict=True)
        output_path = Path(output).resolve()
        if output_path.is_relative_to(REPOSITORY):
            raise ValueError("Unfiltered RAM parser output must stay outside the repository")
        if output_path.exists() or output_path in seen_outputs:
            raise FileExistsError(output_path)
        seen_outputs.add(output_path)
        scans.append((parser, map_path, output_path))

    raw = bytearray(expected_size)
    digest = hashlib.sha256()
    position = 0
    with gzip.open(archive, "rb") as source:
        while block := source.read(8 * 1024 * 1024):
            end = position + len(block)
            if end > expected_size:
                raise ValueError("Decompressed image exceeds acquisition size")
            raw[position:end] = block
            digest.update(block)
            position = end
    actual_raw_sha = digest.hexdigest().upper()
    if position != expected_size or actual_raw_sha != expected_raw_sha:
        raise ValueError("Decompressed image does not match acquisition record")

    summaries = []
    for parser, map_path, output_path in scans:
        rows = json.loads(map_path.read_text(encoding="utf-8-sig"))
        result = PARSERS[parser](InMemoryRaw(raw), rows, expected_size)
        result["archive_replay"] = {
            "adapter": "verified gzip expanded once in host RAM; parser itself unchanged",
            "compressed_sha256": expected_archive_sha,
            "decompressed_sha256": actual_raw_sha,
            "decompressed_bytes": expected_size,
        }
        with output_path.open("x", encoding="utf-8") as target:
            json.dump(result, target, indent=2, ensure_ascii=True)
            target.write("\n")
        summaries.append({
            "parser": parser,
            "map": map_path.name,
            "output": output_path.name,
            "signature_hits": result.get("stats", {}).get("signature_hits", 0),
            "unique_complete_records": result.get("unique_complete_records", 0),
        })
        print(json.dumps(summaries[-1]), flush=True)
    print(json.dumps({"archive_verified": True, "raw_verified": True,
                      "scans_completed": len(summaries)}), flush=True)


if __name__ == "__main__":
    main()
