import gzip
import hashlib
import tempfile
import unittest
from pathlib import Path

from scan_physical_sse import scan_physical_sse


class PhysicalSseScanTests(unittest.TestCase):
    def test_accepts_complete_synthetic_event(self):
        raw = b"\0" * 80 + b'data: {"synthetic":true}\n\n' + b"\0" * 80
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "synthetic.raw.gz"
            with gzip.open(archive, "wb") as target:
                target.write(raw)
            result = scan_physical_sse(
                archive,
                hashlib.sha256(archive.read_bytes()).hexdigest(),
                len(raw),
                hashlib.sha256(raw).hexdigest(),
            )
        self.assertEqual(result["stats"]["signature_hits"], 1)
        self.assertEqual(result["stats"]["complete_event_occurrences"], 1)
        self.assertEqual(result["unique_complete_records"], 1)
        self.assertFalse(result["physical_scan_scope"]["process_attribution"])

    def test_rejects_wrong_raw_digest(self):
        raw = b'data: {"synthetic":true}\n\n'
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "synthetic.raw.gz"
            with gzip.open(archive, "wb") as target:
                target.write(raw)
            with self.assertRaisesRegex(ValueError, "does not match the acquisition"):
                scan_physical_sse(
                    archive,
                    hashlib.sha256(archive.read_bytes()).hexdigest(),
                    len(raw),
                    "0" * 64,
                )


if __name__ == "__main__":
    unittest.main()
