"""Select every active Chromium renderer from image-derived Volatility JSON.

This is process triage, not content discovery. No prompt, answer, conversation
identifier, or memory offset is accepted as input. Keep the source cmdline JSON
private: it can contain unrelated profile paths and browsing details.
"""

import argparse
import json
import re
from pathlib import Path


RENDERER_ARG = re.compile(r"(?<!\S)--type=renderer(?=\s|$)")


def select_renderers(pslist, cmdlines, process_name):
    expected = process_name.casefold()
    active = {}
    exited = []
    for row in pslist:
        if str(row.get("ImageFileName", "")).casefold() != expected:
            continue
        pid = int(row["PID"])
        if row.get("ExitTime") is None:
            active[pid] = row
        else:
            exited.append(pid)

    renderer_cmdlines = set()
    other_cmdlines = set()
    for row in cmdlines:
        if str(row.get("Process", "")).casefold() != expected:
            continue
        pid = int(row["PID"])
        if pid not in active:
            continue
        if RENDERER_ARG.search(str(row.get("Args") or "")):
            renderer_cmdlines.add(pid)
        else:
            other_cmdlines.add(pid)

    selected = sorted(renderer_cmdlines)
    return {
        "process_name": process_name,
        "selection_rule": (
            "matching image name, null ExitTime in windows.pslist, and exact "
            "--type=renderer argument in windows.cmdline"
        ),
        "selected_pids": selected,
        "active_browser_pids": sorted(active),
        "active_pids_without_cmdline": sorted(
            set(active) - renderer_cmdlines - other_cmdlines
        ),
        "exited_browser_pids": sorted(set(exited)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pslist", required=True, type=Path)
    parser.add_argument("--cmdline", required=True, type=Path)
    parser.add_argument("--process-name", required=True,
                        choices=("chrome.exe", "msedge.exe", "ChatGPT.exe"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    pslist = json.loads(args.pslist.read_text(encoding="utf-8-sig"))
    cmdlines = json.loads(args.cmdline.read_text(encoding="utf-8-sig"))
    if not isinstance(pslist, list) or not isinstance(cmdlines, list):
        raise ValueError("Volatility JSON must contain top-level row arrays")
    result = select_renderers(pslist, cmdlines, args.process_name)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"{len(result['selected_pids'])} active {args.process_name} renderers; "
        f"{len(result['active_pids_without_cmdline'])} active browser PIDs "
        "lack a command line"
    )


if __name__ == "__main__":
    main()
