"""Copy the tested core-event method and seal it before a new capture.

No capture, observation, prompt, answer, or ID is an input. A freeze is not itself
validation. Tests are synthetic regressions, not experimental repetitions.
"""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from cli_core_events import DEFAULT_CAP, METHOD_FILES


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--method", choices=("core-v1", "model-input-v1"), default="core-v1")
    args = cli.parse_args()
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parent
    files = []
    method_files = METHOD_FILES if args.method == "core-v1" else ("bounded_json.py", "cli_rpc_records.py", "cli_model_turns.py")
    for name in method_files:
        shutil.copyfile(source / name, target / name)
        raw = (target / name).read_bytes()
        files.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    result = {"method_version": "cli-" + args.method, "frozen_utc": datetime.now(timezone.utc).isoformat(),
              "cohort": "instrumented native Codex app-server stdio, not browser or TUI",
              "record_cap_bytes": DEFAULT_CAP, "encodings": ["utf-8", "utf-16-le"],
              "object_prefix": '{"type"',
              "accepted_types": ["item_completed", "task_complete", "agentMessage"],
              "process_selection": "all live inventoried native codex.exe backends; each map analyzed separately",
              "mapping_scope": "resident user space below 2^47; virtual gaps never bridged",
              "candidate_rule": "one exact turn-ID binding to one thread and one user/completion variant",
              "strong_fields": ["thread_id", "turn_id", "user_message_id", "prompt", "response"],
              "assistant_id_independently_bound": False, "known_values_supplied": False,
              "files": files}
    if args.method == "model-input-v1":
        result.update({"object_prefix": "public-RPC first keys plus compact {\"type\"",
                       "accepted_types": ["message with role=user and aligned user.text metadata", "turn/completed with final_answer agent item"],
                       "candidate_rule": "one exact turn ID, one tagged input, final agent variant and thread binding",
                       "strong_fields": ["thread_id", "turn_id", "prompt", "response", "agent_message_id"],
                       "assistant_id_independently_bound": True,
                       "api_user_item_id_recovered": False,
                       "identifier_boundary": "model_input_message_id is never renamed as an API user-item ID",
                       "timestamp_boundary": "model-input creation metadata is not a human submission timestamp"})
    with (target / "FROZEN_METHOD.json").open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
