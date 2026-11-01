"""Post-capture scoring of a frozen RAM candidate against Chromium page ground truth.

The scorer receives known values; the parser and joiner do not. It handles only
the bold markers and hard line breaks used by these synthetic answers; it does
not claim a general Markdown-to-HTML equivalence algorithm.
"""

import argparse
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dom_message(rows, prefix):
    matching = [
        row for row in rows
        if row.get("tag") == "LI"
        and row.get("name") == "id"
        and isinstance(row.get("text"), str)
        and row["text"].startswith(prefix)
    ]
    if len(matching) != 1:
        raise ValueError(f"Expected one DOM {prefix!r} row, found {len(matching)}")
    row = matching[0]
    return row["value"], row["text"][len(prefix):].strip()


def render_synthetic_markdown(text):
    """Match the two observed Markdown decorations in the controlled replies."""
    return text.replace("**", "").replace("  \n", "\n")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--recovery", type=Path, required=True)
    cli.add_argument("--submit", type=Path, required=True)
    cli.add_argument("--observe", type=Path, required=True)
    cli.add_argument("--ids", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    recovery, submit, observe, ids = map(
        read, (args.recovery, args.submit, args.observe, args.ids)
    )
    if any(value.get("status") != "ok" for value in (submit, observe, ids)):
        raise ValueError("A page observation did not complete")
    if recovery.get("ground_truth_supplied") is not False:
        raise ValueError("Recovery must not have received ground truth")
    conversation = observe["page"]["url"].rstrip("/").split("/")[-1]
    rows = ids["page"]["uuid_attribute_hits"]
    user_id, ui_prompt = dom_message(rows, "You said:")
    assistant_id, ui_response = dom_message(rows, "ChatGPT said:")
    if ui_prompt != submit["prompt"]:
        raise ValueError("Submitted prompt differs from the visible user message")
    candidates = [
        row for row in recovery["candidate_turns"]
        if row["conversation_id"] == conversation
    ]
    if len(candidates) != 1:
        raise ValueError(f"Expected one candidate for the observed URL, got {len(candidates)}")
    candidate = candidates[0]
    checks = {
        "conversation_id": candidate["conversation_id"] == conversation,
        "user_message_id": candidate["user_message_id"] == user_id,
        "assistant_message_id": candidate["assistant_message_id"] == assistant_id,
        "prompt_exact": candidate["prompt"] == ui_prompt,
        "response_rendered_text": render_synthetic_markdown(candidate["response_markdown"]) == ui_response,
    }
    result = {
        "method": "post-capture scoring only; no ground truth supplied to RAM parser or joiner",
        "conversation_id": conversation,
        "submitted_utc": submit.get("submitted_utc", submit.get("clicked_utc")),
        "observed_utc": observe["ended_utc"],
        "total_ram_candidates": len(recovery["candidate_turns"]),
        "fields": checks,
        "matched_fields": sum(checks.values()),
        "all_five_match": all(checks.values()),
        "markdown_note": "Only literal ** markers and two-space Markdown hard line breaks are normalized for this synthetic reply",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
