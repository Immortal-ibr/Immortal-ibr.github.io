"""Materialize a verified WinPmem gzip as a temporary NTFS sparse raw image.

This is for tools that require a seekable flat file. Whole all-zero blocks are
holes; no memory content is changed. The output is private and never published.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from verify_direct_gzip import hash_file


REPOSITORY = Path(__file__).resolve().parents[2]
BLOCK = 1024 * 1024
SAFETY_FREE_BYTES = 1024 * 1024 * 1024


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--verification", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--nonzero-block-upper-bound", type=int, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    partial = output.with_suffix(output.suffix + ".partial")
    if output.is_relative_to(REPOSITORY) or partial.is_relative_to(REPOSITORY):
        raise ValueError("Full raw memory must stay outside the repository")
    if output.exists() or partial.exists():
        raise FileExistsError("Raw or partial image already exists")
    verification = json.loads(args.verification.read_text(encoding="utf-8-sig"))
    if not (verification["copy_verified_against_guest_sha256"]
            and verification["gzip_stream_read_to_eof"]):
        raise ValueError("Archive has not been fully verified")
    archive = args.archive.resolve(strict=True)
    if (archive.stat().st_size != verification["archive_bytes"]
            or hash_file(archive) != verification["archive_sha256"]):
        raise ValueError("Archive changed since verification")
    if shutil.disk_usage(output.parent).free < args.nonzero_block_upper_bound + SAFETY_FREE_BYTES:
        raise OSError("Insufficient free space for sparse raw plus 1 GiB reserve")
    with partial.open("xb"):
        pass
    try:
        subprocess.run(["fsutil", "sparse", "setflag", str(partial)], check=True,
                       capture_output=True, text=True)
        digest = hashlib.sha256()
        length = written = zero_blocks = 0
        with gzip.open(archive, "rb") as source, partial.open("r+b") as target:
            while block := source.read(BLOCK):
                digest.update(block)
                length += len(block)
                if block.count(0) == len(block):
                    target.seek(len(block), 1)
                    zero_blocks += 1
                else:
                    target.write(block)
                    written += len(block)
            target.truncate(length)
        if (length != verification["raw_logical_bytes"]
                or digest.hexdigest().upper() != verification["raw_sha256"]):
            raise ValueError("Sparse raw differs from verified decompressed stream")
        partial.rename(output)
    except BaseException:
        # This exact partial file was created above; no existing user file is touched.
        partial.unlink(missing_ok=True)
        raise
    print(json.dumps({"output": str(output), "logical_bytes": length,
                      "written_nonzero_block_bytes": written,
                      "zero_blocks_skipped": zero_blocks,
                      "raw_sha256": digest.hexdigest().upper(),
                      "ntfs_sparse": True}))


if __name__ == "__main__":
    main()
