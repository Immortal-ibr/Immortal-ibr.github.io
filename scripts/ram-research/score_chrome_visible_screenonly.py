"""Score a blind visible-Chrome turn from a PNG, without a DOM answer-text probe.

The completed answer is transcribed from the actual page screenshot only after
the RAM output is sealed. This can independently score C/P/R, not DOM message
IDs. Parser inputs must never include these page observations.
"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

from score_chrome_reload import CONVERSATION_URL, read
from score_chrome_state import render_synthetic_markdown


REPOSITORY = Path(__file__).resolve().parents[2]


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def score(recovery, submit, before_count, screenshot_meta, postacq_count,
          acquisition, screenshot_sha256, response_transcription):
    controls = (submit, before_count, screenshot_meta, postacq_count)
    if any(row.get("status") != "ok" for row in controls):
        raise ValueError("A page control failed")
    if recovery.get("ground_truth_supplied") is not False:
        raise ValueError("RAM parser received ground truth")
    if submit.get("mode") != "submit_quiet" or submit.get("answer_text_observed") is not False:
        raise ValueError("Submission controller was not answer-text quiet")
    targets = {row.get("target_id") for row in controls}
    if len(targets) != 1 or None in targets:
        raise ValueError("The page target changed")
    before = before_count["page"]
    match = CONVERSATION_URL.fullmatch(before["url"])
    if not match or before["message_uuid_li_count"] != 2:
        raise ValueError("No two-message conversation page before acquisition")
    if postacq_count["page"] != before:
        raise ValueError("Page changed across acquisition")
    if (screenshot_meta.get("mode") != "screenshot"
            or screenshot_meta.get("browser_url_before") != before["url"]
            or screenshot_meta.get("png_sha256", "").upper() != screenshot_sha256.upper()):
        raise ValueError("Actual screenshot provenance disagrees")
    if acquisition.get("exit_code") != 0 or acquisition.get("status") != "captured_unvalidated":
        raise ValueError("Acquisition did not complete")
    if not (instant(submit["submitted_utc"]) < instant(before_count["ended_utc"])
            <= instant(screenshot_meta["started_utc"])
            < instant(screenshot_meta["ended_utc"])
            < instant(acquisition["started_utc"])
            < instant(acquisition["ended_utc"])
            < instant(postacq_count["started_utc"])):
        raise ValueError("Page/acquisition chronology disagrees")
    prompt = submit["prompt"]
    if not response_transcription or response_transcription in prompt:
        raise ValueError("Response transcription is empty or copied from prompt")
    if any(response_transcription in json.dumps(row, ensure_ascii=False) for row in controls):
        raise ValueError("Answer text was returned by the page controller")
    conversation_id = match.group(1)
    target = [row for row in recovery["candidate_turns"]
              if row["conversation_id"].lower() == conversation_id.lower()]
    checks = []
    for row in target:
        fields = {
            "conversation_id": True,
            "prompt_exact": row["prompt"] == prompt,
            "response_rendered_text": render_synthetic_markdown(row["response_markdown"]) == response_transcription,
        }
        checks.append({"fields": fields, "matched_fields": sum(fields.values())})
    result = {
        "method": "post-seal actual-screenshot C/P/R score; no DOM answer-text probe",
        "ground_truth_supplied_to_score_only": True,
        "same_target_across_acquisition": True,
        "two_message_elements_before_and_after_acquisition": True,
        "screenshot_sha256": screenshot_sha256.upper(),
        "answer_text_in_preacquisition_controller_json": False,
        "total_ram_candidates": len(recovery["candidate_turns"]),
        "target_conversation_candidates": len(target),
        "target_candidate_checks": checks,
        "target_reconstructed_3_of_3": len(checks) == 1 and checks[0]["matched_fields"] == 3,
        "independent_dom_message_ids_scored": False,
    }
    known = {
        "source": "host transcription of actual pre-acquisition PNG after blind RAM output seal",
        "screenshot_sha256": screenshot_sha256.upper(),
        "conversation_id": conversation_id,
        "prompt": prompt,
        "response": response_transcription,
        "independent_dom_message_ids_available": False,
    }
    return result, known


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ("recovery", "submit", "before-count", "screenshot-meta",
                 "postacq-count", "acquisition", "screenshot", "output", "known-output"):
        cli.add_argument("--" + name, type=Path, required=True)
    cli.add_argument("--response-transcription", required=True)
    args = cli.parse_args()
    for path in (args.output, args.known_output):
        if path.resolve().is_relative_to(REPOSITORY) or path.exists():
            raise ValueError("Score and known values must be new private outputs")
    screenshot_sha = hashlib.sha256(args.screenshot.read_bytes()).hexdigest().upper()
    result, known = score(*(read(path) for path in (
        args.recovery, args.submit, args.before_count, args.screenshot_meta,
        args.postacq_count, args.acquisition)), screenshot_sha,
        args.response_transcription)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.known_output.write_text(json.dumps(known, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
