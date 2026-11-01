"""Synthetic regression checks for the frozen Chrome state grammar and join."""

import io
import json
import tempfile
import unittest
from pathlib import Path

from chrome_state_records import scan
from chrome_state_turns import reconstruct
from score_chrome_state import render_synthetic_markdown


def state(conversation="conversation-a", parent="assistant-a"):
    return {
        "backendConversationId": conversation,
        "messages": [
            {"id": "user-a", "role": "user", "content": "synthetic prompt"},
            {"id": "assistant-a", "role": "assistant", "content": "synthetic reply"},
        ],
        "parentMessageId": parent,
        "userMessageCount": 1,
    }


class ChromeStateTests(unittest.TestCase):
    def test_scoring_display_normalization_preserves_unicode(self):
        markdown = "Name: **Lunar Echo**  \nمرصد café 🌙  \n12 + 34 = **46**."
        visible = "Name: Lunar Echo\nمرصد café 🌙\n12 + 34 = 46."
        self.assertEqual(render_synthetic_markdown(markdown), visible)

    def test_framing_crosses_virtually_adjacent_nonadjacent_physical_pages(self):
        payload = json.dumps(state(), separators=(",", ":")).encode()
        image = bytearray(12288)
        first_length = 96
        image[4096 + 4096 - first_length:8192] = payload[:first_length]
        image[:len(payload) - first_length] = payload[first_length:]
        rows = [
            {"Virtual": 4096, "Physical": 4096, "Size": 4096},
            {"Virtual": 8192, "Physical": 0, "Size": 4096},
        ]
        parsed = scan(io.BytesIO(image), rows, len(image), cap=4096)
        self.assertEqual(parsed["unique_complete_records"], 1)
        self.assertEqual(parsed["records"][0]["state"], state())
        self.assertEqual(len(parsed["records"][0]["source_spans"][0]), 2)

    def test_join_keeps_conversations_separate_and_checks_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = []
            for name, value in (
                ("first", state()),
                ("second", state("conversation-b")),
                ("wrong-parent", state("conversation-c", "unrelated")),
            ):
                path = Path(temp) / f"{name}.json"
                path.write_text(json.dumps({
                    "ground_truth_supplied": False,
                    "unique_complete_records": 1,
                    "records": [{
                        "sha256": name,
                        "encoding": "utf-8",
                        "virtual_addresses": [1234],
                        "state": value,
                    }],
                }), encoding="utf-8")
                paths.append(path)
            result = reconstruct(paths)
            self.assertEqual(len(result["candidate_turns"]), 2)
            self.assertEqual(
                {candidate["conversation_id"] for candidate in result["candidate_turns"]},
                {"conversation-a", "conversation-b"},
            )


if __name__ == "__main__":
    unittest.main()
