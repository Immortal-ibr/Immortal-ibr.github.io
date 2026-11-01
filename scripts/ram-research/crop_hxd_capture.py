"""Crop an actual HxD screenshot without changing pixels in the kept region."""

import argparse
import hashlib
from pathlib import Path

from PIL import Image


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("destination", type=Path)
    ap.add_argument("left", type=int)
    ap.add_argument("top", type=int)
    ap.add_argument("right", type=int)
    ap.add_argument("bottom", type=int)
    args = ap.parse_args()

    if args.destination.exists():
        ap.error(f"refusing to overwrite {args.destination}")
    with Image.open(args.source) as image:
        if not (0 <= args.left < args.right <= image.width and
                0 <= args.top < args.bottom <= image.height):
            ap.error(f"crop outside {image.size}")
        cropped = image.crop((args.left, args.top, args.right, args.bottom))
        cropped.save(args.destination)
        print(f"source_sha256={hashlib.sha256(args.source.read_bytes()).hexdigest()}")
        print(f"crop=({args.left}, {args.top}, {args.right}, {args.bottom})")
        print(f"size={cropped.size}")
        print(f"public_sha256={hashlib.sha256(args.destination.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
