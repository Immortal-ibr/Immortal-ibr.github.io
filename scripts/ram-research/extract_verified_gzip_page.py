"""Carve one 4 KiB physical page containing a previously verified record."""

import argparse
import gzip
import hashlib
from pathlib import Path


PAGE_SIZE = 4096


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive", type=Path)
    ap.add_argument("page_physical_offset", type=lambda value: int(value, 0))
    ap.add_argument("record_displacement", type=lambda value: int(value, 0))
    ap.add_argument("record_length", type=lambda value: int(value, 0))
    ap.add_argument("expected_record_sha256")
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    if args.page_physical_offset < 0 or args.page_physical_offset % PAGE_SIZE:
        ap.error("physical page offset must be nonnegative and 4 KiB aligned")
    if not (0 <= args.record_displacement < PAGE_SIZE and
            0 < args.record_length <= PAGE_SIZE - args.record_displacement):
        ap.error("record must fit inside the extracted page")
    if args.output.exists():
        ap.error(f"refusing to overwrite {args.output}")

    with gzip.open(args.archive, "rb") as source:
        source.seek(args.page_physical_offset)
        page = source.read(PAGE_SIZE)
    if len(page) != PAGE_SIZE:
        raise SystemExit(f"expected {PAGE_SIZE} page bytes, got {len(page)}")

    record = page[args.record_displacement:
                  args.record_displacement + args.record_length]
    record_sha = hashlib.sha256(record).hexdigest()
    if record_sha.lower() != args.expected_record_sha256.lower():
        raise SystemExit(f"record SHA-256 mismatch: {record_sha}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(page)
    print(f"page_physical=0x{args.page_physical_offset:x}")
    print(f"page_sha256={hashlib.sha256(page).hexdigest()}")
    print(f"record_offset_in_page=0x{args.record_displacement:x}")
    print(f"record_length=0x{args.record_length:x}")
    print(f"record_sha256={record_sha}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
