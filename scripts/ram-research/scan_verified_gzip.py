"""Run an unchanged RAM parser against a hash-verified gzip archive.

The archive is read sequentially once to verify the acquisition SHA-256 and
build indexed_gzip's seek index. The parser then sees the decompressed physical
address space through seek/read, without writing another raw image. Both the
archive and every parser output are private: a complete record may contain
account data or unrelated conversations.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import indexed_gzip

from chrome_state_records import scan as scan_chrome_state
from bounded_json import scan as scan_stream_item
from browser_json_envelopes import scan as scan_browser_envelopes
from cli_request_core_turns import recover as recover_cli_request_core
from cli_rpc_records import scan as scan_cli_rpc
from sse_event_records import scan as scan_sse_events


PARSERS = {
    "chrome-state": scan_chrome_state,
    "stream-item": scan_stream_item,
    "browser-envelopes": scan_browser_envelopes,
    "cli-request-core": recover_cli_request_core,
    "cli-rpc": scan_cli_rpc,
    "sse-events": scan_sse_events,
}
REPOSITORY = Path(__file__).resolve().parents[2]


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def scan_archive(archive, rows, expected_size, expected_raw_sha256, parser):
    with indexed_gzip.IndexedGzipFile(filename=str(archive)) as source:
        digest = hashlib.sha256()
        actual_size = 0
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
            actual_size += len(block)
        actual_raw_sha256 = digest.hexdigest().upper()
        if actual_size != expected_size or actual_raw_sha256 != expected_raw_sha256.upper():
            raise ValueError("Decompressed archive does not match the acquisition record")
        source.seek(0)
        result = PARSERS[parser](source, rows, expected_size)
    return result, actual_raw_sha256


class InMemoryRaw:
    """Seekable physical image backed by RAM, not by a temporary raw file."""

    def __init__(self, buffer):
        self.buffer = buffer
        self.position = 0

    def seek(self, position):
        if position < 0 or position > len(self.buffer):
            raise ValueError("Seek outside the verified physical image")
        self.position = position
        return position

    def read(self, size):
        end = min(len(self.buffer), self.position + size)
        block = bytes(memoryview(self.buffer)[self.position:end])
        self.position = end
        return block


def scan_archive_in_memory(archive, rows, expected_size, expected_raw_sha256, parser):
    """Use host RAM when random access to indexed gzip would be very slow."""
    raw = bytearray(expected_size)
    digest = hashlib.sha256()
    position = 0
    with gzip.open(archive, "rb") as source:
        while block := source.read(8 * 1024 * 1024):
            end = position + len(block)
            if end > expected_size:
                raise ValueError("Decompressed image exceeds acquisition size")
            raw[position:end] = block
            digest.update(block)
            position = end
    actual_raw_sha256 = digest.hexdigest().upper()
    if position != expected_size or actual_raw_sha256 != expected_raw_sha256.upper():
        raise ValueError("Decompressed archive does not match the acquisition record")
    result = PARSERS[parser](InMemoryRaw(raw), rows, expected_size)
    return result, actual_raw_sha256


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, required=True)
    cli.add_argument("--acquisition", type=Path, required=True)
    cli.add_argument("--archive-sha256", required=True)
    cli.add_argument("--parser", choices=sorted(PARSERS), required=True)
    cli.add_argument("--backend", choices=("indexed-gzip", "memory"), default="indexed-gzip")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Unfiltered RAM parser output must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    acquisition = json.loads(args.acquisition.read_text(encoding="utf-8-sig"))
    expected_size = int(acquisition["raw_logical_bytes"])
    expected_raw_sha256 = str(acquisition["raw_sha256"]).upper()
    if len(expected_raw_sha256) != 64 or len(args.archive_sha256) != 64:
        raise ValueError("Expected SHA-256 values must be 64 hex characters")
    actual_archive_sha256 = sha256_file(args.archive)
    if actual_archive_sha256 != args.archive_sha256.upper():
        raise ValueError("Archive bytes do not match the verified archive SHA-256")
    rows = json.loads(args.memmap.read_text(encoding="utf-8-sig"))
    run_scan = scan_archive_in_memory if args.backend == "memory" else scan_archive
    result, actual_raw_sha256 = run_scan(args.archive, rows, expected_size, expected_raw_sha256, args.parser)
    result["archive_replay"] = {
        "adapter": ("verified gzip expanded in host RAM" if args.backend == "memory"
                    else "indexed-gzip 1.10.3") + "; parser itself unchanged",
        "compressed_sha256": actual_archive_sha256,
        "decompressed_sha256": actual_raw_sha256,
        "decompressed_bytes": expected_size,
    }
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, ensure_ascii=True)
        target.write("\n")
    print(json.dumps({
        "parser": args.parser,
        "signature_hits": result.get("stats", {}).get("signature_hits", 0),
        "unique_complete_records": result["unique_complete_records"],
        "candidate_count": result.get("join", {}).get("candidate_count"),
        "archive_verified": True,
        "raw_verified": True,
    }))


if __name__ == "__main__":
    main()
