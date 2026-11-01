"""Post-hoc provenance check for known synthetic text in a process map.

This is not a blind reconstruction method. It inspects only already-known
synthetic values, keeps all surrounding bytes private, and emits structural
features rather than account content or text excerpts.
"""

import argparse
from bisect import bisect_right
import hashlib
import json
import os
from pathlib import Path
import sys


USER_LIMIT = 1 << 47
WINDOW_RADIUS = 8192
KEYS = {
    "textTail": b"textTail",
    "user": b'"user"',
    "assistant": b'"assistant"',
    "page": b'"page"',
    "dataConversation": b"dataConversation",
    "chatgpt_said": b"ChatGPT said:",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def occurrences(data: bytes, needle: bytes):
    cursor = 0
    while (position := data.find(needle, cursor)) != -1:
        yield position
        cursor = position + 1


def mapped_rows(rows, image_size: int):
    accepted = []
    for row in rows:
        physical, virtual, size = (int(row[name]) for name in ("Physical", "Virtual", "Size"))
        if 0 <= physical and 0 < size and virtual < USER_LIMIT and physical + size <= image_size:
            accepted.append((virtual, virtual + size, physical))
    accepted.sort()
    overlaps = sum(right[0] < left[1] for left, right in zip(accepted, accepted[1:]))
    if overlaps:
        raise ValueError(f"Process map has {overlaps} overlapping virtual intervals")
    return accepted


def virtual_window(image, intervals, starts, begin: int, end: int) -> tuple[bytes, int]:
    """Read mapped bytes in [begin,end), zero-filling unmapped gaps."""
    output = bytearray(max(0, end - begin))
    mapped = 0
    cursor = begin
    while cursor < end:
        index = bisect_right(starts, cursor) - 1
        if index >= 0 and cursor < intervals[index][1]:
            row_begin, row_end, physical = intervals[index]
            take = min(end, row_end) - cursor
            image.seek(physical + cursor - row_begin)
            chunk = image.read(take)
            if len(chunk) != take:
                raise IOError("Short read from mapped physical interval")
            output[cursor - begin:cursor - begin + take] = chunk
            mapped += take
            cursor += take
        else:
            next_start = intervals[index + 1][0] if index + 1 < len(intervals) else end
            cursor = min(end, next_start)
    return bytes(output), mapped


def nearest_offsets(context: bytes, centre: int, marker: bytes) -> list[int]:
    offsets = [position - centre for position in occurrences(context, marker)]
    return sorted(offsets, key=lambda offset: (abs(offset), offset))[:4]


def analyze(image_path: Path, map_path: Path, known_path: Path, observation_path: Path):
    known = read_json(known_path)
    observed = read_json(observation_path)["page"]["textTail"]
    values = {name: known[name].encode("utf-8") for name in ("prompt", "response")}
    if any(not value or value not in observed.encode("utf-8") for value in values.values()):
        raise ValueError("The known values are absent from the selected observation")
    raw_observation = observed.encode("utf-8")
    json_observation = json.dumps(observed, ensure_ascii=False)[1:-1].encode("utf-8")
    image_size = image_path.stat().st_size
    intervals = mapped_rows(read_json(map_path), image_size)
    starts = [row[0] for row in intervals]
    hits = []
    with image_path.open("rb") as image:
        for virtual, end, physical in intervals:
            size = end - virtual
            image.seek(physical)
            row_data = image.read(size)
            if len(row_data) != size:
                raise IOError("Short process-map read")
            for label, value in values.items():
                for offset in occurrences(row_data, value):
                    hit_va = virtual + offset
                    begin = max(0, hit_va - WINDOW_RADIUS)
                    window_end = min(USER_LIMIT, hit_va + len(value) + WINDOW_RADIUS)
                    context, mapped = virtual_window(image, intervals, starts, begin, window_end)
                    centre = hit_va - begin
                    features = {name: nearest_offsets(context, centre, marker)
                                for name, marker in KEYS.items()}
                    features["other_value"] = nearest_offsets(
                        context, centre, values["response" if label == "prompt" else "prompt"])
                    features["full_raw_observation"] = nearest_offsets(
                        context, centre, raw_observation)
                    features["full_json_escaped_observation"] = nearest_offsets(
                        context, centre, json_observation)
                    hits.append({"label": label, "virtual_private": hit_va,
                                 "physical_private": physical + offset,
                                 "mapped_context_bytes": mapped,
                                 "context_length": len(context), "offsets": features})
    grouped = {label: [hit for hit in hits if hit["label"] == label] for label in values}
    return {
        "method": "post-hoc known-value context scan; not blind reconstruction",
        "process_map": map_path.name,
        "image_bytes": image_size,
        "mapped_intervals": len(intervals),
        "window_radius": WINDOW_RADIUS,
        "counts": {label: len(rows) for label, rows in grouped.items()},
        "hits_private": hits,
        "caveat": "Structural proximity alone cannot establish the origin of every physical copy.",
    }


def crosscheck_memprocfs(result: dict, known_path: Path, observation_path: Path,
                        image_path: Path, sdk_root: Path, pid: int):
    """Independently validate each reported VA, physical translation, and value."""
    sdk = sdk_root.resolve(strict=True)
    sys.path.insert(0, str(sdk))
    dll = os.add_dll_directory(str(sdk)) if os.name == "nt" else None
    import memprocfs
    vmm = memprocfs.Vmm(["-device", str(image_path.resolve(strict=True))])
    try:
        process = vmm.process(pid)
        known = read_json(known_path)
        text_tail = read_json(observation_path)["page"]["textTail"]
        escaped_observation = json.dumps(text_tail, ensure_ascii=False)[1:-1].encode("utf-8")
        checks = []
        for hit in result["hits_private"]:
            needle = known[hit["label"]].encode("utf-8")
            address = hit["virtual_private"]
            try:
                actual = process.memory.read(
                    address, len(needle), memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING)
                physical = process.memory.virt2phys(address)
                escaped_offsets = hit["offsets"]["full_json_escaped_observation"]
                escaped_match = False
                if escaped_offsets:
                    escaped_address = address + escaped_offsets[0]
                    escaped_actual = process.memory.read(
                        escaped_address, len(escaped_observation),
                        memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING)
                    escaped_match = escaped_actual == escaped_observation
                checks.append({"virtual_private": address,
                               "physical_private": hit["physical_private"],
                               "actual_sha256": hashlib.sha256(actual).hexdigest(),
                               "expected_sha256": hashlib.sha256(needle).hexdigest(),
                               "bytes_match": actual == needle,
                               "translation_match": physical == hit["physical_private"],
                               "full_observation_match": escaped_match})
            except Exception as error:
                checks.append({"virtual_private": address,
                               "error": type(error).__name__})
        result["memprocfs_crosscheck"] = {
            "pid": pid,
            "checks_private": checks,
            "all_match": bool(checks) and all(
                check.get("bytes_match") and check.get("translation_match") and
                check.get("full_observation_match") for check in checks),
        }
    finally:
        del vmm
        if dll:
            dll.close()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, required=True)
    cli.add_argument("--known", type=Path, required=True)
    cli.add_argument("--observation", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--sdk-root", type=Path)
    cli.add_argument("--pid", type=int)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if (args.sdk_root is None) != (args.pid is None):
        cli.error("--sdk-root and --pid must be supplied together")
    result = analyze(args.image, args.memmap, args.known, args.observation)
    if args.sdk_root is not None:
        crosscheck_memprocfs(result, args.known, args.observation, args.image,
                            args.sdk_root, args.pid)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": result["counts"],
                      "memprocfs_all_match": result.get("memprocfs_crosscheck", {}).get("all_match"),
                      "output_private": str(args.output)}))


if __name__ == "__main__":
    main()
