import copy
import unittest

from score_chrome_visible_screenonly import score


CID = "11111111-2222-3333-4444-555555555555"
URL = f"https://chatgpt.com/uc/{CID}"
RESPONSE = "A ceramic sextant measures angles, not snowflakes."


def controls():
    common = {"status": "ok", "target_id": "one-tab"}
    submit = {**common, "mode": "submit_quiet", "answer_text_observed": False,
              "prompt": "Why cannot a ceramic sextant weigh a snowflake?",
              "submitted_utc": "2026-10-01T00:00:01Z"}
    before = {**common, "page": {"url": URL, "message_uuid_li_count": 2},
              "ended_utc": "2026-10-01T00:00:02Z"}
    screenshot = {**common, "mode": "screenshot", "browser_url_before": URL,
                  "png_sha256": "ABCD", "started_utc": "2026-10-01T00:00:03Z",
                  "ended_utc": "2026-10-01T00:00:04Z"}
    post = {**common, "page": copy.deepcopy(before["page"]),
            "started_utc": "2026-10-01T00:00:07Z"}
    acquisition = {"exit_code": 0, "status": "captured_unvalidated",
                   "started_utc": "2026-10-01T00:00:05Z",
                   "ended_utc": "2026-10-01T00:00:06Z"}
    return [submit, before, screenshot, post, acquisition]


class VisibleScreenOnlyScoreTests(unittest.TestCase):
    def test_exact_three_field_candidate(self):
        recovery = {"ground_truth_supplied": False, "candidate_turns": [
            {"conversation_id": CID, "prompt": controls()[0]["prompt"],
             "response_markdown": RESPONSE}]}
        result, known = score(recovery, *controls(), "ABCD", RESPONSE)
        self.assertTrue(result["target_reconstructed_3_of_3"])
        self.assertFalse(result["independent_dom_message_ids_scored"])
        self.assertEqual(known["response"], RESPONSE)

    def test_zero_candidate_is_reportable(self):
        result, _ = score({"ground_truth_supplied": False, "candidate_turns": []},
                          *controls(), "ABCD", RESPONSE)
        self.assertEqual(result["target_conversation_candidates"], 0)

    def test_answer_text_in_controller_is_rejected(self):
        rows = controls()
        rows[1]["unexpected_text"] = RESPONSE
        with self.assertRaisesRegex(ValueError, "returned by the page controller"):
            score({"ground_truth_supplied": False, "candidate_turns": []},
                  *rows, "ABCD", RESPONSE)

    def test_changed_target_is_rejected(self):
        rows = controls()
        rows[3]["target_id"] = "other-tab"
        with self.assertRaisesRegex(ValueError, "target changed"):
            score({"ground_truth_supplied": False, "candidate_turns": []},
                  *rows, "ABCD", RESPONSE)

    def test_screenshot_after_acquisition_is_rejected(self):
        rows = controls()
        rows[2]["started_utc"] = "2026-10-01T00:00:08Z"
        with self.assertRaisesRegex(ValueError, "chronology"):
            score({"ground_truth_supplied": False, "candidate_turns": []},
                  *rows, "ABCD", RESPONSE)


if __name__ == "__main__":
    unittest.main()
