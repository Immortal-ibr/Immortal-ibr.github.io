"""Synthetic checks for the VMware physical-reader adapter."""

import json
import unittest

from chrome_state_records import scan as scan_state
from scan_vmware_snapshot import PhysicalReader, state_turn_shape, verify_samples


class Memory:
    def __init__(self, base, data):
        self.base = base
        self.data = data

    def read(self, position, amount, flags):
        offset = position - self.base
        return self.data[offset:offset + amount]


class ProcessMemory(Memory):
    def __init__(self, virtual, physical, data):
        super().__init__(virtual, data)
        self.physical = physical

    def virt2phys(self, virtual):
        return self.physical + virtual - self.base


class SnapshotReaderTests(unittest.TestCase):
    def test_reads_guest_physical_address_above_compact_file_length(self):
        base = 7_000_000_000
        reader = PhysicalReader(Memory(base, b"abcdefghijklmnop"), flags=3)
        reader.seek(base + 2)
        self.assertEqual(reader.read(4), b"cdef")
        self.assertEqual(reader.read(2), b"gh")

    def test_virtual_and_physical_sample_agree(self):
        physical = 7_000_000_000
        virtual = 0x1000
        data = b"a" * 32
        vmm = type("Vmm", (), {"memory": Memory(physical, data)})()
        process = type("Process", (), {"memory": ProcessMemory(virtual, physical, data)})()
        self.assertEqual(verify_samples(vmm, process, [{"Virtual": virtual,
                                                        "Physical": physical,
                                                        "Size": 32}], 3),
                         {"requested": 1, "matched": 1,
                          "virtual_translation_unavailable": 0,
                          "physical_sample_unavailable": 0})

    def test_bounded_parser_uses_guest_physical_not_compact_file_offset(self):
        physical = 7_000_000_000
        state = {"backendConversationId": "synthetic-chat", "messages": [
            {"id": "u", "role": "user", "content": "synthetic prompt"},
            {"id": "a", "role": "assistant", "content": "synthetic answer"}],
            "parentMessageId": "a"}
        page = bytearray(4096)
        payload = json.dumps(state, separators=(",", ":")).encode()
        page[100:100 + len(payload)] = payload
        reader = PhysicalReader(Memory(physical, page), flags=3)
        parsed = scan_state(reader, [{"Virtual": 0x1000, "Physical": physical,
                                      "Size": 4096}], physical + 4096)
        self.assertEqual(parsed["unique_complete_records"], 1)
        self.assertTrue(state_turn_shape(parsed["records"][0]))

    def test_state_shape_requires_parent_and_two_roles(self):
        record = {"state": {"messages": [
            {"id": "u", "role": "user", "content": "prompt"},
            {"id": "a", "role": "assistant", "content": "answer"}],
            "parentMessageId": "a"}}
        self.assertTrue(state_turn_shape(record))
        record["state"]["parentMessageId"] = "unrelated"
        self.assertFalse(state_turn_shape(record))


if __name__ == "__main__":
    unittest.main()
