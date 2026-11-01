"""Post-seal score for a reload trial with no pre-acquisition answer-text probe.

The response fragment is manually transcribed from the actual screenshot
after acquisition. The page controller returned only a URL and message count,
never the answer text. Unlike DOM-ID trials, this can score only C/P/answer
fragment and does not independently verify message IDs or a full response.
"""

import argparse
import hashlib
import json
from pathlib import Path

from score_chrome_reload import CONVERSATION_URL, read


REPOSITORY = Path(__file__).resolve().parents[2]


def score(recovery, submit, before_count, reload, after_count, postacq_count,
          screenshot_meta, screenshot_sha256, answer_fragment):
    controls = [submit, before_count, reload, after_count, postacq_count, screenshot_meta]
    if any(row.get("status") != "ok" for row in controls):
        raise ValueError("A page control failed")
    if recovery.get("ground_truth_supplied") is not False:
        raise ValueError("RAM parser received ground truth")
    if submit.get("mode") != "submit_quiet" or submit.get("answer_text_observed") is not False:
        raise ValueError("Submission controller was not answer-text quiet")
    target_ids = {row.get("target_id") for row in controls}
    if len(target_ids) != 1 or None in target_ids:
        raise ValueError("The page target changed")
    before_url = before_count["page"]["url"]
    match = CONVERSATION_URL.fullmatch(before_url)
    if not match or before_count["page"]["message_uuid_li_count"] != 2:
        raise ValueError("No completed two-message page before reload")
    if reload.get("browser_url_before") != before_url or not reload.get("reload_requested_utc"):
        raise ValueError("Reload was not requested on the completed page")
    if (screenshot_meta.get("mode") != "screenshot"
            or screenshot_meta.get("browser_url_before") != before_url
            or screenshot_meta.get("png_sha256", "").upper() != screenshot_sha256.upper()):
        raise ValueError("Actual pre-reload screenshot provenance disagrees")
    for row in (after_count, postacq_count):
        if row["page"] != {"url": "https://chatgpt.com/", "message_uuid_li_count": 0}:
            raise ValueError("Post-reload page is not empty new chat")
    prompt = submit["prompt"]
    if not answer_fragment or answer_fragment in prompt:
        raise ValueError("Answer fragment is empty or appears in the submitted prompt")
    if any(answer_fragment in json.dumps(row, ensure_ascii=False) for row in controls):
        raise ValueError("Answer fragment was returned by the page controller")
    conversation_id = match.group(1)
    target = [row for row in recovery["candidate_turns"]
              if row["conversation_id"].lower() == conversation_id.lower()]
    checks = []
    for row in target:
        fields = {"conversation_id": True,
                  "prompt_exact": row["prompt"] == prompt,
                  "screenshot_answer_fragment": answer_fragment in row["response_markdown"]}
        checks.append({"fields": fields, "matched_fields": sum(fields.values())})
    result = {
        "method": "post-seal screenshot-only C/P/answer-fragment score",
        "ground_truth_supplied_to_score_only": True,
        "same_target": True,
        "pre_reload_two_message_elements": True,
        "post_reload_empty_new_chat": True,
        "screenshot_sha256": screenshot_sha256.upper(),
        "answer_fragment_transcribed_from_screenshot": True,
        "answer_fragment_in_preacquisition_controller_json": False,
        "total_ram_candidates": len(recovery["candidate_turns"]),
        "target_conversation_candidates": len(target),
        "target_candidate_checks": checks,
        "target_reconstructed_3_of_3": len(checks) == 1 and checks[0]["matched_fields"] == 3,
        "independent_message_ids_or_full_response_scored": False,
    }
    known = {
        "source": "host transcription of actual pre-acquisition PNG after blind RAM output seal",
        "screenshot_sha256": screenshot_sha256.upper(),
        "conversation_id": conversation_id,
        "prompt": prompt,
        "response": answer_fragment,
        "response_is_fragment": True,
    }
    return result, known


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("recovery", "submit", "before-count", "reload", "after-count",
                 "postacq-count", "screenshot-meta", "screenshot", "output", "known-output"):
        cli.add_argument("--" + name, type=Path, required=True)
    cli.add_argument("--answer-fragment", required=True)
    args = cli.parse_args()
    for path in (args.output, args.known_output):
        if path.resolve().is_relative_to(REPOSITORY) or path.exists():
            raise ValueError("Score and known values must be new private outputs")
    screenshot_sha = hashlib.sha256(args.screenshot.read_bytes()).hexdigest().upper()
    result, known = score(*(read(getattr(args, name.replace("-", "_")))
                            for name in ("recovery", "submit", "before-count", "reload",
                                         "after-count", "postacq-count", "screenshot-meta")),
                          screenshot_sha, args.answer_fragment)
    for path, value in ((args.output, result), (args.known_output, known)):
        with path.open("x", encoding="utf-8") as target:
            json.dump(value, target, indent=2, ensure_ascii=False)
            target.write("\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "target_candidate_checks"}, indent=2))


if __name__ == "__main__":
    main()
