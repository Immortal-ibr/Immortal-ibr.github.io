"""Synthetic ancestry/patch-join regressions; no account or RAM data."""

import copy
import unittest

from signedin_sse_turns import join


def fixture():
    conversation = "synthetic-conversation"
    user = {"id": "u1", "author": {"role": "user"},
            "content": {"content_type": "text", "parts": ["synthetic prompt"]}}
    system = {"id": "s1", "author": {"role": "system"},
              "metadata": {"parent_id": "u1"}}
    assistant = {"id": "a1", "author": {"role": "assistant"},
                 "content": {"content_type": "text", "parts": [""]},
                 "metadata": {"parent_id": "s1"}}
    data = [
        {"type": "input_message", "input_message": user, "conversation_id": conversation},
        {"v": {"message": system, "conversation_id": conversation}},
        {"v": {"message": assistant, "conversation_id": conversation}},
        {"type": "message_marker", "conversation_id": conversation,
         "message_id": "a1", "marker": "user_visible_token"},
        {"type": "message_marker", "conversation_id": conversation,
         "message_id": "a1", "marker": "final_channel_token"},
        {"p": "/message/content/parts/0", "o": "append", "v": "alpha "},
        {"v": "beta "},
        {"o": "patch", "v": [
            {"p": "/message/content/parts/0", "o": "append", "v": "gamma"},
            {"p": "/message/status", "o": "replace", "v": "finished_successfully"},
            {"p": "/message/end_turn", "o": "replace", "v": True},
        ]},
        {"type": "message_marker", "conversation_id": conversation,
         "message_id": "a1", "marker": "last_token"},
        {"type": "message_stream_complete", "conversation_id": conversation},
    ]
    records = [{"event": {"data": event}, "record_sha256": f"synthetic-{index}"}
               for index, event in enumerate(data)]
    segment = {"record_indices": list(range(len(records))),
               "control_gaps": [{} for _ in range(len(records) - 1)],
               "stream_sha256": "synthetic-stream", "byte_length": 1000,
               "start_virtual": 4096, "end_virtual": 5096, "source_spans": []}
    return {"ground_truth_supplied": False, "records": records,
            "contiguous_segments": [segment]}


class SignedInSseTurnTests(unittest.TestCase):
    def test_system_hop_and_all_patches_join_without_known_values(self):
        result = join(fixture())
        self.assertEqual(result["candidate_count"], 1)
        candidate = result["candidate_turns"][0]
        self.assertEqual(candidate["response"], "alpha beta gamma")
        self.assertEqual(candidate["prompt"], "synthetic prompt")
        self.assertEqual(candidate["user_message_id"], "u1")
        self.assertEqual(candidate["assistant_message_id"], "a1")
        self.assertEqual(candidate["ancestry_message_ids"], ["u1", "s1", "a1"])

    def test_wrong_parent_or_marker_cannot_join(self):
        for event_index, path, replacement in (
            (2, ("v", "message", "metadata", "parent_id"), "other"),
            (4, ("message_id",), "other"),
        ):
            parsed = fixture()
            value = parsed["records"][event_index]["event"]["data"]
            for key in path[:-1]:
                value = value[key]
            value[path[-1]] = replacement
            self.assertEqual(join(parsed)["candidate_count"], 0)

    def test_missing_completion_or_final_status_cannot_join(self):
        parsed = fixture()
        parsed["records"][9]["event"]["data"]["conversation_id"] = "other"
        self.assertEqual(join(parsed)["candidate_count"], 0)
        parsed = fixture()
        parsed["records"][7]["event"]["data"]["v"][1]["v"] = "in_progress"
        self.assertEqual(join(parsed)["candidate_count"], 0)

    def test_unverified_adjacency_and_second_assistant_rejected(self):
        parsed = fixture()
        parsed["contiguous_segments"][0]["control_gaps"] = []
        self.assertEqual(join(parsed)["candidate_count"], 0)
        parsed = fixture()
        extra = copy.deepcopy(parsed["records"][2])
        extra["event"]["data"]["v"]["message"]["id"] = "a2"
        parsed["records"].append(extra)
        parsed["contiguous_segments"][0]["record_indices"].insert(3, len(parsed["records"]) - 1)
        parsed["contiguous_segments"][0]["control_gaps"].append({})
        self.assertEqual(join(parsed)["candidate_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
