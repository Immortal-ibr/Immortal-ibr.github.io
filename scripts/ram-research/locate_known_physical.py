"""Locate a known synthetic value in verified gzip RAM without publishing bytes.

This is post-hoc ground-truth-assisted analysis, never blind reconstruction.
The private output records physical offsets and nearby marker distances but no
surrounding memory text. Even a marker match is not process attribution.
"""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import indexed_gzip

from bounded_json import frame_end, strict_json
from scan_verified_gzip import REPOSITORY, sha256_file


MARKERS = {
    "textTail_json_key": b'"textTail"',
    "chatgpt_said_label": b"ChatGPT said:",
    "assistant_json_key": b'"assistant"',
    "user_json_key": b'"user"',
    "sse_data_prefix": b"data: {",
}


def find_offsets(source, needle, chunk_size=8 * 1024 * 1024):
    if not needle or chunk_size <= 0:
        raise ValueError("Needle and chunk size must be nonempty")
    offsets = []
    tail = b""
    processed = 0
    digest = hashlib.sha256()
    while block := source.read(chunk_size):
        digest.update(block)
        window = tail + block
        base = processed - len(tail)
        limit = max(0, len(window) - len(needle) + 1)
        cursor = 0
        while (found := window.find(needle, cursor)) != -1 and found < limit:
            offsets.append(base + found)
            cursor = found + 1
        tail = window[limit:]
        processed += len(block)
    cursor = 0
    while (found := tail.find(needle, cursor)) != -1:
        offsets.append(processed - len(tail) + found)
        cursor = found + 1
    return offsets, processed, digest.hexdigest().upper()


def nearest_marker_distances(context, hit_start, hit_end):
    distances = {}
    for name, marker in MARKERS.items():
        positions = []
        cursor = 0
        while (found := context.find(marker, cursor)) != -1:
            positions.append(found)
            cursor = found + 1
        distances[name] = min(
            (found - hit_start if found <= hit_start else found - hit_end for found in positions),
            key=abs,
            default=None,
        )
    return distances


def classify_texttail_context(context, hit_start, needle):
    """Test whether a byte hit lies inside one strictly decoded textTail JSON string."""
    key = b'"textTail"'
    positions = []
    cursor = 0
    while (found := context.find(key, cursor)) != -1 and found < hit_start:
        positions.append(found)
        cursor = found + 1
    for found in reversed(positions):
        position = found + len(key)
        while position < len(context) and context[position] in b" \t\r\n":
            position += 1
        if context[position:position + 1] != b":":
            continue
        position += 1
        while position < len(context) and context[position] in b" \t\r\n":
            position += 1
        if context[position:position + 1] != b'"':
            continue
        end = position + 1
        escaped = False
        while end < len(context):
            byte = context[end]
            if escaped:
                escaped = False
            elif byte == 0x5C:
                escaped = True
            elif byte == 0x22:
                end += 1
                break
            end += 1
        else:
            continue
        try:
            encoded_value = context[position:end]
            decoded_value = encoded_value.decode("utf-8", errors="strict")
            value, consumed = json.JSONDecoder().raw_decode(decoded_value)
        except (UnicodeError, ValueError):
            continue
        if not isinstance(value, str) or consumed != len(decoded_value):
            continue
        if not position <= hit_start or hit_start + len(needle) > end:
            continue
        decoded_needle = needle.decode("utf-8", errors="strict")
        return {
            "hit_inside_parsed_textTail_string": True,
            "exact_value_in_decoded_textTail": decoded_needle in value,
            "chatgpt_said_label_directly_before_value":
                "ChatGPT said: " + decoded_needle in value,
        }
    return {
        "hit_inside_parsed_textTail_string": False,
        "exact_value_in_decoded_textTail": False,
        "chatgpt_said_label_directly_before_value": False,
    }


