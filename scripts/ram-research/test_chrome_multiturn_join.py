"""Synthetic boundary checks for the already-frozen Chrome state joiner."""

import json
from pathlib import Path
import tempfile
import unittest

from chrome_state_turns import reconstruct


def record(messages, parent, digest):
    return {"sha256": digest, "encoding": "utf-8", "virtual_addresses": [4096],
            "state": {"backendConversationId": "same-conversation",
                      "messages": messages, "parentMessageId": parent,
                      "userMessageCount": len(messages) // 2}}


class FrozenJoinBoundaryTests(unittest.TestCase):
    def test_latest_state_yields_only_latest_pair(self):
        messages = [
            {"id": "u1", "role": "user", "content": "first prompt"},
            {"id": "a1", "role": "assistant", "content": "first answer"},
            {"id": "u2", "role": "user", "content": "second prompt"},
            {"id": "a2", "role": "assistant", "content": "second answer"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            latest = Path(temp) / "latest.json"
            latest.write_text(json.dumps({"ground_truth_supplied": False,
                                          "unique_complete_records": 1,
                                          "records": [record(messages, "a2", "latest")]}), encoding="utf-8")
            result = reconstruct([latest])
        self.assertEqual(len(result["candidate_turns"]), 1)
        self.assertEqual(result["candidate_turns"][0]["user_message_id"], "u2")

    def test_earlier_state_copy_adds_first_pair(self):
        messages = [
            {"id": "u1", "role": "user", "content": "first prompt"},
            {"id": "a1", "role": "assistant", "content": "first answer"},
            {"id": "u2", "role": "user", "content": "second prompt"},
            {"id": "a2", "role": "assistant", "content": "second answer"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "both.json"
            path.write_text(json.dumps({"ground_truth_supplied": False,
                                        "unique_complete_records": 2,
                                        "records": [record(messages[:2], "a1", "earlier"),
                                                    record(messages, "a2", "latest")]}), encoding="utf-8")
            result = reconstruct([path])
        self.assertEqual({turn["user_message_id"] for turn in result["candidate_turns"]},
                         {"u1", "u2"})


if __name__ == "__main__":
    unittest.main()
