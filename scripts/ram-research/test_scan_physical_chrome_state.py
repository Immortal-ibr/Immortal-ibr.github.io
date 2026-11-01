import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scan_physical_chrome_state import scan_physical


class PhysicalChromeStateScanTests(unittest.TestCase):
    def test_scans_verified_bytes_without_process_attribution(self):
        state = {
            "backendConversationId": "synthetic-conversation",
            "messages": [
                {"id": "synthetic-user", "role": "user", "content": "sample input"},
                {"id": "synthetic-assistant", "role": "assistant", "content": "sample output"},
            ],
        }
        raw = b"\0" * 100 + json.dumps(state, separators=(",", ":")).encode() + b"\0" * 100
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "synthetic.raw.gz"
            with gzip.open(archive, "wb") as target:
                target.write(raw)
            result = scan_physical(
                archive,
                hashlib.sha256(archive.read_bytes()).hexdigest(),
                len(raw),
                hashlib.sha256(raw).hexdigest(),
            )
        self.assertEqual(result["unique_complete_records"], 1)
        self.assertEqual(result["records"][0]["state"], state)
        self.assertFalse(result["physical_scan_scope"]["process_attribution"])
        self.assertFalse(result["physical_scan_scope"]["virtual_adjacency_established"])

    def test_rejects_wrong_archive_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "synthetic.raw.gz"
            with gzip.open(archive, "wb") as target:
                target.write(b"example")
            with self.assertRaisesRegex(ValueError, "Archive SHA-256"):
                scan_physical(archive, "0" * 64, 7, hashlib.sha256(b"example").hexdigest())

    def test_flat_scan_does_not_reassemble_a_scattered_record(self):
        state = {
            "backendConversationId": "synthetic-conversation",
            "messages": [{"id": "u", "role": "user", "content": "sample input"}],
        }
        encoded = json.dumps(state, separators=(",", ":")).encode()
        raw = b"\0" * 100 + encoded[:60] + b"\0" * 4096 + encoded[60:] + b"\0" * 100
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "scattered.raw.gz"
            with gzip.open(archive, "wb") as target:
                target.write(raw)
            result = scan_physical(
                archive,
                hashlib.sha256(archive.read_bytes()).hexdigest(),
                len(raw),
                hashlib.sha256(raw).hexdigest(),
            )
        self.assertEqual(result["stats"]["signature_hits"], 1)
        self.assertEqual(result["unique_complete_records"], 0)


if __name__ == "__main__":
    unittest.main()
