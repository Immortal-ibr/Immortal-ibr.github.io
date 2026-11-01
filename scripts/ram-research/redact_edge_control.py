"""Make a documented, non-generative crop of the real Edge control screen.

Only the account greeting and profile avatar are covered. This is a screenshot
derivative, not a fabricated result panel or a replacement for the private
original. The original stays outside the repository.
"""

import argparse
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw


SOURCE_SHA256 = "25876b71e66be5db7a5f1a8f75faab5a849f86b9d19de0782710f2606bb1bac2"
CROP = (710, 170, 2160, 1125)
REDACTIONS = (
    (1325, 550, 1620, 600),  # Personalized account greeting.
    (725, 1060, 780, 1120),  # Account avatar in collapsed sidebar.
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to replace an existing screenshot derivative")
    if sha256(args.source) != SOURCE_SHA256:
        raise SystemExit("Source screenshot digest differs from the observed original")
    with Image.open(args.source) as source:
        if source.size != (2267, 1328):
            raise SystemExit("Unexpected source dimensions")
        derivative = source.crop(CROP).convert("RGB")
    draw = ImageDraw.Draw(derivative)
    for left, top, right, bottom in REDACTIONS:
        draw.rectangle(
            (left - CROP[0], top - CROP[1], right - CROP[0], bottom - CROP[1]),
            fill=(0, 0, 0),
        )
    derivative.save(args.output, format="PNG")
    print(f"PNG {derivative.width}x{derivative.height} SHA-256 {sha256(args.output)}")


if __name__ == "__main__":
    main()
