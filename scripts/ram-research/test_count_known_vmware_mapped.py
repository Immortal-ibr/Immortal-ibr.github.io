"""Synthetic mapping-boundary regressions for the post-hoc control."""

import io
import unittest

from count_known_vmware_mapped import count_mapped


class KnownVmwareCountTests(unittest.TestCase):
    def test_counts_across_adjacent_virtual_nonadjacent_physical_rows(self):
        raw = bytearray(8192)
        raw[4092:4096] = b"abcd"
        raw[0:2] = b"ef"
        rows = [{"Virtual": 4096, "Physical": 4092, "Size": 4},
                {"Virtual": 4100, "Physical": 0, "Size": 2}]
        result = count_mapped(io.BytesIO(raw), rows, len(raw), {"synthetic": b"abcdef"})
        self.assertEqual(result["mapped_counts"], {"synthetic": 1})
        self.assertEqual(result["short_reads"], 0)

    def test_does_not_join_across_a_virtual_gap(self):
        raw = bytearray(8192)
        raw[4092:4096] = b"abcd"
        raw[0:2] = b"ef"
        rows = [{"Virtual": 4096, "Physical": 4092, "Size": 4},
                {"Virtual": 4101, "Physical": 0, "Size": 2}]
        result = count_mapped(io.BytesIO(raw), rows, len(raw), {"synthetic": b"abcdef"})
        self.assertEqual(result["mapped_counts"], {"synthetic": 0})


if __name__ == "__main__":
    unittest.main()
