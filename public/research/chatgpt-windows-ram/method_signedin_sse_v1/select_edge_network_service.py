"""Select the one live Edge NetworkService utility from image-derived metadata.

No target conversation, prompt, response, identifier or memory offset is read.
Private process command lines remain in the input JSON outside the blog.
"""

import argparse
import json
from pathlib import Path
import re


NETWORK_ARG = re.compile(r"(?<!\S)--utility-sub-type=network\.mojom\.NetworkService(?=\s|$)")


def select(pslist, cmdlines):
    active = {int(row["PID"]) for row in pslist
              if str(row.get("ImageFileName", "")).casefold() == "msedge.exe"
              and row.get("ExitTime") is None}
    selected = sorted({int(row["PID"]) for row in cmdlines
                       if str(row.get("Process", "")).casefold() == "msedge.exe"
                       and int(row["PID"]) in active
                       and NETWORK_ARG.search(str(row.get("Args") or ""))})
    if len(selected) != 1:
        raise ValueError(f"Expected one active Edge NetworkService; found {len(selected)}")
    return {"selection_rule": "active msedge.exe in windows.pslist plus exact NetworkService utility subtype in windows.cmdline",
            "selected_pid": selected[0], "ground_truth_supplied": False}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--pslist", type=Path, required=True)
    cli.add_argument("--cmdline", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = select(json.loads(args.pslist.read_text(encoding="utf-8-sig")),
                    json.loads(args.cmdline.read_text(encoding="utf-8-sig")))
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
        target.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
