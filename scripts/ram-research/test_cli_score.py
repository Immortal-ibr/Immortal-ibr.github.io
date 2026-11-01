"""Synthetic freeze/prospective-score guards, not capture results."""
import unittest

from score_cli_core import validate_frozen


class ScoreFreezeTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"files": [{"path": "core.py", "sha256": "synthetic-hash"}],
                         "record_cap_bytes": 1024, "frozen_utc": "2026-09-29T01:00:00+00:00"}
        self.recovered = {"executed_method_sha256": {"core.py": "synthetic-hash"}, "record_byte_cap": 1024}

    def test_matching_method_frozen_before_submission(self):
        validate_frozen(self.recovered, self.manifest, "2026-09-29T02:00:00+00:00")

    def test_different_or_missing_source_hashes_fail(self):
        for hashes in ({}, {"core.py": "other-hash"}, {"core.py": "synthetic-hash", "extra.py": "hash"}):
            self.recovered["executed_method_sha256"] = hashes
            with self.assertRaises(ValueError):
                validate_frozen(self.recovered, self.manifest, "2026-09-29T02:00:00+00:00")

    def test_different_cap_fails(self):
        self.recovered["record_byte_cap"] = 2048
        with self.assertRaises(ValueError):
            validate_frozen(self.recovered, self.manifest, "2026-09-29T02:00:00+00:00")

    def test_freeze_after_or_equal_to_submission_fails(self):
        for stamp in ("2026-09-29T00:00:00+00:00", "2026-09-29T01:00:00+00:00"):
            with self.assertRaises(ValueError):
                validate_frozen(self.recovered, self.manifest, stamp)


if __name__ == "__main__":
    unittest.main()
