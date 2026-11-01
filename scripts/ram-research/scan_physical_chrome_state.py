"""Exploratory flat-physical scan of a hash-verified WinPmem gzip image.

This deliberately does *not* assign recovered bytes to a process. Physical
adjacency is not virtual adjacency, so a complete record here is a lead to
investigate, not proof that an active renderer retained it. Output stays private
because valid records may contain unrelated account content.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scan_verified_gzip import REPOSITORY, scan_archive_in_memory, sha256_file


def scan_physical(archive, compressed_sha256, raw_size, raw_sha256):
    actual_compressed_sha256 = sha256_file(archive)
    if actual_compressed_sha256 != compressed_sha256.upper():
        raise ValueError("Archive SHA-256 does not match the acquisition")
    # The scanner receives an identity mapping only to reuse the unchanged
    # bounded-record grammar. This is *not* a Volatility process memmap.
    physical_identity = [{"Virtual": 0, "Physical": 0, "Size": raw_size}]
    result, actual_raw_sha256 = scan_archive_in_memory(
        archive, physical_identity, raw_size, raw_sha256, "chrome-state"
    )
    result["method"] = "exploratory bounded Chrome-state scan of flat physical RAM"
    result["physical_scan_scope"] = {
        "process_attribution": False,
        "virtual_adjacency_established": False,
        "ground_truth_supplied": False,
        "identity_row_is_only_a_scanning_adapter": True,
    }
    result["archive_replay"] = {
        "compressed_sha256": actual_compressed_sha256,
        "decompressed_sha256": actual_raw_sha256,
        "decompressed_bytes": raw_size,
        "adapter": "verified gzip expanded in host RAM; no raw disk image written",
    }
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--archive-sha256", required=True)
    cli.add_argument("--raw-size", type=int, required=True)
    cli.add_argument("--raw-sha256", required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.raw_size <= 0:
        raise ValueError("Raw size must be positive")
    for digest in (args.archive_sha256, args.raw_sha256):
        if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ValueError("Expected SHA-256 values must be 64 hex digits")
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Unfiltered memory records must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    result = scan_physical(
        args.archive, args.archive_sha256, args.raw_size, args.raw_sha256
    )
    result["scan_finished_utc"] = datetime.now(timezone.utc).isoformat()
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, ensure_ascii=True)
        target.write("\n")
    print(json.dumps({
        "signature_hits": result.get("stats", {}).get("signature_hits", 0),
        "complete_record_occurrences": result.get("stats", {}).get("complete_record_occurrences", 0),
        "unique_complete_records": result["unique_complete_records"],
        "archive_verified": True,
        "raw_verified": True,
        "output_is_private": True,
    }))


if __name__ == "__main__":
    main()
