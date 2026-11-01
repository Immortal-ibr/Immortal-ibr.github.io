"""Regression checks for the public fresh-replay verifier (not RAM trials)."""

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PUBLIC_ROOT = Path(__file__).resolve().parents[2] / "public/research/chatgpt-windows-ram"
SPEC = importlib.util.spec_from_file_location(
    "fixture_verifier", PUBLIC_ROOT / "final_verification/verify_fixture_replays.py"
)
VERIFIER = importlib.util.module_from_spec(SPEC)
_previous_bytecode_setting = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    SPEC.loader.exec_module(VERIFIER)
finally:
    sys.dont_write_bytecode = _previous_bytecode_setting


class FixtureVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fixture-verifier-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        manifest = json.loads((PUBLIC_ROOT / "FROZEN_METHOD_V2.json").read_text(encoding="utf-8"))
        files = ["FROZEN_METHOD_V2.json", manifest["runner_file"], *manifest["method_files"]]
        for folder in ("trial_iab_two_chats_004_results", "trial_iab_visible_005_results"):
            files += [folder + "/synthetic_record_fixture.json",
                      folder + "/fixture_reconstruction_v2.json"]
        for name in files:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PUBLIC_ROOT / name, target)

    def test_fresh_joins_reproduce_fields_and_counts(self):
        record = VERIFIER.verify(self.root)
        self.assertTrue(record["all_checks_pass"])
        self.assertEqual([r["replay_candidates"] for r in record["cases"]], [2, 1])
        self.assertTrue(all(r["fresh_joiner_executed"] for r in record["cases"]))

    def test_old_saved_replay_files_are_not_inputs(self):
        directory = self.root / "final_verification"
        directory.mkdir()
        for name in ("two_chats_replay.json", "visible_replay.json"):
            (directory / name).write_text("not even JSON", encoding="utf-8")
        self.assertTrue(VERIFIER.verify(self.root)["all_checks_pass"])

    def test_modified_frozen_code_is_not_executed(self):
        method = self.root / "method_v2/reconstruct_turns.py"
        method.write_text("raise RuntimeError('must not run')", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "refusing to execute"):
            VERIFIER.verify(self.root)

    def test_changed_fixture_is_a_failed_check(self):
        fixture = self.root / "trial_iab_visible_005_results/synthetic_record_fixture.json"
        fixture.write_text('{"records": []}', encoding="utf-8")
        record = VERIFIER.verify(self.root)
        self.assertFalse(record["all_checks_pass"])
        self.assertEqual(record["cases"][1]["replay_candidates"], 0)


if __name__ == "__main__":
    unittest.main()
