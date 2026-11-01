"""Synthetic process-inventory checks; not a recovered-memory experiment."""

import importlib.util
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "select_browser_renderers", Path(__file__).with_name("select_browser_renderers.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SelectionTests(unittest.TestCase):
    def test_selects_all_active_renderers_without_pid_order(self):
        processes = [
            {"PID": 101, "ImageFileName": "msedge.exe", "ExitTime": None},
            {"PID": 404, "ImageFileName": "msedge.exe", "ExitTime": None},
            {"PID": 22, "ImageFileName": "msedge.exe", "ExitTime": None},
            {"PID": 5, "ImageFileName": "msedge.exe", "ExitTime": "2026-09-30T00:00:00Z"},
            {"PID": 9, "ImageFileName": "chrome.exe", "ExitTime": None},
        ]
        cmdlines = [
            {"PID": 404, "Process": "msedge.exe", "Args": "--type=renderer --foo"},
            {"PID": 101, "Process": "msedge.exe", "Args": "--type=gpu-process"},
            {"PID": 22, "Process": "msedge.exe", "Args": "--type=renderer"},
            {"PID": 5, "Process": "msedge.exe", "Args": "--type=renderer"},
            {"PID": 9, "Process": "chrome.exe", "Args": "--type=renderer"},
        ]
        result = MODULE.select_renderers(processes, cmdlines, "msedge.exe")
        self.assertEqual(result["selected_pids"], [22, 404])
        self.assertEqual(result["active_pids_without_cmdline"], [])
        self.assertEqual(result["exited_browser_pids"], [5])

    def test_reports_missing_command_lines_and_rejects_partial_type(self):
        processes = [
            {"PID": 1, "ImageFileName": "chrome.exe", "ExitTime": None},
            {"PID": 2, "ImageFileName": "chrome.exe", "ExitTime": None},
        ]
        cmdlines = [
            {"PID": 2, "Process": "chrome.exe", "Args": "--type=renderer-helper"},
        ]
        result = MODULE.select_renderers(processes, cmdlines, "chrome.exe")
        self.assertEqual(result["selected_pids"], [])
        self.assertEqual(result["active_pids_without_cmdline"], [1])

    def test_chatgpt_app_uses_the_same_renderer_role_rule(self):
        processes = [{"PID": 81, "ImageFileName": "ChatGPT.exe", "ExitTime": None},
                     {"PID": 82, "ImageFileName": "ChatGPT.exe", "ExitTime": None}]
        cmdlines = [{"PID": 81, "Process": "ChatGPT.exe", "Args": "--type=renderer --lang=en"},
                    {"PID": 82, "Process": "ChatGPT.exe", "Args": "--type=utility"}]
        result = MODULE.select_renderers(processes, cmdlines, "ChatGPT.exe")
        self.assertEqual(result["selected_pids"], [81])


if __name__ == "__main__":
    unittest.main()
