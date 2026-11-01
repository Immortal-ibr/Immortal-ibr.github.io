import copy
import unittest

from export_cli_model_case import review


class ModelPublicationReview(unittest.TestCase):
    def setUp(self):
        self.candidate = {"thread_id": "C", "turn_id": "T", "model_input_message_id": "M",
                          "agent_message_id": "A", "prompt": "synthetic prompt", "response": "synthetic answer"}
        self.user = {"type": "message", "id": "M", "role": "user",
                     "content": [{"type": "input_text", "text": "synthetic prompt"}],
                     "internal_chat_message_metadata_passthrough": {"turn_id": "T", "create_time": 1.5,
                                                                    "content_item_kinds": ["user.text"]}}
        self.terminal = {"method": "turn/completed", "emittedAtMs": 2000,
                         "params": {"threadId": "C", "turn": {"id": "T", "itemsView": "summary",
                           "status": "completed", "error": None, "startedAt": 1, "completedAt": 2, "durationMs": 1000,
                           "items": [{"type": "agentMessage", "id": "A", "text": "synthetic answer",
                                      "phase": "final_answer", "memoryCitation": None, "delivery": None, "questions": None}]}}}

    def test_reviewed_pair(self):
        review(self.user, self.candidate)
        review(self.terminal, self.candidate)

    def test_unknown_fields_are_not_silently_removed(self):
        value = copy.deepcopy(self.user)
        value["privateExtra"] = "not reviewed"
        with self.assertRaises(ValueError):
            review(value, self.candidate)

    def test_unrelated_or_generated_input_rejected(self):
        for change in ("text", "kind", "id"):
            value = copy.deepcopy(self.user)
            if change == "text": value["content"][0]["text"] = "unrelated"
            if change == "kind": value["internal_chat_message_metadata_passthrough"]["content_item_kinds"] = ["environments.environment_context"]
            if change == "id": value["id"] = "other"
            with self.assertRaises(ValueError):
                review(value, self.candidate)

    def test_assistant_annotations_rejected(self):
        value = copy.deepcopy(self.terminal)
        value["params"]["turn"]["items"][0]["questions"] = ["private"]
        with self.assertRaises(ValueError):
            review(value, self.candidate)

    def test_nonfinite_or_boolean_time_rejected(self):
        for invalid in (True, float("nan"), -1, "1"):
            value = copy.deepcopy(self.user)
            value["internal_chat_message_metadata_passthrough"]["create_time"] = invalid
            with self.assertRaises(ValueError):
                review(value, self.candidate)


if __name__ == "__main__":
    unittest.main()
