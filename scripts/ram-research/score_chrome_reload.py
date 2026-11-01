"""Score a pre-reload Chrome turn against a blind post-reload RAM recovery.

Page observations are supplied only after the frozen renderer parser and
joiner have run and their output has been sealed. A zero candidate is a
reportable result, not a scoring exception.
"""

import argparse
import json
from pathlib import Path
import re

from score_chrome_state import dom_message, render_synthetic_markdown


CONVERSATION_URL = re.compile(
    r"^https://chatgpt\.com/uc/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def submitted_dom_rows(record):
    return [row for row in record["page"]["uuid_attribute_hits"]
            if row.get("tag") == "LI" and row.get("name") == "id"
            and isinstance(row.get("text"), str)
            and (row["text"].startswith("You said:") or
                 row["text"].startswith("ChatGPT said:"))]


def score(recovery, submit, before_observe, before_ids, reload, after_observe,
          after_ids, postacq_ids):
    observations = [submit, before_observe, before_ids, reload,
                    after_observe, after_ids, postacq_ids]
    if any(row.get("status") != "ok" for row in observations):
        raise ValueError("An independent page-control observation failed")
    if recovery.get("ground_truth_supplied") is not False:
        raise ValueError("RAM recovery had ground truth")
    target_ids = {row.get("target_id") for row in observations}
    if len(target_ids) != 1 or None in target_ids:
        raise ValueError("Page target changed during this same-tab trial")
    before_url = before_observe["page"]["url"]
    match = CONVERSATION_URL.fullmatch(before_url)
    if not match or before_ids["page"]["url"] != before_url:
        raise ValueError("No stable pre-reload anonymous conversation URL")
    if reload.get("browser_url_before") != before_url or not reload.get("reload_requested_utc"):
        raise ValueError("Reload was not requested on the observed conversation")
    for record in (after_observe, after_ids, postacq_ids):
        if record["page"]["url"] != "https://chatgpt.com/":
            raise ValueError("Post-reload page is not the new-chat URL")
    if submitted_dom_rows(after_ids) or submitted_dom_rows(postacq_ids):
        raise ValueError("A submitted message remained after reload")
    rows = before_ids["page"]["uuid_attribute_hits"]
    user_id, prompt = dom_message(rows, "You said:")
    assistant_id, response = dom_message(rows, "ChatGPT said:")
    if prompt != submit["prompt"] or prompt not in before_observe["page"]["textTail"]:
        raise ValueError("Pre-reload prompt disagrees across observations")
    if response not in before_observe["page"]["textTail"]:
        raise ValueError("Pre-reload response disagrees across observations")
    conversation_id = match.group(1)
    candidates = [row for row in recovery["candidate_turns"]
                  if row["conversation_id"].lower() == conversation_id.lower()]
    checks = []
    for row in candidates:
        fields = {
            "conversation_id": row["conversation_id"].lower() == conversation_id.lower(),
            "user_message_id": row["user_message_id"] == user_id,
            "assistant_message_id": row["assistant_message_id"] == assistant_id,
            "prompt_exact": row["prompt"] == prompt,
            "response_rendered_text": render_synthetic_markdown(row["response_markdown"]) == response,
        }
        checks.append({"fields": fields, "matched_fields": sum(fields.values())})
    return {
        "method": "post-seal pre/post-reload page scoring; no known values supplied to RAM parser",
        "ground_truth_supplied_to_score_only": True,
        "same_target": True,
        "pre_reload_completed_dom_pair": True,
        "post_reload_new_chat_without_submitted_dom_pair": True,
        "total_ram_candidates": len(recovery["candidate_turns"]),
        "target_conversation_candidates": len(candidates),
        "target_candidate_checks": checks,
        "target_reconstructed_5_of_5": len(checks) == 1 and checks[0]["matched_fields"] == 5,
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("recovery", "submit", "before-observe", "before-ids", "reload",
                 "after-observe", "after-ids", "postacq-ids", "output"):
        cli.add_argument("--" + name, type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = score(*(read(getattr(args, name.replace("-", "_")))
                     for name in ("recovery", "submit", "before-observe", "before-ids",
                                  "reload", "after-observe", "after-ids", "postacq-ids")))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "target_candidate_checks"}, indent=2))


if __name__ == "__main__":
    main()
