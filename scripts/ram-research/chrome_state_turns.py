"""Join completed visible turns inside bounded Chrome state records.

The join uses message order, role, and parentMessageId inside one parsed JSON
object. It receives no ground-truth strings. It does not infer timestamps or
claim that every surviving state copy represents a distinct submission.
"""

import argparse
import json
from pathlib import Path


def reconstruct(parsed_files):
    candidates = {}
    audit = []
    for parsed_file in parsed_files:
        parsed = json.loads(parsed_file.read_text(encoding="utf-8"))
        if parsed.get("ground_truth_supplied") is not False:
            raise ValueError(f"Ground-truth status is not false: {parsed_file}")
        audit.append({
            "parsed_file": str(parsed_file),
            "complete_records": parsed["unique_complete_records"],
        })
        for record in parsed["records"]:
            state = record["state"]
            messages = state["messages"]
            if len(messages) < 2:
                continue
            last = messages[-1]
            previous = messages[-2]
            if (
                last.get("role") != "assistant"
                or previous.get("role") != "user"
                or state.get("parentMessageId") != last.get("id")
                or not previous.get("content")
                or not last.get("content")
            ):
                continue
            key = (
                state["backendConversationId"],
                previous["id"],
                last["id"],
                previous["content"],
                last["content"],
            )
            if key not in candidates:
                candidates[key] = {
                    "conversation_id": key[0],
                    "user_message_id": key[1],
                    "assistant_message_id": key[2],
                    "prompt": key[3],
                    "response_markdown": key[4],
                    "user_message_count": state.get("userMessageCount"),
                    "support": [],
                }
            candidates[key]["support"].append({
                "parsed_file": str(parsed_file),
                "record_sha256": record["sha256"],
                "encoding": record["encoding"],
                "virtual_addresses": record["virtual_addresses"],
                "contains_rendered_html": "renderedHtml" in last,
            })
    return {
        "method": "bounded state object; adjacent user/assistant messages; parentMessageId equals final assistant ID",
        "ground_truth_supplied": False,
        "audit": audit,
        "candidate_turns": list(candidates.values()),
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--parsed", required=True, type=Path, action="append")
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    result = reconstruct(args.parsed)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=True)
    print(json.dumps({
        "parsed_files": len(args.parsed),
        "candidate_turns": len(result["candidate_turns"]),
    }, indent=2))


if __name__ == "__main__":
    main()
