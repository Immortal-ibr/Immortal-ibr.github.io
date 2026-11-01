"""Verify a private guest archive and decompress it without replacing any file."""

import argparse
import gzip
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--guest-manifest", type=Path, required=True)
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    archive = args.archive.resolve(strict=True)
    image = args.image.resolve()
    partial = image.with_suffix(image.suffix + ".partial")
    output = args.output.resolve()
    if any(p.exists() for p in (image, partial, output)):
        raise SystemExit("Refusing to replace an image, partial file or verification")
    manifest = json.loads(args.guest_manifest.read_text(encoding="utf-8-sig"))
    expected_length = int(manifest["raw_logical_bytes"])
    expected_hash = manifest["raw_sha256_from_acquisition"].lower()
    started = time.monotonic()
    archive_hash = sha256_file(archive)
    if archive.stat().st_size != int(manifest["archive_bytes"]) or archive_hash != manifest["archive_sha256"].lower():
        raise SystemExit("Transferred archive does not match the guest's length and hash")
    digest = hashlib.sha256()
    length = 0
    with gzip.open(archive, "rb") as source, partial.open("xb") as destination:
        while block := source.read(8 * 1024 * 1024):
            length += len(block)
            if length > expected_length:
                raise ValueError("Decompressed image exceeds the source length")
            digest.update(block)
            destination.write(block)
    if length != expected_length or digest.hexdigest() != expected_hash:
        raise ValueError("Decompressed image differs from acquisition; partial retained")
    partial.rename(image)
    result = {"verified_utc": datetime.now(timezone.utc).isoformat(),
              "trial_id": manifest["trial_id"], "archive_sha256": archive_hash,
              "archive_bytes": archive.stat().st_size, "raw_sha256": digest.hexdigest(),
              "raw_logical_bytes": length, "copy_verified": True,
              "decompressed_digest_verified": True, "elapsed_seconds": time.monotonic() - started,
              "archive_deleted": False}
    with output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