def classify_observation_object(context, hit_start, needle):
    """Recognize the probe's URL/user/assistant/textTail object without outputting it."""
    decoded_needle = needle.decode("utf-8", errors="strict")
    for start in range(hit_start - 1, max(-1, hit_start - 4096), -1):
        if context[start:start + 1] != b"{":
            continue
        try:
            end = frame_end(context[start:], "utf-8")
            if end is None or start + end < hit_start + len(needle):
                continue
            payload = strict_json(context[start:start + end].decode("utf-8", errors="strict"))
        except (ValueError, UnicodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if not all(key in payload for key in ("url", "user", "assistant", "textTail")):
            continue
        tail = payload["textTail"]
        assistants = payload["assistant"]
        return {
            "parsed_probe_object_shape": isinstance(payload["url"], str)
            and isinstance(payload["user"], list)
            and isinstance(assistants, list)
            and isinstance(tail, str),
            "chatgpt_url": isinstance(payload["url"], str)
            and payload["url"].startswith("https://chatgpt.com/"),
            "answer_in_textTail": isinstance(tail, str) and decoded_needle in tail,
            "answer_in_assistant_array": isinstance(assistants, list)
            and any(isinstance(item, str) and decoded_needle in item for item in assistants),
        }
    return {
        "parsed_probe_object_shape": False,
        "chatgpt_url": False,
        "answer_in_textTail": False,
        "answer_in_assistant_array": False,
    }


def inspect(archive, archive_sha256, raw_size, raw_sha256, value, radius=8192):
    if sha256_file(archive) != archive_sha256.upper():
        raise ValueError("Archive SHA-256 does not match")
    hits = {}
    with gzip.open(archive, "rb") as source:
        for encoding in ("utf-8", "utf-16-le"):
            # Verify the full raw stream on each encoding pass; one pass would
            # be enough for integrity, but keeps each search independent.
            source.seek(0)
            offsets, size, digest = find_offsets(source, value.encode(encoding))
            if size != raw_size or digest != raw_sha256.upper():
                raise ValueError("Decompressed image does not match")
            hits[encoding] = offsets
    observations = []
    with indexed_gzip.IndexedGzipFile(filename=str(archive)) as source:
        for encoding, offsets in hits.items():
            needle = value.encode(encoding)
            for offset in offsets:
                begin = max(0, offset - radius)
                end = min(raw_size, offset + len(needle) + radius)
                source.seek(begin)
                context = source.read(end - begin)
                relative = offset - begin
                if context[relative:relative + len(needle)] != needle:
                    raise ValueError("Indexed replay disagrees with streamed hit")
                observations.append({
                    "encoding": encoding,
                    "physical_offset": offset,
                    "physical_page": offset // 4096,
                    "offset_in_page": offset % 4096,
                    "context_sha256": hashlib.sha256(context).hexdigest().upper(),
                    "nearest_marker_byte_distances": nearest_marker_distances(
                        context, relative, relative + len(needle)
                    ),
                    "textTail_json_evidence": classify_texttail_context(
                        context, relative, needle
                    ) if encoding == "utf-8" else None,
                    "probe_object_evidence": classify_observation_object(
                        context, relative, needle
                    ) if encoding == "utf-8" else None,
                })
    return {
        "method": "post-hoc known synthetic value in full verified physical RAM",
        "ground_truth_supplied": True,
        "value_sha256": hashlib.sha256(value.encode()).hexdigest().upper(),
        "value_utf8_bytes": len(value.encode()),
        "archive_sha256": archive_sha256.upper(),
        "raw_sha256": raw_sha256.upper(),
        "raw_bytes": raw_size,
        "hits": observations,
        "warning": "Offsets and nearby marker distances do not establish process ownership or application provenance.",
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--archive-sha256", required=True)
    cli.add_argument("--raw-size", type=int, required=True)
    cli.add_argument("--raw-sha256", required=True)
    cli.add_argument("--value", required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if args.raw_size <= 0 or not args.value:
        raise ValueError("Raw size and known value must be nonempty")
    for digest in (args.archive_sha256, args.raw_sha256):
        if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ValueError("Expected SHA-256 values must be 64 hex digits")
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Physical hit offsets must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    result = inspect(
        args.archive, args.archive_sha256, args.raw_size, args.raw_sha256, args.value
    )
    with output.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, ensure_ascii=True)
        target.write("\n")
    print(json.dumps({
        "utf8_hits": sum(hit["encoding"] == "utf-8" for hit in result["hits"]),
        "utf16le_hits": sum(hit["encoding"] == "utf-16-le" for hit in result["hits"]),
        "archive_and_raw_verified": True,
        "output_is_private": True,
    }))


if __name__ == "__main__":
    main()
