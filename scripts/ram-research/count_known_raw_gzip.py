"""Count known synthetic trial values in a verified compressed RAM image.

This is a post-hoc physical-byte diagnostic, never the reconstruction method.
The input observations and output stay private: the image can contain account
data, and physical hits have no process attribution.
"""

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path


UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
SYNTHETIC_LABEL = re.compile(r"\bsynthetic label\s+([a-z]+-[a-z]+-\d+)\b", re.I)
ANSWER_NAMES = (
    re.compile(r"\bName:\s*([A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+)"),
    re.compile(r"\bcalled\s+([A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+)"),
    re.compile(r"\bmuseum,\s+([A-Z][A-Za-z]+\s+[A-Z][A-Za-z]+)"),
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def known_values(submission: dict, observation: dict, ids: dict) -> dict[str, str]:
    prompt = submission["prompt"]
    page = observation["page"]
    if prompt not in page["textTail"]:
        raise ValueError("Observed page did not contain the submitted synthetic prompt")
    marker = UUID.search(prompt) or SYNTHETIC_LABEL.search(prompt)
    conversation = UUID.search(page["url"])
    if not marker or not conversation:
        raise ValueError("Synthetic marker or conversation ID is absent")
    li = [hit for hit in ids["page"]["uuid_attribute_hits"]
          if hit["tag"] == "LI" and hit["name"] == "id" and UUID.fullmatch(hit["value"])]
    users = [hit for hit in li if prompt in (hit.get("text") or "")]
    assistants = [hit for hit in li if hit not in users]
    if len(users) != 1 or len(assistants) != 1:
        raise ValueError("Could not identify the two LI message elements")
    answer_name = next((match for pattern in ANSWER_NAMES
                        if (match := pattern.search(assistants[0].get("text") or ""))), None)
    if not answer_name:
        raise ValueError("The expected synthetic two-word answer name is absent")
    user_ids = [users[0]["value"]]
    assistant_ids = [assistants[0]["value"]]
    if len(user_ids) != 1 or len(assistant_ids) != 1 or user_ids[0] == assistant_ids[0]:
        raise ValueError("Could not independently identify both LI message IDs")
    if conversation.group().lower() not in ids["page"]["url"].lower():
        raise ValueError("Observation and DOM-ID URLs disagree")
    return {
        "conversation_id": conversation.group(),
        "prompt_marker": marker.group(),
        "answer_name": answer_name.group(1),
        "user_message_id": user_ids[0],
        "assistant_message_id": assistant_ids[0],
    }


def count_stream(source, needles: dict[str, bytes], chunk_size: int = 8 * 1024 * 1024) -> tuple[dict[str, int], int, str]:
    if chunk_size <= 0 or not needles or any(not needle for needle in needles.values()):
        raise ValueError("Chunk size and needles must be nonempty")
    counts = dict.fromkeys(needles, 0)
    max_needle = max(map(len, needles.values()))
    remainder = b""
    total = 0
    digest = hashlib.sha256()
    while chunk := source.read(chunk_size):
        digest.update(chunk)
        total += len(chunk)
        data = remainder + chunk
        safe_start_limit = max(0, len(data) - max_needle + 1)
        for label, needle in needles.items():
            cursor = 0
            while (offset := data.find(needle, cursor)) != -1 and offset < safe_start_limit:
                counts[label] += 1
                cursor = offset + 1
        remainder = data[safe_start_limit:]
    for label, needle in needles.items():
        cursor = 0
        while (offset := remainder.find(needle, cursor)) != -1:
            counts[label] += 1
            cursor = offset + 1
    return counts, total, digest.hexdigest().upper()


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--acquisition", type=Path, required=True)
    cli.add_argument("--submission", type=Path, required=True)
    cli.add_argument("--observation", type=Path, required=True)
    cli.add_argument("--ids", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    values = known_values(load(args.submission), load(args.observation), load(args.ids))
    needles = {f"{name}/{encoding}": value.encode(encoding)
               for name, value in values.items() for encoding in ("utf-8", "utf-16-le")}
    with gzip.open(args.archive, "rb") as source:
        counts, raw_length, raw_sha = count_stream(source, needles)
    acquisition = load(args.acquisition)
    if raw_length != acquisition["raw_logical_bytes"] or raw_sha != acquisition["raw_sha256"].upper():
        raise ValueError("Decompressed image does not match acquisition length and SHA-256")
    result = {
        "method": "Post-hoc exact synthetic-byte count over full sparse raw image; no process attribution",
        "trial_id": acquisition["trial_id"],
        "image_sha256_verified": True,
        "raw_logical_bytes": raw_length,
        "counts": counts,
        "warning": "Some hits may be observer/controller copies; this does not identify a browser process or prove recoverability of a conversation",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
