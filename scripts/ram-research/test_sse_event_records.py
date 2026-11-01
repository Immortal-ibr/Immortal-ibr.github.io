"""Synthetic SSE framing tests, never published as recovered RAM evidence."""

import io
import unittest

from sse_event_records import scan


class SseEventTests(unittest.TestCase):
    def test_utf8_and_utf16_complete_events(self):
        for encoding in ("utf-8", "utf-16-le"):
            raw = 'data: {"v":[{"p":"/message/content/parts/0","v":"synthetic"}]}\n\n'.encode(encoding)
            result = scan(io.BytesIO(b"_" + raw),
                          [{"Virtual": 4097, "Physical": 1, "Size": len(raw)}],
                          len(raw) + 1)
            self.assertEqual(result["unique_complete_records"], 1)
            self.assertEqual(result["records"][0]["event"]["data"]["v"][0]["v"],
                             "synthetic")

    def test_unterminated_and_invalid_json_do_not_count(self):
        for raw in (b'data: {"v":1}', b'data: {"v":NaN}\n\n'):
            result = scan(io.BytesIO(raw),
                          [{"Virtual": 4096, "Physical": 0, "Size": len(raw)}],
                          len(raw))
            self.assertEqual(result["unique_complete_records"], 0)

    def test_verified_sse_control_line_joins_but_junk_separates(self):
        first = b'data: {"type":"input_message"}\n\n'
        second = b'data: {"v":"answer"}\n\n'
        good = first + b'event: delta\n' + second
        result = scan(io.BytesIO(good),
                      [{"Virtual": 4096, "Physical": 0, "Size": len(good)}], len(good))
        self.assertEqual([s["record_indices"] for s in result["contiguous_segments"]], [[0, 1]])
        self.assertEqual(result["contiguous_segments"][0]["control_gaps"][0]["control_line"],
                         "event: delta\n")
        bad = first + b'not-an-sse-control\n' + second
        result = scan(io.BytesIO(bad),
                      [{"Virtual": 4096, "Physical": 0, "Size": len(bad)}], len(bad))
        self.assertEqual([s["record_indices"] for s in result["contiguous_segments"]], [[0], [1]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
