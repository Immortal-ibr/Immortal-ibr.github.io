"""Synthetic regression cases; no real RAM or account material is embedded."""

import hashlib
import io
import json
import unittest

from browser_json_envelopes import scan


def request():
    return {"action": "next", "messages": [{"id": "synthetic-user", "author": {"role": "user"}}],
            "conversation_id": "synthetic-conversation", "parent_message_id": "synthetic-parent"}


def one(blob, **kwargs):
    rows = [{"Virtual": 4096, "Physical": 0, "Size": len(blob)}]
    return scan(io.BytesIO(blob), rows, len(blob), **kwargs)


class BrowserEnvelopeTests(unittest.TestCase):
    def test_exact_request_and_duplicate_provenance(self):
        raw = json.dumps(request(), separators=(",", ":")).encode()
        result = one(raw + b"\x00" * 19 + raw)
        self.assertEqual(result["unique_complete_records"], 1)
        record = result["records"][0]
        self.assertEqual(record["kind"], "next-request")
        self.assertEqual(record["record_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(record["source_virtual_addresses"], [4096, 4096 + len(raw) + 19])
        self.assertEqual(result["stats"]["next-request/complete_occurrences"], 2)

    def test_utf16_request_and_contiguous_virtual_split(self):
        raw = json.dumps(request(), separators=(",", ":")).encode("utf-16-le")
        split = 31
        image = bytearray(2048)
        image[512:512 + split] = raw[:split]
        image[1024:1024 + len(raw) - split] = raw[split:]
        rows = [{"Virtual": 4097, "Physical": 512, "Size": split},
                {"Virtual": 4097 + split, "Physical": 1024, "Size": len(raw) - split}]
        result = scan(io.BytesIO(image), rows, len(image))
        self.assertEqual(result["unique_complete_records"], 1)
        record = result["records"][0]
        self.assertEqual(record["encoding"], "utf-16-le")
        self.assertEqual(record["source_virtual_addresses"], [4097])
        self.assertEqual(len(record["source_spans"][0]), 2)

    def test_incomplete_and_invalid_not_accepted(self):
        prefix = b'{"action":"next","messages":'
        for blob in (prefix + b'[{"id":"x"}]',
                     prefix + b'[],"conversation_id":null}',
                     prefix + b'[],"conversation_id":"x","conversation_id":"y"}'):
            result = one(blob)
            self.assertEqual(result["unique_complete_records"], 0)

    def test_response_envelope_schema(self):
        response = {"message": {"id": "synthetic-assistant", "author": {"role": "assistant"}},
                    "conversation_id": "synthetic-conversation"}
        raw = json.dumps(response, separators=(",", ":")).encode()
        result = one(raw)
        self.assertEqual(result["records"][0]["kind"], "message-event")


if __name__ == "__main__":
    unittest.main(verbosity=2)
