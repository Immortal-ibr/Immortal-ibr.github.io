"""Summarize image-derived presence of prior CLI PIDs after TUI exit.

Reads only Volatility outputs from the specified private trial folder and emits
selected PID metadata; it makes no inference about erased content.
"""

import argparse
import json
from pathlib import Path


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--trial", type=Path, required=True)
    cli.add_argument("--pids", type=int, nargs="+", required=True)
    cli.add_argument("--output", default="process_evidence_exit.json")
    args = cli.parse_args()
    trial = args.trial.resolve()
    private = trial / "private"
    sources = {}
    for name in ("pslist", "psscan", "cmdline"):
        path = private / f"{name}.json"
        sources[name] = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else []
    out = {"trial_id": trial.name,
           "method": "image-derived Volatility pslist, psscan, and cmdline lookup for prior CLI PIDs",
           "processes": [],
           "limitations": "A missing or exited process object is not proof that its content was erased from physical RAM."}
    for pid in args.pids:
        record = {"pid": pid, "sources": {}}
        for name, rows in sources.items():
            matches = []
            for row in rows:
                if int(row.get("PID", -1)) != pid:
                    continue
                if name == "cmdline":
                    matches.append({"image_file_name": row.get("Process"),
                                    "trial_path_in_command_line": "cli_tui_active_010" in str(row.get("Args", ""))})
                else:
                    matches.append({"image_file_name": row.get("ImageFileName"),
                                    "ppid": row.get("PPID"),
                                    "create_time": row.get("CreateTime"),
                                    "exit_time": row.get("ExitTime")})
            record["sources"][name] = matches
        out["processes"].append(record)
    (trial / args.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
