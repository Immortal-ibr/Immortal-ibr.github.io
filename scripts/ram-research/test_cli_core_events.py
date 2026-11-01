"""Synthetic join-rule tests, not capture outcomes."""
import io
import json
import unittest

from cli_core_events import core_record, join_core, recover


def record(value):
    return {"payload": value, "record_sha256": "synthetic-fixture", "encoding": "utf-8",
            "raw_byte_length": 20, "source_virtual_addresses": [4096], "source_spans": []}


def user(thread="c-1", turn="t-1", text="synthetic input", identity="u-1"):
    return record({"type": "item_completed", "thread_id": thread, "turn_id": turn,
                   "item": {"type": "UserMessage", "id": identity,
                            "content": [{"type": "text", "text": text}]}})


def done(turn="t-1", text="synthetic reply"):
    return record({"type": "task_complete", "turn_id": turn, "last_agent_message": text,
                   "started_at": 100, "completed_at": 101, "duration_ms": 1000})


class CoreEventTests(unittest.TestCase):
    def test_core_turn_identity_joins_without_known_values(self):
        result = join_core([user(), done()])
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["prompt"], "synthetic input")

    def test_turn_mismatch_or_missing_completion_is_not_a_candidate(self):
        self.assertEqual(join_core([user(), done(turn="t-2")])["candidate_count"], 0)
        self.assertEqual(join_core([user()])["candidate_count"], 0)

    def test_conflicting_text_and_thread_bindings_are_not_guessed(self):
        for other in (user(text="other"), user(identity="u-2"), user(thread="c-2"), done(text="other")):
            self.assertEqual(join_core([user(), done(), other])["candidate_count"], 0)

    def test_duplicate_evidence_does_not_add_a_turn(self):
        value = join_core([user(), user(), done(), done()])
        self.assertEqual(value["candidate_count"], 1)
        self.assertEqual(len(value["candidates"][0]["user_support"]), 2)

    def test_assistant_id_remains_unbound_even_if_text_is_unique(self):
        agent = record({"type": "agentMessage", "id": "a-1", "text": "synthetic reply", "phase": "final_answer"})
        candidate = join_core([user(), done(), agent])["candidates"][0]
        self.assertFalse(candidate["agent_id_independently_bound"])
        self.assertEqual(candidate["text_matching_unbound_agent_objects"][0]["agent_message_id"], "a-1")

    def test_same_reply_in_two_turns_never_proves_an_agent_binding(self):
        agent = record({"type": "agentMessage", "id": "a-1", "text": "synthetic reply", "phase": "final_answer"})
        result = join_core([user(), done(), user(turn="t-2"), done(turn="t-2"), agent])
        self.assertEqual(result["candidate_count"], 2)
        self.assertTrue(all(not c["agent_id_independently_bound"] for c in result["candidates"]))

    def test_unsupported_nontext_and_lowercase_items_are_not_repaired(self):
        for kind in ("userMessage", "AgentMessage"):
            value = user()
            value["payload"]["item"]["type"] = kind
            self.assertEqual(join_core([value, done()])["candidate_count"], 0)
        value = user()
        value["payload"]["item"]["content"] = [{"type": "image", "url": "synthetic"}]
        self.assertEqual(join_core([value, done()])["candidate_count"], 0)

    def test_nonstring_type_and_malformed_times_do_not_crash(self):
        for kind in ({}, [], None, 42, True):
            self.assertFalse(core_record({"type": kind}))
        for invalid in ({}, [], True, -1, "100", 1.5):
            completion = done()
            completion["payload"]["started_at"] = invalid
            result = join_core([user(), completion])
            self.assertEqual(result["candidate_count"], 0)
            self.assertEqual(result["semantic_rejections"]["invalid_task_timestamp"], 1)

    def test_backwards_clock_is_reported_not_repaired(self):
        completion = done()
        completion["payload"]["completed_at"] = 99
        result = join_core([user(), completion])
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["semantic_rejections"]["task_end_before_start"], 1)

    def test_core_recovery_across_adjacent_pages_in_both_encodings(self):
        for encoding in ("utf-8", "utf-16-le"):
            payloads = [user(text="Arabic: \u062a\u062c\u0631\u0628\u0629; caf\u00e9; \U0001f642")["payload"], done()["payload"], {"type": {}}]
            raw = b"\0" * 12 + b"\0\0".join(json.dumps(p, ensure_ascii=False, separators=(",", ":")).encode(encoding) for p in payloads)
            split = 93
            image = raw[:split] + b"\0" * 10 + raw[split:]
            rows = [{"Virtual": 4096, "Physical": 0, "Size": split},
                    {"Virtual": 4096 + split, "Physical": split + 10, "Size": len(raw) - split}]
            result = recover(io.BytesIO(image), rows, len(image), cap=4096)
            self.assertEqual(result["unique_complete_core_records"], 2)
            self.assertEqual(result["join"]["candidate_count"], 1)
            self.assertEqual(result["join"]["candidates"][0]["prompt"], payloads[0]["item"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
