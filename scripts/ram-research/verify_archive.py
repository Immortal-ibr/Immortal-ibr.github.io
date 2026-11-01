"""Compress a private RAM image and verify a full decompressed SHA-256 round trip.

No image is deleted. Private output paths and manifest are not public artifacts.
Requires the separately installed zstandard Python package.
"""

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import zstandard

BLOCK_SIZE = 8 * 1024 * 1024


def digest_stream(source):
    digest = hashlib.sha256()
    length = 0
    while block := source.read(BLOCK_SIZE):
        digest.update(block)
        length += len(block)
    return length, digest.hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", required=True, type=Path)
    cli.add_argument("--archive", required=True, type=Path)
    cli.add_argument("--manifest", required=True, type=Path)
    cli.add_argument("--level", type=int, default=3)
    args = cli.parse_args()
    image = args.image.resolve(strict=True)
    archive = args.archive.resolve()
    manifest = args.manifest.resolve()
    partial = archive.with_suffix(archive.suffix + ".partial")
    if any(path.exists() for path in (archive, partial, manifest)):
        raise SystemExit("Refusing to overwrite an archive, partial file, or manifest")
    if len({image, archive, partial, manifest}) != 4:
        raise SystemExit("Input and output paths must differ")
    start = time.monotonic()
    image_stat = image.stat()
    compressor = zstandard.ZstdCompressor(level=args.level, threads=2, write_checksum=True)
    digest = hashlib.sha256()
    length = 0
    with image.open("rb") as source, partial.open("xb") as target:
        with compressor.stream_writer(target, closefd=False, size=image_stat.st_size) as stream:
            while block := source.read(BLOCK_SIZE):
                digest.update(block)
                length += len(block)
                stream.write(block)
    final_stat = image.stat()
    if image_stat.st_size != final_stat.st_size or image_stat.st_mtime_ns != final_stat.st_mtime_ns:
        raise SystemExit("Input changed during compression; partial archive retained")
    with partial.open("rb") as source:
        with zstandard.ZstdDecompressor().stream_reader(source) as stream:
            verified_length, verified_hash = digest_stream(stream)
    if verified_length != length or verified_hash != digest.hexdigest():
        raise SystemExit("Round-trip verification failed; raw and partial archive retained")
    with partial.open("rb") as source:
        archive_length, archive_hash = digest_stream(source)
    partial.rename(archive)
    result = {
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "image_private_path": str(image),
        "archive_private_path": str(archive),
        "raw_logical_bytes": length,
        "raw_sha256": verified_hash,
        "archive_bytes": archive_length,
        "archive_sha256": archive_hash,
        "decompressed_digest_verified": True,
        "compression": "zstandard",
        "zstandard_version": zstandard.__version__,
        "level": args.level,
        "elapsed_seconds": time.monotonic() - start,
        "raw_deleted": False,
    }
    with manifest.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    print(json.dumps({key: value for key, value in result.items() if not key.endswith("_path")}, indent=2))


if __name__ == "__main__":
    main()
