"""Extract one previously identified physical span from a gzip RAM image.

This is a presentation aid, not a search or parser. Supply the physical offset,
length, and SHA-256 recorded by the independent bounded-record parser. The
output is written only if the source bytes match that expected digest.
"""

import argparse
import gzip
import hashlib
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive", type=Path)
    ap.add_argument("physical_offset", type=int)
    ap.add_argument("length", type=int)
    ap.add_argument("expected_sha256")
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    if args.physical_offset < 0 or not 0 < args.length <= 1024 * 1024:
        ap.error("expected a nonnegative offset and a span of 1 to 1048576 bytes")
    if args.output.exists():
        ap.error(f"refusing to overwrite {args.output}")

    with gzip.open(args.archive, "rb") as source:
        source.seek(args.physical_offset)
        data = source.read(args.length)

    actual = hashlib.sha256(data).hexdigest()
    if len(data) != args.length or actual.lower() != args.expected_sha256.lower():
        raise SystemExit(
            f"span failed verification: bytes={len(data)}, sha256={actual}"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"source={args.archive}")
    print(f"physical_offset={args.physical_offset} (0x{args.physical_offset:x})")
    print(f"length={len(data)} (0x{len(data):x})")
    print(f"sha256={actual}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
