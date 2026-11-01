"""Synthetic regressions only; these are not acquired RAM experiments."""
import hashlib
import io
import json
import unittest

from cli_rpc_records import join, relevant_rpc, scan


def fixture(method, params):
    payload = {"method": method, "params": params}
    return {"record_sha256": hashlib.sha256(json.dumps(payload).encode()).hexdigest(),
            "encoding": "utf-8", "payload": payload, "source_virtual_addresses": [4096]}


def user(thread="c-1", turn="t-1", text="synthetic prompt", identity="u-1"):
    return fixture("item/started", {"threadId": thread, "turnId": turn,
        "item": {"type": "userMessage", "id": identity, "content": [{"type": "text", "text": text}]}})


def agent(thread="c-1", turn="t-1", text="synthetic answer", identity="a-1", phase="final_answer"):
    return fixture("item/completed", {"threadId": thread, "turnId": turn,
        "item": {"type": "agentMessage", "id": identity, "text": text, "phase": phase}})


def completed(thread="c-1", turn="t-1", status="completed", error=None):
    return fixture("turn/completed", {"threadId": thread,
        "turn": {"id": turn, "items": [], "status": status, "error": error}})


class CliRpcTests(unittest.TestCase):
    def test_exact_thread_turn_join(self):
        value = join([user(), agent(), completed()])
        self.assertEqual(value["candidate_count"], 1)
        self.assertEqual(value["candidates"][0]["prompt"], "synthetic prompt")

    def test_thread_or_turn_mismatch_never_joins(self):
        for entry in (agent(thread="c-2"), agent(turn="t-2")):
            self.assertEqual(join([user(), entry, completed()])["candidate_count"], 0)

    def test_completion_is_required(self):
        self.assertEqual(join([user(), agent()])["candidate_count"], 0)
        for entry in (completed(status="inProgress"), completed(status="failed", error={"message": "synthetic"})):
            self.assertEqual(join([user(), agent(), entry])["candidate_count"], 0)

    def test_conflicting_text_or_multiple_final_ids_stays_ambiguous(self):
        for entry in (user(text="other"), agent(text="other"), agent(identity="a-2")):
            self.assertEqual(join([user(), agent(), completed(), entry])["candidate_count"], 0)

    def test_duplicates_keep_evidence_without_extra_candidate(self):
        result = join([user(), user(), agent(), completed()])
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(len(result["candidates"][0]["user_support"]), 2)

    def test_commentary_and_incomplete_agent_are_not_final(self):
        value = agent(phase="commentary")
        self.assertEqual(join([user(), value, completed()])["candidate_count"], 0)
        value["payload"]["method"] = "item/started"
        value["payload"]["params"]["item"]["phase"] = "final_answer"
        self.assertEqual(join([user(), value, completed()])["candidate_count"], 0)

    def test_nonstring_method_does_not_crash_format_classifier(self):
        self.assertFalse(relevant_rpc({"method": {"type": "string"}}))
        self.assertFalse(relevant_rpc({"method": []}))

    def test_unicode_bytes_and_virtual_page_crossing(self):
        payload = user(text="مرحبا 🧪 café")["payload"]
        for encoding in ("utf-8", "utf-16-le"):
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(encoding)
            blob = b"X" * 13 + raw + b"\xff"
            rows = [{"Virtual": 4096, "Physical": 0, "Size": 20},
                    {"Virtual": 4116, "Physical": 20, "Size": len(blob) - 20}]
            result = scan(io.BytesIO(blob), rows, len(blob), cap=2048, chunk_size=19)
            self.assertEqual(result["unique_complete_records"], 1)
            self.assertEqual(result["records"][0]["record_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(sum(s["size"] for s in result["records"][0]["source_spans"][0]), len(raw))

    def test_cap_and_gap_remain_visible_failures(self):
        raw = json.dumps(user()["payload"], separators=(",", ":")).encode()
        rows = [{"Virtual": 4096, "Physical": 0, "Size": len(raw)}]
        result = scan(io.BytesIO(raw), rows, len(raw), cap=30)
        self.assertEqual(result["stats"]["cap_limited_hits"], 1)
        rows = [{"Virtual": 4096, "Physical": 0, "Size": 30},
                {"Virtual": 8192, "Physical": 30, "Size": len(raw) - 30}]
        result = scan(io.BytesIO(raw), rows, len(raw))
        self.assertEqual(result["unique_complete_records"], 0)
        self.assertEqual(result["stats"]["gap_or_end_truncated_hits"], 1)


if __name__ == "__main__":
    unittest.main()
