"""Synthetic checks for the two-turn post-capture scorer."""

import unittest

from score_chrome_multiturn import score


CONVERSATION = "11111111-2222-3333-4444-555555555555"
IDS = ["aaaaaaaa-1111-2222-3333-444444444444",
       "bbbbbbbb-1111-2222-3333-444444444444",
       "cccccccc-1111-2222-3333-444444444444",
       "dddddddd-1111-2222-3333-444444444444"]
URL = "https://chatgpt.com/uc/" + CONVERSATION


def observation(count):
    text = ["You said:First prompt", "ChatGPT said:First answer",
            "You said:Second prompt", "ChatGPT said:Second answer"]
    return {"status": "ok", "ended_utc": "2026-10-01T00:00:00Z",
            "page": {"url": URL, "uuid_attribute_hits": [
                {"tag": "LI", "name": "id", "value": IDS[index], "text": text[index]}
                for index in range(count * 2)]}}


def candidate(index):
    start = (index - 1) * 2
    return {"conversation_id": CONVERSATION,
            "user_message_id": IDS[start], "assistant_message_id": IDS[start + 1],
            "prompt": ("First" if index == 1 else "Second") + " prompt",
            "response_markdown": ("First" if index == 1 else "Second") + " answer"}


class MultiturnScoreTests(unittest.TestCase):
    def args(self, candidates):
        return ({"ground_truth_supplied": False, "candidate_turns": candidates},
                {"status": "ok", "target_id": "same-page", "prompt": "First prompt"},
                observation(1),
                {"status": "ok", "target_id": "same-page", "prompt": "Second prompt"},
                observation(2))

    def test_both_exact_turns(self):
        result = score(*self.args([candidate(1), candidate(2)]))
        self.assertEqual([item["matched_fields"] for item in result["turns"]], [5, 5])
        self.assertEqual(result["unexpected_same_conversation_pairs"], 0)

    def test_only_latest_turn(self):
        result = score(*self.args([candidate(2)]))
        self.assertEqual([item["matched_fields"] for item in result["turns"]], [0, 5])

    def test_cross_join_is_reported(self):
        wrong = candidate(2)
        wrong["user_message_id"] = IDS[0]
        result = score(*self.args([candidate(1), wrong]))
        self.assertEqual(result["turns"][1]["matched_fields"], 4)
        self.assertEqual(result["unexpected_same_conversation_pairs"], 1)

    def test_changed_first_turn_rejected(self):
        arguments = list(self.args([]))
        arguments[-1]["page"]["uuid_attribute_hits"][0]["text"] = "You said:Changed"
        with self.assertRaisesRegex(ValueError, "not stable"):
            score(*arguments)


if __name__ == "__main__":
    unittest.main()
