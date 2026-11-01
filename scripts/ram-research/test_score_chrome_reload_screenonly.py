import copy
import unittest

from score_chrome_reload_screenonly import score


CID = "11111111-2222-3333-4444-555555555555"
URL = f"https://chatgpt.com/uc/{CID}"
FRAGMENT = "The clay barometer measures pressure, not birds."


def controls():
    common = {"status": "ok", "target_id": "one-tab"}
    submit = {**common, "mode": "submit_quiet", "answer_text_observed": False,
              "prompt": "Why cannot a clay barometer count birds?"}
    before = {**common, "page": {"url": URL, "message_uuid_li_count": 2}}
    reload = {**common, "browser_url_before": URL,
              "reload_requested_utc": "2026-10-01T00:00:00Z"}
    after = {**common, "page": {"url": "https://chatgpt.com/",
                               "message_uuid_li_count": 0}}
    screenshot = {**common, "mode": "screenshot", "browser_url_before": URL,
                  "png_sha256": "ABCD"}
    return [submit, before, reload, after, copy.deepcopy(after), screenshot]


class ScreenOnlyScoreTests(unittest.TestCase):
    def test_zero_candidate_is_scored_without_ids(self):
        result, known = score({"ground_truth_supplied": False, "candidate_turns": []},
                              *controls(), "ABCD", FRAGMENT)
        self.assertEqual(result["target_conversation_candidates"], 0)
        self.assertFalse(result["independent_message_ids_or_full_response_scored"])
        self.assertTrue(known["response_is_fragment"])

    def test_matching_candidate_scores_three(self):
        candidate = {"conversation_id": CID, "prompt": controls()[0]["prompt"],
                     "response_markdown": FRAGMENT}
        result, _ = score({"ground_truth_supplied": False, "candidate_turns": [candidate]},
                          *controls(), "ABCD", FRAGMENT)
        self.assertTrue(result["target_reconstructed_3_of_3"])

    def test_answer_text_in_controller_rejected(self):
        rows = controls()
        rows[1]["unexpected_text"] = FRAGMENT
        with self.assertRaisesRegex(ValueError, "returned by the page controller"):
            score({"ground_truth_supplied": False, "candidate_turns": []},
                  *rows, "ABCD", FRAGMENT)

    def test_unverified_screenshot_rejected(self):
        with self.assertRaisesRegex(ValueError, "screenshot provenance"):
            score({"ground_truth_supplied": False, "candidate_turns": []},
                  *controls(), "DIFFERENT", FRAGMENT)


if __name__ == "__main__":
    unittest.main()
