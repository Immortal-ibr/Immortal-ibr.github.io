"""Post-hoc ground-truth diagnostic for a browser RAM capture.

This is deliberately not a reconstruction method: it receives known values,
counts exact UTF-8/UTF-16LE hits, and saves bounded byte neighborhoods in a
private file so a new client format can be investigated. Do not publish its
raw output without reviewing it for unrelated memory content.
"""

import argparse
import json
from pathlib import Path


USER_LIMIT = 1 << 47


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--image", type=Path, required=True)
    cli.add_argument("--memmap", type=Path, action="append", required=True)
    cli.add_argument("--needle", nargs=2, action="append", metavar=("NAME", "TEXT"), required=True)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--context-bytes", type=int, default=256)
    cli.add_argument("--max-contexts", type=int, default=16)
    args = cli.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if not (0 <= args.context_bytes <= 4096 and 0 <= args.max_contexts <= 100):
        raise ValueError("Context limits are out of range")
    needles = {
        f"{name}/{encoding}": text.encode(encoding)
        for name, text in args.needle
        for encoding in ("utf-8", "utf-16-le")
    }
    image_size = args.image.stat().st_size
    output = {
        "method": "post-hoc ground-truth-assisted exact byte diagnostic; not blind reconstruction",
        "image": str(args.image),
        "needles": {name: len(value) for name, value in needles.items()},
        "processes": [],
    }
    with args.image.open("rb", buffering=0) as source:
        for mapfile in args.memmap:
            rows = json.loads(mapfile.read_text(encoding="utf-8-sig"))
            counts = {name: 0 for name in needles}
            addresses = {name: [] for name in needles}
            contexts = {name: [] for name in needles}
            scanned_rows = 0
            for row in rows:
                physical, virtual, amount = (int(row[key]) for key in ("Physical", "Virtual", "Size"))
                if virtual >= USER_LIMIT or amount <= 0 or physical < 0 or physical + amount > image_size:
                    continue
                scanned_rows += 1
                source.seek(physical)
                data = source.read(amount)
                for name, needle in needles.items():
                    cursor = 0
                    while (index := data.find(needle, cursor)) != -1:
                        counts[name] += 1
                        if len(addresses[name]) < 100:
                            addresses[name].append({"virtual": virtual + index, "physical": physical + index})
                        if len(contexts[name]) < args.max_contexts:
                            start = max(0, index - args.context_bytes)
                            end = min(len(data), index + len(needle) + args.context_bytes)
                            contexts[name].append({
                                "virtual": virtual + index,
                                "physical": physical + index,
                                "before_hex": data[start:index].hex(),
                                "after_hex": data[index + len(needle):end].hex(),
                            })
                        cursor = index + 1
            output["processes"].append({
                "memmap": str(mapfile),
                "user_space_rows_scanned": scanned_rows,
                "hit_counts": counts,
                "first_addresses": addresses,
                "private_contexts": contexts,
            })
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    for process in output["processes"]:
        print(Path(process["memmap"]).name, process["hit_counts"])


if __name__ == "__main__":
    main()
