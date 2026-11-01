"""Synthetic process-selection regressions."""

import unittest

from select_edge_network_service import select


class NetworkSelectionTests(unittest.TestCase):
    def test_exact_active_subtype(self):
        pslist = [{"PID": 10, "ImageFileName": "msedge.exe", "ExitTime": None},
                  {"PID": 11, "ImageFileName": "msedge.exe", "ExitTime": None},
                  {"PID": 12, "ImageFileName": "msedge.exe", "ExitTime": "past"}]
        lines = [{"PID": 10, "Process": "msedge.exe", "Args": "--type=utility --utility-sub-type=network.mojom.NetworkService"},
                 {"PID": 11, "Process": "msedge.exe", "Args": "--type=utility --utility-sub-type=network.mojom.NetworkServiceExtra"},
                 {"PID": 12, "Process": "msedge.exe", "Args": "--type=utility --utility-sub-type=network.mojom.NetworkService"}]
        self.assertEqual(select(pslist, lines)["selected_pid"], 10)

    def test_missing_or_multiple_is_not_guessed(self):
        pslist = [{"PID": pid, "ImageFileName": "msedge.exe", "ExitTime": None}
                  for pid in (10, 11)]
        with self.assertRaises(ValueError):
            select(pslist, [])
        lines = [{"PID": pid, "Process": "msedge.exe",
                  "Args": "--utility-sub-type=network.mojom.NetworkService"}
                 for pid in (10, 11)]
        with self.assertRaises(ValueError):
            select(pslist, lines)


if __name__ == "__main__":
    unittest.main(verbosity=2)
