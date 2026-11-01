"""Synthetic regressions for the post-hoc request/core join."""

import unittest

from cli_request_core_turns import join


def record(payload, digest):
    return {"payload": payload, "record_sha256": digest, "encoding": "utf-8",
            "raw_byte_length": 100, "source_virtual_addresses": [4096],
            "source_spans": [[{"virtual": 4096, "physical": 8192, "size": 100}]]}


def request(thread="thread-a", turn="turn-a", prompt="synthetic prompt"):
    human = {"type": "message", "id": "model-msg-a", "role": "user",
             "content": [{"type": "input_text", "text": prompt}],
             "internal_chat_message_metadata_passthrough": {
                 "turn_id": turn, "content_item_kinds": ["user.text"]}}
    environment = {"type": "message", "id": "environment", "role": "user",
                   "content": [{"type": "input_text", "text": "generated context"}],
                   "internal_chat_message_metadata_passthrough": {
                       "turn_id": turn, "content_item_kinds": ["environments.environment_context"]}}
    return {"type": "response.create", "client_metadata": {
        "thread_id": thread, "turn_id": turn}, "input": [environment, human]}


def complete(turn="turn-a", response="synthetic reply"):
    return {"type": "task_complete", "turn_id": turn,
            "last_agent_message": response, "started_at": 10,
            "completed_at": 12, "duration_ms": 2000}


class RequestCoreTests(unittest.TestCase):
    def test_exact_turn_joins_thread_prompt_and_answer_without_agent_id(self):
        result = join([record(request(), "request"), record(complete(), "complete")])
        self.assertEqual(result["candidate_count"], 1)
        candidate = result["candidates"][0]
        self.assertEqual((candidate["thread_id"], candidate["turn_id"],
                          candidate["model_input_message_id"], candidate["prompt"],
                          candidate["response"]),
                         ("thread-a", "turn-a", "model-msg-a", "synthetic prompt", "synthetic reply"))
        self.assertFalse(candidate["assistant_message_id_independently_bound"])
        self.assertFalse(candidate["api_user_item_id_recovered"])

    def test_wrong_turn_and_generated_context_cannot_make_a_candidate(self):
        wrong_turn = join([record(request(), "request"),
                           record(complete(turn="turn-b"), "complete")])
        self.assertEqual(wrong_turn["candidate_count"], 0)
        only_context = request()
        only_context["input"] = only_context["input"][:1]
        missing_human = join([record(only_context, "request"), record(complete(), "complete")])
        self.assertEqual(missing_human["candidate_count"], 0)
        self.assertEqual(missing_human["semantic_rejections"],
                         {"request_without_one_matching_human_input": 1})

    def test_conflicts_remain_ambiguous(self):
        records = [record(request(), "request-a"),
                   record(request(thread="thread-b"), "request-b"),
                   record(complete(), "complete-a"),
                   record(complete(response="different reply"), "complete-b")]
        result = join(records)
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(len(result["incomplete_or_ambiguous"]), 2)


if __name__ == "__main__":
    unittest.main()
