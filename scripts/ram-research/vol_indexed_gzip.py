"""Run a local Volatility 3 checkout against an indexed gzip RAM image.

Volatility can open .gz images, but repeated random seeks through a normal
gzip stream are costly. This wrapper substitutes indexed_gzip only for the
specified image; Volatility's other compressed resources keep their normal
reader. It never writes an expanded memory image.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import indexed_gzip


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_index(image: Path, index: Path) -> None:
    if index.exists():
        return
    if not index.parent.is_dir():
        raise ValueError(f"Index directory does not exist: {index.parent}")
    temporary = index.with_name(index.name + ".partial")
    if temporary.exists():
        raise ValueError(f"Refusing to replace partial index: {temporary}")
    try:
        with indexed_gzip.IndexedGzipFile(filename=str(image)) as stream:
            stream.raw.build_full_index()
            stream.raw.export_index(str(temporary))
        os.replace(temporary, index)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--vol", type=Path, required=True)
    parser.add_argument("--sha256", help="Expected SHA-256 of compressed image")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("vol_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    image = args.image.resolve(strict=True)
    vol = args.vol.resolve(strict=True)
    index = args.index.resolve()
    if image.suffix.lower() != ".gz":
        parser.error("--image must be a .gz file")
    if args.sha256 and sha256_file(image).lower() != args.sha256.lower():
        parser.error("Compressed-image SHA-256 mismatch")

    ensure_index(image, index)
    if args.build_only:
        print(f"Indexed {image.stat().st_size} compressed bytes", file=sys.stderr)
        return

    vol_args = args.vol_args
    if vol_args and vol_args[0] == "--":
        vol_args = vol_args[1:]
    if not vol_args:
        parser.error("Volatility plugin and arguments are required after --")

    original_gzip_file = gzip.GzipFile
    def open_gzip(*pargs: object, **kwargs: object):
        fileobj = kwargs.get("fileobj")
        source_url = fileobj.geturl() if hasattr(fileobj, "geturl") else None
        source_path = None
        if source_url and urllib.parse.urlparse(source_url).scheme == "file":
            source_path = Path(
                urllib.request.url2pathname(urllib.parse.urlparse(source_url).path)
            ).resolve()
        elif getattr(fileobj, "name", None):
            source_path = Path(fileobj.name).resolve()
        if source_path == image:
            print("Using indexed gzip reader for memory image", file=sys.stderr)
            return indexed_gzip.IndexedGzipFile(
                fileobj=fileobj, mode=kwargs.get("mode", "rb"), index_file=str(index)
            )
        return original_gzip_file(*pargs, **kwargs)

    gzip.GzipFile = open_gzip
    sys.path.insert(0, str(vol.parent))
    sys.argv = [str(vol), "-f", str(image), *vol_args]
    from volatility3.cli import main as volatility_main

    volatility_main()


if __name__ == "__main__":
    main()
