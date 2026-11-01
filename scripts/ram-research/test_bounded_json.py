"""Synthetic framing regressions. Passing these is not a RAM recovery result."""

import hashlib
import io
import json
import unittest

from bounded_json import parse_sse, scan


def record(text="ascii"):
    return json.dumps({"type": "stream-item", "encoded_item": f'data: {{"text": {json.dumps(text, ensure_ascii=False)}}}\n\n',
                       "stream_item_id": "synthetic-stream"}, ensure_ascii=False, separators=(",", ":"))


def single(blob, **kwargs):
    return scan(io.BytesIO(blob), [{"Virtual": 4096, "Physical": 0, "Size": len(blob)}], len(blob), **kwargs)


class BoundedJsonTests(unittest.TestCase):
    def test_unicode_hash_covers_bytes_not_characters(self):
        raw = record("مرحبا café 🧪").encode("utf-8")
        result = single(raw + b"\xff\x00trailing garbage")
        candidate = result["records"][0]
        self.assertEqual(candidate["record_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(candidate["raw_byte_length"], len(raw))
        self.assertEqual(candidate["decoded_events"][0]["data"]["text"], "مرحبا café 🧪")

    def test_utf16_unaligned_and_multibyte(self):
        raw = record("مرحبا 🧪").encode("utf-16-le")
        result = single(b"X" + raw + b"\x00", chunk_size=13)
        candidate = result["records"][0]
        self.assertEqual(candidate["encoding"], "utf-16-le")
        self.assertEqual(candidate["record_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(candidate["source_virtual_addresses"], [4097])

    def test_signature_crosses_virtual_page_and_chunk_boundary(self):
        raw = record().encode()
        virtual_data = b"x" * 15 + raw
        split = 23
        image = bytearray(2048)
        image[512:512 + split] = virtual_data[:split]
        image[1024:1024 + len(virtual_data) - split] = virtual_data[split:]
        rows = [{"Virtual": 4096, "Physical": 512, "Size": split},
                {"Virtual": 4096 + split, "Physical": 1024, "Size": len(virtual_data) - split}]
        result = scan(io.BytesIO(image), rows, len(image), chunk_size=17)
        self.assertEqual(result["stats"]["signature_hits"], 1)
        candidate = result["records"][0]
        self.assertEqual(candidate["source_virtual_addresses"], [4111])
        self.assertEqual(sum(s["size"] for s in candidate["source_spans"][0]), len(raw))
        self.assertEqual(len(candidate["source_spans"][0]), 2)

    def test_virtual_gap_is_never_bridged(self):
        raw = record().encode()
        split = 40
        rows = [{"Virtual": 4096, "Physical": 0, "Size": split},
                {"Virtual": 4096 + split + 1, "Physical": split, "Size": len(raw) - split}]
        result = scan(io.BytesIO(raw), rows, len(raw), chunk_size=19)
        self.assertEqual(result["unique_complete_records"], 0)
        self.assertEqual(result["stats"]["gap_or_end_truncated_hits"], 1)

    def test_duplicate_bytes_keep_both_sources(self):
        raw = record().encode()
        result = single(raw + b"x" * 8 + raw, chunk_size=23)
        self.assertEqual(result["unique_complete_records"], 1)
        self.assertEqual(result["stats"]["complete_record_occurrences"], 2)
        self.assertEqual(len(result["records"][0]["source_spans"]), 2)

    def test_cap_limited_hit_is_not_silently_absent(self):
        raw = record("x" * 2000).encode()
        result = single(raw, cap=128)
        self.assertEqual(result["unique_complete_records"], 0)
        self.assertEqual(result["stats"]["cap_limited_hits"], 1)

    def test_quotes_braces_and_backslashes_inside_string(self):
        raw = record('literal } [ " \\ end').encode()
        self.assertEqual(single(raw)["unique_complete_records"], 1)

    def test_duplicate_keys_and_non_json_constants_rejected(self):
        for raw in (b'{"type":"stream-item","type":"stream-item","encoded_item":""}',
                    b'{"type":"stream-item","encoded_item":"","other":NaN}'):
            self.assertEqual(single(raw)["stats"]["invalid_json_or_encoding_hits"], 1)

    def test_overlapping_or_out_of_bounds_mappings_rejected(self):
        for rows in ([{"Virtual": 4096, "Physical": 0, "Size": 5}, {"Virtual": 4098, "Physical": 5, "Size": 4}],
                     [{"Virtual": 4096, "Physical": 8, "Size": 5}]):
            with self.assertRaises(ValueError):
                scan(io.BytesIO(b"x" * 10), rows, 10)

    def test_kernel_rows_are_out_of_scope(self):
        raw = record().encode()
        result = scan(io.BytesIO(raw), [{"Virtual": 1 << 63, "Physical": 0, "Size": len(raw)}], len(raw))
        self.assertEqual(result["unique_complete_records"], 0)
        self.assertEqual(result["skipped_kernel_rows"], 1)

    def test_sse_multiline_crlf_and_default_event(self):
        result = parse_sse(': comment\r\nid: test-id\r\nevent: custom\r\ndata: {"a":\r\ndata: 1}\r\n\r\ndata: {"b":2}\r\n\r\n')
        self.assertEqual(result[0]["event"], "custom")
        self.assertEqual(result[0]["data"], {"a": 1})
        self.assertEqual(result[1]["event"], "message")
        self.assertEqual(result[1]["id"], "test-id")

    def test_sse_unterminated_event_does_not_dispatch(self):
        self.assertEqual(parse_sse('data: {"a":1}\n'), [])
        self.assertEqual(parse_sse('data: {"a":1}'), [])
        self.assertEqual(parse_sse('event: unused\n\n'), [])
        self.assertTrue(parse_sse('data: [DONE]\n\n')[0]["done"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
