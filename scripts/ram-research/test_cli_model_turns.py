"""Synthetic model-input/RPC joins, not experimental outcomes."""
import io
import json
import unittest

from cli_model_turns import join_model, recover, tagged_user


def frame(value):
    return {"payload": value, "record_sha256": "synthetic", "encoding": "utf-8", "raw_byte_length": 10,
            "source_virtual_addresses": [4096], "source_spans": [[]]}


def user(turn="t-1", identity="model-input-id", prompt="synthetic", kind="user.text"):
    return frame({"type": "message", "id": identity, "role": "user", "content": [{"type": "input_text", "text": prompt}],
                  "internal_chat_message_metadata_passthrough": {"turn_id": turn, "create_time": 123.4, "content_item_kinds": [kind]}})


def answer(thread="c-1", turn="t-1", identity="a-1", text="synthetic reply", status="completed", error=None):
    return frame({"method": "turn/completed", "params": {"threadId": thread, "turn": {"id": turn, "status": status,
                  "error": error, "items": [{"type": "agentMessage", "id": identity, "text": text, "phase": "final_answer"}]}}})


class ModelJoinTests(unittest.TestCase):
    def test_exact_turn_join_preserves_the_identifier_namespace(self):
        candidate = join_model([user(), answer()])["candidates"][0]
        self.assertEqual(candidate["model_input_message_id"], "model-input-id")
        self.assertNotIn("user_message_id", candidate)
        self.assertFalse(candidate["api_user_item_id_recovered"])
        self.assertTrue(candidate["agent_id_independently_bound"])

    def test_user_role_without_human_text_tag_is_not_a_prompt(self):
        for kind in ("environments.environment_context", "other", None):
            self.assertFalse(tagged_user(user(kind=kind)["payload"]))
            self.assertEqual(join_model([user(kind=kind), answer()])["candidate_count"], 0)

    def test_wrong_turn_or_unsuccessful_terminal_cannot_join(self):
        for other in (answer(turn="t-2"), answer(status="interrupted"), answer(error={"message": "synthetic"})):
            self.assertEqual(join_model([user(), other])["candidate_count"], 0)

    def test_conflicting_inputs_answers_or_thread_bindings_are_ambiguous(self):
        for other in (user(prompt="other"), user(identity="other"), answer(text="other"), answer(identity="other"), answer(thread="c-2")):
            self.assertEqual(join_model([user(), answer(), other])["candidate_count"], 0)

    def test_duplicate_records_do_not_add_a_turn(self):
        self.assertEqual(join_model([user(), user(), answer(), answer()])["candidate_count"], 1)

    def test_metadata_cardinality_and_nontext_are_not_repaired(self):
        for metadata in (None, "user.text", {"turn_id": "t-1", "content_item_kinds": "user.text"},
                         {"turn_id": "t-1", "content_item_kinds": ["user.text", "user.text"]}):
            value = user()["payload"]
            value["internal_chat_message_metadata_passthrough"] = metadata
            self.assertFalse(tagged_user(value))

    def test_frame_replay_in_both_encodings_excludes_generated_context(self):
        for encoding in ("utf-8", "utf-16-le"):
            values = [user(kind="environments.environment_context"), user(prompt="\u062a\u062c\u0631\u0628\u0629 \U0001f642"), answer()]
            raw = b"\0\0".join(json.dumps(value["payload"], ensure_ascii=False, separators=(",", ":")).encode(encoding) for value in values)
            result = recover(io.BytesIO(raw), [{"Virtual": 4096, "Physical": 0, "Size": len(raw)}], len(raw), cap=4096)
            self.assertEqual(result["join"]["candidate_count"], 1)
            self.assertEqual(result["other_user_role_records_excluded"], 1)


if __name__ == "__main__":
    unittest.main()
