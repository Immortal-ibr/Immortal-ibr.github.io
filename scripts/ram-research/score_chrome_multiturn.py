"""Post-seal score of two observed turns in one anonymous Chrome conversation.

The frozen RAM parser and joiner receive none of these inputs. This scorer
checks the first turn's DOM IDs both before and after the second submission,
then compares candidates by conversation and assistant-message ID. No partial
or approximate text match counts as a recovered field.
"""

import argparse
import json
from pathlib import Path
import re

from score_chrome_state import render_synthetic_markdown


UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def li_turns(observation):
    rows = [row for row in observation["page"]["uuid_attribute_hits"]
            if row.get("tag") == "LI" and row.get("name") == "id"]
    if len(rows) % 2 or not rows:
        raise ValueError("Expected an even, nonzero number of LI message IDs")
    turns = []
    for index in range(0, len(rows), 2):
        user, assistant = rows[index:index + 2]
        user_text, assistant_text = user.get("text"), assistant.get("text")
        if (not isinstance(user_text, str) or not user_text.startswith("You said:")
                or not isinstance(assistant_text, str)
                or not assistant_text.startswith("ChatGPT said:")
                or not UUID.fullmatch(user.get("value", ""))
                or not UUID.fullmatch(assistant.get("value", ""))):
            raise ValueError("DOM messages are not alternating complete user/assistant pairs")
        turns.append({"user_message_id": user["value"],
                      "assistant_message_id": assistant["value"],
                      "prompt": user_text[len("You said:"):].strip(),
                      "response": assistant_text[len("ChatGPT said:"):].strip()})
    return turns


def score(recovery, first_submit, first_ids, second_submit, second_ids):
    if recovery.get("ground_truth_supplied") is not False:
        raise ValueError("RAM recovery is not marked blind")
    if any(item.get("status") != "ok" for item in
           (first_submit, first_ids, second_submit, second_ids)):
        raise ValueError("Incomplete page observation")
    if first_submit.get("target_id") != second_submit.get("target_id"):
        raise ValueError("Submissions used different DevTools page targets")
    before, after = li_turns(first_ids), li_turns(second_ids)
    if len(before) != 1 or len(after) != 2 or before[0] != after[0]:
        raise ValueError("First DOM turn was not stable across second submission")
    if after[0]["prompt"] != first_submit.get("prompt"):
        raise ValueError("First submitted and visible prompts differ")
    if after[1]["prompt"] != second_submit.get("prompt"):
        raise ValueError("Second submitted and visible prompts differ")
    first_url, second_url = first_ids["page"]["url"], second_ids["page"]["url"]
    if first_url != second_url or not first_url.startswith("https://chatgpt.com/uc/"):
        raise ValueError("Turn observations did not stay in one anonymous conversation")
    conversation_id = first_url.rstrip("/").split("/")[-1]
    if not UUID.fullmatch(conversation_id):
        raise ValueError("Observed conversation URL lacks an ID")
    candidates = recovery.get("candidate_turns", [])
    scores = []
    for index, observed in enumerate(after, start=1):
        matches = [candidate for candidate in candidates
                   if candidate.get("conversation_id") == conversation_id
                   and candidate.get("assistant_message_id") == observed["assistant_message_id"]]
        if len(matches) > 1:
            raise ValueError("More than one RAM candidate has this assistant ID")
        candidate = matches[0] if matches else None
        checks = {"conversation_id": bool(candidate) and candidate.get("conversation_id") == conversation_id,
                  "user_message_id": bool(candidate) and candidate.get("user_message_id") == observed["user_message_id"],
                  "assistant_message_id": bool(candidate) and candidate.get("assistant_message_id") == observed["assistant_message_id"],
                  "prompt_exact": bool(candidate) and candidate.get("prompt") == observed["prompt"],
                  "response_rendered_text": bool(candidate) and
                  render_synthetic_markdown(candidate.get("response_markdown", "")) == observed["response"]}
        scores.append({"turn_index": index, "candidate_found": candidate is not None,
                       "fields": checks, "matched_fields": sum(checks.values()),
                       "all_five_match": all(checks.values())})
    expected_pairs = {(turn["user_message_id"], turn["assistant_message_id"]) for turn in after}
    same_conversation = [candidate for candidate in candidates
                         if candidate.get("conversation_id") == conversation_id]
    unexpected = sum((candidate.get("user_message_id"), candidate.get("assistant_message_id"))
                     not in expected_pairs for candidate in same_conversation)
    return {"method": "post-seal comparison of two stable DOM turns; no ground truth supplied to RAM parser",
            "ground_truth_supplied_to_score_only": True,
            "conversation_id_private": conversation_id,
            "submitted_utc_private": [first_submit.get("submitted_utc"), second_submit.get("submitted_utc")],
            "observed_utc_private": [first_ids.get("ended_utc"), second_ids.get("ended_utc")],
            "total_ram_candidates": len(candidates),
            "same_conversation_candidates": len(same_conversation),
            "unexpected_same_conversation_pairs": unexpected,
            "turns": scores,
            "markdown_note": "Only literal ** markers and two-space hard line breaks normalized"}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("recovery", "first-submit", "first-ids", "second-submit", "second-ids", "output"):
        cli.add_argument("--" + name, type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = score(*(read(path) for path in
                     (args.recovery, args.first_submit, args.first_ids,
                      args.second_submit, args.second_ids)))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total_ram_candidates": result["total_ram_candidates"],
                      "same_conversation_candidates": result["same_conversation_candidates"],
                      "unexpected_same_conversation_pairs": result["unexpected_same_conversation_pairs"],
                      "turn_scores": [turn["matched_fields"] for turn in result["turns"]]}))


if __name__ == "__main__":
    main()
