"""Synthetic regression for the post-hoc observer-copy classifier."""

import json
from pathlib import Path
import tempfile
import unittest

from classify_observer_mapped_hits import analyze, mapped_rows, virtual_window


class ObserverContextTests(unittest.TestCase):
    def test_finds_observer_structure_without_emitting_content(self):
        prompt = "Synthetic prompt blue triangle 27"
        response = "Synthetic answer violet lantern 41"
        text_tail = prompt + "\n\nChatGPT said:\n\n" + response
        object_bytes = json.dumps({"page": {"user": [], "assistant": [],
                                           "textTail": text_tail,
                                           "dataConversation": None}}).encode("utf-8")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / "image.raw"
            image.write_bytes(bytes(4096) + object_bytes + bytes(4096 - len(object_bytes)))
            memmap = root / "map.json"
            memmap.write_text(json.dumps([{"Virtual": 0x1000, "Physical": 4096,
                                            "Size": 4096}]), encoding="utf-8")
            known = root / "known.json"
            known.write_text(json.dumps({"prompt": prompt, "response": response}), encoding="utf-8")
            observation = root / "observation.json"
            observation.write_text(json.dumps({"page": {"textTail": text_tail}}), encoding="utf-8")
            result = analyze(image, memmap, known, observation)
        self.assertEqual(result["counts"], {"prompt": 1, "response": 1})
        for hit in result["hits_private"]:
            self.assertTrue(hit["offsets"]["textTail"])
            self.assertTrue(hit["offsets"]["full_json_escaped_observation"])
            self.assertTrue(hit["offsets"]["other_value"])
        self.assertNotIn(prompt, json.dumps(result))
        self.assertNotIn(response, json.dumps(result))

    def test_virtual_window_and_overlap_guard(self):
        with tempfile.TemporaryFile() as image:
            image.write(b"ABCDEFGH")
            image.seek(0)
            intervals = [(100, 104, 0), (106, 110, 4)]
            window, mapped = virtual_window(image, intervals, [100, 106], 101, 109)
        self.assertEqual(window, b"BCD\x00\x00EFG")
        self.assertEqual(mapped, 6)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            mapped_rows([{"Virtual": 100, "Physical": 0, "Size": 8},
                         {"Virtual": 104, "Physical": 8, "Size": 8}], 16)


if __name__ == "__main__":
    unittest.main()
