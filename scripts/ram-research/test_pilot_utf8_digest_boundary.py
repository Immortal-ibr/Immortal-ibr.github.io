"""Synthetic regression for the frozen pilot stream-item byte-digest boundary.

This deliberately leaves the historical parser unchanged. Its decoded JSON
character count is not a byte count when the original record contains an
unescaped multibyte UTF-8 character; accepted field values can still parse.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PARSER = (Path(__file__).resolve().parents[2] / "public" / "research"
          / "chatgpt-windows-ram" / "trial_iab_visible_002" / "parse_stream_items.py")
FIXTURE = PARSER.parents[1] / "PILOT_UTF8_DIGEST_BOUNDARY_20261001.json"


def run_fixture(embedded):
    payload = {"type": "stream-item", "encoded_item": embedded}
    record_bytes = json.dumps(payload, ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8")
    image_bytes = b"\x00" * 32 + record_bytes + b"\x00" * 64
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        image = root / "synthetic.raw"
        mapping = root / "synthetic-memmap.json"
        output = root / "parsed.json"
        image.write_bytes(image_bytes)
        mapping.write_text(json.dumps([{
            "Virtual": 4096, "Physical": 0, "Size": len(image_bytes)
        }]), encoding="utf-8")
        subprocess.run([sys.executable, str(PARSER), "--image", str(image),
                        "--memmap", str(mapping), "--output", str(output)],
                       check=True, capture_output=True, text=True)
        parsed = json.loads(output.read_text(encoding="utf-8"))
    return record_bytes, parsed


class PilotUtf8DigestBoundaryTests(unittest.TestCase):
    def test_public_fixture_matches_the_reproduced_bytes_and_digests(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            with self.subTest(encoded_item=case["encoded_item"]):
                raw, parsed = run_fixture(case["encoded_item"])
                self.assertEqual(len(raw), case["complete_record_utf8_bytes"])
                self.assertEqual(len(raw.decode("utf-8")),
                                 case["decoded_json_characters"])
                self.assertEqual(hashlib.sha256(raw).hexdigest().upper(),
                                 case["full_record_sha256"])
                self.assertEqual(parsed["records"][0]["record_sha256"].upper(),
                                 case["frozen_parser_record_sha256"])
                if "complete_record_utf8_hex" in case:
                    self.assertEqual(raw.hex().upper(), case["complete_record_utf8_hex"])

    def test_ascii_record_digest_matches_original_bytes(self):
        raw, parsed = run_fixture("synthetic ascii")
        self.assertEqual(parsed["unique_complete_records"], 1)
        self.assertEqual(parsed["records"][0]["record_sha256"],
                         hashlib.sha256(raw).hexdigest())

    def test_unescaped_multibyte_text_parses_but_digest_is_truncated(self):
        raw, parsed = run_fixture("synthetic café")
        self.assertEqual(parsed["unique_complete_records"], 1)
        self.assertEqual(parsed["records"][0]["payload"]["encoded_item"],
                         "synthetic café")
        self.assertNotEqual(parsed["records"][0]["record_sha256"],
                            hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main()
