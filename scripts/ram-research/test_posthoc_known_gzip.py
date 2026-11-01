"""Synthetic-only checks for the compressed-image known-value adapter."""

import io
import json
from pathlib import Path
import tempfile
import unittest

from posthoc_known_gzip import scan_map


class KnownGzipMapTests(unittest.TestCase):
    def test_mapped_counts_use_physical_bytes_and_preserve_virtual_address(self):
        raw = b"000prompt000answer000"
        rows = [{"Physical": 3, "Virtual": 0x1000, "Size": 6},
                {"Physical": 12, "Virtual": 0x2000, "Size": 6}]
        needles = {"prompt/utf-8": b"prompt", "response/utf-8": b"answer"}
        with tempfile.TemporaryDirectory() as temporary:
            mapfile = Path(temporary) / "map.json"
            mapfile.write_text(json.dumps(rows), encoding="utf-8")
            result = scan_map(io.BytesIO(raw), len(raw), mapfile, needles)
        self.assertEqual(result["mapped_occurrence_counts"],
                         {"prompt/utf-8": 1, "response/utf-8": 1})
        self.assertEqual(result["first_hits_private"]["prompt/utf-8"],
                         {"virtual": 0x1000, "physical": 3, "byte_length": 6})
        self.assertEqual(result["first_hits_private"]["response/utf-8"],
                         {"virtual": 0x2000, "physical": 12, "byte_length": 6})


if __name__ == "__main__":
    unittest.main()
