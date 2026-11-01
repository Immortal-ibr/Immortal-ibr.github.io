import hashlib
import io
import unittest

from count_known_raw_gzip import count_stream, known_values
from attribute_known_browser_hits import count_occurrences


class CountStreamTests(unittest.TestCase):
    def test_cross_chunk_and_overlapping_occurrences(self):
        data = b"0ababab1cafe2ab3"
        counts, length, digest = count_stream(
            io.BytesIO(data), {"overlap": b"aba", "boundary": b"cafe", "absent": b"xyz"}, 3
        )
        self.assertEqual(counts, {"overlap": 2, "boundary": 1, "absent": 0})
        self.assertEqual(length, len(data))
        self.assertEqual(digest, hashlib.sha256(data).hexdigest().upper())

    def test_empty_or_invalid_input(self):
        with self.assertRaises(ValueError):
            count_stream(io.BytesIO(b"x"), {}, 1)
        with self.assertRaises(ValueError):
            count_stream(io.BytesIO(b"x"), {"empty": b""}, 1)

    def test_mapped_occurrences_include_overlaps(self):
        self.assertEqual(count_occurrences(b"ababab", b"aba"), 2)
        self.assertEqual(count_occurrences(b"ababab", b"missing"), 0)

    def test_observed_synthetic_values_are_separate_from_ram_parser(self):
        prompt = "For the synthetic label cobalt-orbit-517, describe a fictional museum."
        conversation = "123e4567-e89b-12d3-a456-426614174000"
        user_id = "123e4567-e89b-12d3-a456-426614174001"
        assistant_id = "123e4567-e89b-12d3-a456-426614174002"
        values = known_values(
            {"prompt": prompt},
            {"page": {"url": f"https://chatgpt.com/c/{conversation}",
                      "textTail": prompt + " Answer: museum, Marrow Gleam."}},
            {"page": {"url": f"https://chatgpt.com/c/{conversation}",
                      "uuid_attribute_hits": [
                          {"tag": "LI", "name": "id", "value": user_id, "text": prompt},
                          {"tag": "LI", "name": "id", "value": assistant_id,
                           "text": "ChatGPT said: museum, Marrow Gleam."},
                      ]}},
        )
        self.assertEqual(values["conversation_id"], conversation)
        self.assertEqual(values["prompt_marker"], "synthetic label cobalt-orbit-517")
        self.assertEqual(values["answer_name"], "Marrow Gleam")
        self.assertEqual(values["user_message_id"], user_id)
        self.assertEqual(values["assistant_message_id"], assistant_id)


if __name__ == "__main__":
    unittest.main()
