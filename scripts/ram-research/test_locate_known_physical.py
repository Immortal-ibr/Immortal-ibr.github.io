import gzip
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from locate_known_physical import find_offsets, inspect


class LocateKnownPhysicalTests(unittest.TestCase):
    def test_finds_cross_chunk_hit_once(self):
        raw = b"abc" + b"SYNTHETIC" + b"xx" + b"SYNTHETIC"
        offsets, size, digest = find_offsets(io.BytesIO(raw), b"SYNTHETIC", chunk_size=5)
        self.assertEqual(offsets, [3, 14])
        self.assertEqual(size, len(raw))
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest().upper())

    def test_verified_context_result_does_not_include_value(self):
        value = "synthetic answer"
        raw = b'"textTail": "' + value.encode() + b'"'
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "synthetic.raw.gz"
            with gzip.open(archive, "wb") as target:
                target.write(raw)
            result = inspect(
                archive,
                hashlib.sha256(archive.read_bytes()).hexdigest(),
                len(raw),
                hashlib.sha256(raw).hexdigest(),
                value,
            )
        self.assertEqual(len(result["hits"]), 1)
        self.assertEqual(result["hits"][0]["physical_offset"], len(b'"textTail": "'))
        self.assertTrue(result["hits"][0]["textTail_json_evidence"]["hit_inside_parsed_textTail_string"])
        self.assertTrue(result["hits"][0]["textTail_json_evidence"]["exact_value_in_decoded_textTail"])
        self.assertNotIn(value, str(result))

    def test_recognizes_probe_object_without_returning_its_text(self):
        value = "synthetic answer"
        observation = {
            "url": "https://chatgpt.com/c/synthetic",
            "user": ["synthetic prompt"],
            "assistant": [value],
            "textTail": "ChatGPT said:\n" + value,
        }
        raw = json.dumps(observation, separators=(",", ":")).encode()
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "observation.raw.gz"
            with gzip.open(archive, "wb") as target:
                target.write(raw)
            result = inspect(
                archive,
                hashlib.sha256(archive.read_bytes()).hexdigest(),
                len(raw),
                hashlib.sha256(raw).hexdigest(),
                value,
            )
        self.assertEqual(len(result["hits"]), 2)
        self.assertTrue(any(
            hit["probe_object_evidence"]["parsed_probe_object_shape"]
            and hit["probe_object_evidence"]["answer_in_textTail"]
            for hit in result["hits"]
        ))
        self.assertNotIn(value, str(result))


if __name__ == "__main__":
    unittest.main()
