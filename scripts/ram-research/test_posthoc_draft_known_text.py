"""Synthetic guards for the draft-only exact-value diagnostic."""

import unittest

from posthoc_draft_known_text import draft_prompt


class DraftInputTests(unittest.TestCase):
    def record(self):
        return {"status": "ok", "prompt": "synthetic draft marker 56",
                "draft_exact_match": True, "submission_attempted": False,
                "page_after": {"url": "https://chatgpt.com/",
                               "draft": "synthetic draft marker 56",
                               "message_li_count": 0}}

    def test_accepts_exact_unsent_draft(self):
        self.assertEqual(draft_prompt(self.record()), "synthetic draft marker 56")

    def test_rejects_submitted_or_changed_state(self):
        for field, value in (("submission_attempted", True), ("draft_exact_match", False)):
            item = self.record()
            item[field] = value
            with self.assertRaises(ValueError):
                draft_prompt(item)
        item = self.record()
        item["page_after"]["message_li_count"] = 2
        with self.assertRaises(ValueError):
            draft_prompt(item)


if __name__ == "__main__":
    unittest.main()
