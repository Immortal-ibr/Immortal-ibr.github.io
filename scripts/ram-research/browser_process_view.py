"""Print a compact process-role view from saved Volatility JSON output.

The source files must be the unedited JSON emitted by windows.pslist and
windows.cmdline for the *same* memory image. No PIDs or roles are hard-coded.
"""

import argparse
import json
import re
from pathlib import Path


TYPE_ARG = re.compile(r"(?:^|\s)--type=([^\s]+)")
UTILITY_ARG = re.compile(r"(?:^|\s)--utility-sub-type=([^\s]+)")


def read_rows(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list):
        raise ValueError(f"expected a JSON array in {path}")
    return rows


def role(command_line: str) -> str:
    match = TYPE_ARG.search(command_line)
    if not match:
        return "browser (no --type)"
    process_type = match.group(1).strip('"')
    if process_type == "utility":
        subtype = UTILITY_ARG.search(command_line)
        if subtype:
            return subtype.group(1).strip('"').rsplit(".", 1)[-1]
    return process_type


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pslist", type=Path)
    parser.add_argument("cmdline", type=Path)
    parser.add_argument("--name", default="chrome.exe")
    args = parser.parse_args()

    commands = {int(row["PID"]): str(row.get("Args") or "")
                for row in read_rows(args.cmdline) if "PID" in row}
    processes = [row for row in read_rows(args.pslist)
                 if str(row.get("ImageFileName", "")).casefold() == args.name.casefold()
                 and row.get("ExitTime") is None]
    processes.sort(key=lambda row: (int(row["PID"]), int(row["PPID"])))

    print("Source: Volatility windows.pslist + windows.cmdline (saved JSON)")
    print(f"Filter: active {args.name}; role from exact --type argument")
    print("PID    PPID   ROLE")
    print("-----  -----  --------------------------------")
    for row in processes:
        pid = int(row["PID"])
        print(f"{pid:<5}  {int(row['PPID']):<5}  {role(commands.get(pid, ''))}")


if __name__ == "__main__":
    main()
