import copy
import unittest

from score_chrome_reload import score


CID = "11111111-2222-3333-4444-555555555555"
TARGET = "same-target"
PROMPT = "Why is a wool thermometer not an anemometer?"
RESPONSE = "Because it measures temperature, not wind speed."
BEFORE = f"https://chatgpt.com/uc/{CID}"


def inputs():
    common = {"status": "ok", "target_id": TARGET}
    submit = {**common, "prompt": PROMPT}
    before_observe = {**common, "page": {"url": BEFORE,
                                       "textTail": f"You said:\n{PROMPT}\nChatGPT said:\n{RESPONSE}"}}
    before_ids = {**common, "page": {"url": BEFORE, "uuid_attribute_hits": [
        {"tag": "LI", "name": "id", "value": "user-id", "text": f"You said:\n{PROMPT}"},
        {"tag": "LI", "name": "id", "value": "assistant-id", "text": f"ChatGPT said:\n{RESPONSE}"},
    ]}}
    reload = {**common, "browser_url_before": BEFORE,
              "reload_requested_utc": "2026-10-01T00:00:00Z"}
    empty = {**common, "page": {"url": "https://chatgpt.com/", "uuid_attribute_hits": []}}
    after_observe = {**common, "page": {"url": "https://chatgpt.com/"}}
    return [submit, before_observe, before_ids, reload,
            after_observe, empty, copy.deepcopy(empty)]


class ReloadScoreTests(unittest.TestCase):
    def test_zero_candidate_is_a_result(self):
        result = score({"ground_truth_supplied": False, "candidate_turns": []}, *inputs())
        self.assertEqual(result["target_conversation_candidates"], 0)
        self.assertFalse(result["target_reconstructed_5_of_5"])

    def test_correct_candidate_scores_five(self):
        candidate = {"conversation_id": CID, "user_message_id": "user-id",
                     "assistant_message_id": "assistant-id", "prompt": PROMPT,
                     "response_markdown": RESPONSE}
        result = score({"ground_truth_supplied": False,
                        "candidate_turns": [candidate]}, *inputs())
        self.assertEqual(result["target_candidate_checks"][0]["matched_fields"], 5)
        self.assertTrue(result["target_reconstructed_5_of_5"])

    def test_target_change_rejected(self):
        control = inputs()
        control[-1]["target_id"] = "different-tab"
        with self.assertRaisesRegex(ValueError, "target changed"):
            score({"ground_truth_supplied": False, "candidate_turns": []}, *control)

    def test_submitted_pair_after_reload_rejected(self):
        control = inputs()
        control[-1]["page"]["uuid_attribute_hits"].append(
            {"tag": "LI", "name": "id", "text": "You said: text"})
        with self.assertRaisesRegex(ValueError, "remained"):
            score({"ground_truth_supplied": False, "candidate_turns": []}, *control)


if __name__ == "__main__":
    unittest.main()
