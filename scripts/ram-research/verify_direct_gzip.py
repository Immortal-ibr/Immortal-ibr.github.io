"""Verify a directly gzip-streamed WinPmem acquisition without expanding it.

Checks the guest's compressed size/SHA-256 against the transferred file, then
reads to gzip EOF (including CRC/size validation) to record decompressed size
and SHA-256. This direct-stream mode has no independent guest raw-image hash.
"""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--acquisition", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Full acquisition verification stays outside the repository")
    if output.exists():
        raise FileExistsError(output)
    acquisition = json.loads(args.acquisition.read_text(encoding="utf-8-sig"))
    if acquisition["status"] != "captured_unvalidated" or acquisition["exit_code"] != 0:
        raise ValueError("Not a successful direct-gzip acquisition")
    archive = args.archive.resolve(strict=True)
    archive_sha256 = hash_file(archive)
    if (archive.stat().st_size != int(acquisition["archive_bytes"])
            or archive_sha256 != acquisition["archive_sha256"].upper()):
        raise ValueError("Host archive does not match the guest acquisition")
    raw_sha256 = hashlib.sha256()
    raw_size = 0
    with gzip.open(archive, "rb") as source:
        while block := source.read(8 * 1024 * 1024):
            raw_sha256.update(block)
            raw_size += len(block)
    result = {
        "trial_id": acquisition["trial_id"],
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": archive_sha256,
        "copy_verified_against_guest_sha256": True,
        "gzip_stream_read_to_eof": True,
        "raw_logical_bytes": raw_size,
        "raw_sha256": raw_sha256.hexdigest().upper(),
        "raw_digest_source": "host decompression of the guest's direct gzip stream",
        "independent_guest_raw_digest_available": False,
    }
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
