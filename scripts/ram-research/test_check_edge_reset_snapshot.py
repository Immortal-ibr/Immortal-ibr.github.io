"""Synthetic checks for the post-hoc VMware reset-file control."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from check_edge_reset_snapshot import control_values


class ResetControlTests(unittest.TestCase):
    def test_values_come_from_independent_submission_and_dom_ids(self):
        prompt = "For the synthetic label cobalt-orbit-517, invent a museum."
        conversation = "123e4567-e89b-12d3-a456-426614174000"
        user = "123e4567-e89b-12d3-a456-426614174001"
        assistant = "123e4567-e89b-12d3-a456-426614174002"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "submission.json").write_text(json.dumps({"prompt": prompt}), encoding="utf-8")
            (root / "ids.json").write_text(json.dumps({"page": {
                "url": f"https://chatgpt.com/c/{conversation}",
                "uuid_attribute_hits": [
                    {"tag": "LI", "name": "id", "value": user, "text": prompt},
                    {"tag": "LI", "name": "id", "value": assistant, "text": "fictional reply"},
                ],
            }}), encoding="utf-8")
            with patch("check_edge_reset_snapshot.CASES", (("test", "submission.json", "ids.json"),)):
                values = control_values(root)
            self.assertEqual(values, {
                "test/conversation_id": conversation,
                "test/prompt_marker": "synthetic label cobalt-orbit-517",
                "test/user_message_id": user,
                "test/assistant_message_id": assistant,
            })


if __name__ == "__main__":
    unittest.main()
