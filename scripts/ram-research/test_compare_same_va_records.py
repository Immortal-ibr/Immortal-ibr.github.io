import hashlib
import io
import unittest

from bounded_json import MappedReader, Row
from compare_same_va_records import compare
from scan_verified_gzip import InMemoryRaw


class SameAddressComparisonTests(unittest.TestCase):
    def test_same_and_changed_bytes_are_distinguished_without_text_output(self):
        original = b"data: old\n\n"
        image = bytearray(64)
        image[8:8 + len(original)] = original
        reader = MappedReader(io.BytesIO(image), [Row(100, 0, 64)])
        reference = {"records": [{
            "record_sha256": hashlib.sha256(original).hexdigest(),
            "raw_byte_length": len(original),
            "source_virtual_addresses": [108],
            "source_spans": [[{"virtual": 108, "physical": 8, "size": len(original)}]],
        }]}
        same = compare(reference, reader)[0]
        self.assertTrue(same["record_hash_matches"])
        self.assertTrue(same["same_physical_spans"])
        self.assertTrue(same["complete_bytes_begin_sse_data"])
        image[8] = ord("x")
        changed = compare(reference, MappedReader(io.BytesIO(image), [Row(100, 0, 64)]))[0]
        self.assertFalse(changed["record_hash_matches"])
        self.assertEqual(changed["mapped_length"], len(original))

    def test_missing_mapping_is_not_treated_as_changed_record(self):
        reference = {"records": [{
            "record_sha256": hashlib.sha256(b"data:").hexdigest(),
            "raw_byte_length": 5,
            "source_virtual_addresses": [108],
            "source_spans": [[{"virtual": 108, "physical": 8, "size": 5}]],
        }]}
        missing = compare(reference, MappedReader(io.BytesIO(bytes(64)), [Row(200, 0, 64)]))[0]
        self.assertEqual(missing["mapped_length"], 0)
        self.assertFalse(missing["record_hash_matches"])

    def test_in_memory_raw_seeks_without_disk_file(self):
        source = InMemoryRaw(bytearray(b"abcdef"))
        self.assertEqual(source.read(2), b"ab")
        source.seek(4)
        self.assertEqual(source.read(10), b"ef")
        with self.assertRaises(ValueError):
            source.seek(7)


if __name__ == "__main__":
    unittest.main()
