"""Synthetic regressions for the hash-verified gzip seek adapter."""

import gzip
import hashlib
import io
from pathlib import Path
import tempfile
import unittest

from chrome_state_records import scan
from browser_json_envelopes import scan as scan_browser_envelopes
from scan_verified_gzip import scan_archive, scan_archive_in_memory


class VerifiedGzipTests(unittest.TestCase):
    def test_chrome_state_matches_the_same_raw_bytes(self):
        record = (b'{"backendConversationId":"synthetic-thread",'
                  b'"messages":[{"id":"m1","role":"user",'
                  b'"content":"synthetic prompt"}]}')
        raw = b"\x00" * 32 + record + b"\x00" * 32
        rows = [{"Virtual": 4096, "Physical": 0, "Size": len(raw)}]
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "synthetic.raw.gz"
            with archive.open("wb") as target:
                with gzip.GzipFile(fileobj=target, mode="wb", mtime=0) as compressed:
                    compressed.write(raw)
            replay, digest = scan_archive(
                archive, rows, len(raw), hashlib.sha256(raw).hexdigest(), "chrome-state"
            )
            self.assertEqual(replay, scan(io.BytesIO(raw), rows, len(raw)))
            self.assertEqual(digest, hashlib.sha256(raw).hexdigest().upper())
            self.assertEqual(replay["unique_complete_records"], 1)
            memory_replay, memory_digest = scan_archive_in_memory(
                archive, rows, len(raw), hashlib.sha256(raw).hexdigest(), "chrome-state"
            )
            self.assertEqual(memory_replay, replay)
            self.assertEqual(memory_digest, digest)

    def test_wrong_raw_hash_or_size_fails_closed(self):
        raw = b"synthetic physical bytes"
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "synthetic.raw.gz"
            archive.write_bytes(gzip.compress(raw, mtime=0))
            with self.assertRaisesRegex(ValueError, "does not match"):
                scan_archive(archive, [], len(raw), "0" * 64, "chrome-state")
            with self.assertRaisesRegex(ValueError, "does not match"):
                scan_archive(archive, [], len(raw) + 1,
                             hashlib.sha256(raw).hexdigest(), "chrome-state")
            with self.assertRaisesRegex(ValueError, "does not match"):
                scan_archive_in_memory(archive, [], len(raw), "0" * 64, "chrome-state")
            with self.assertRaisesRegex(ValueError, "exceeds acquisition size"):
                scan_archive_in_memory(archive, [], len(raw) - 1,
                                       hashlib.sha256(raw).hexdigest(), "chrome-state")

    def test_browser_envelope_matches_the_same_raw_bytes(self):
        record = (b'{"action":"next","messages":[],"conversation_id":'
                  b'"synthetic-conversation"}')
        raw = b"\x00" * 11 + record + b"\x00" * 19
        rows = [{"Virtual": 4096, "Physical": 0, "Size": len(raw)}]
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "synthetic.raw.gz"
            archive.write_bytes(gzip.compress(raw, mtime=0))
            replay, _ = scan_archive(archive, rows, len(raw),
                                     hashlib.sha256(raw).hexdigest(),
                                     "browser-envelopes")
            self.assertEqual(replay, scan_browser_envelopes(io.BytesIO(raw), rows, len(raw)))
            self.assertEqual(replay["unique_complete_records"], 1)


if __name__ == "__main__":
    unittest.main()
