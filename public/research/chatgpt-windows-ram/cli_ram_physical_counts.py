"""Count exact synthetic CLI values across full physical RAM after capture.

This comparison has no process attribution and is separate from the frozen
browser method and the mapped CLI-process scan.
"""

import argparse
import json
from pathlib import Path


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--trial", type=Path, required=True)
    args = cli.parse_args()
    trial = args.trial.resolve()
    truth = json.loads((trial / "ground_truth.json").read_text(encoding="utf-8-sig"))
    image = trial / "private" / "memory.raw"
    values = {"prompt": truth["prompt"], "response": truth["actual_response"],
              "marker": truth["marker"]}
    needles = {f"{name}_{enc}": value.encode("utf-8" if enc == "utf8" else "utf-16le")
               for name, value in values.items() for enc in ("utf8", "utf16le")}
    counts = dict.fromkeys(needles, 0)
    overlap = max(len(needle) for needle in needles.values()) - 1
    tail = b""
    scanned = 0
    with image.open("rb") as source:
        while chunk := source.read(64 * 1024 * 1024):
            data = tail + chunk
            safe_end = max(0, len(data) - overlap)
            for name, needle in needles.items():
                pos = 0
                while (pos := data.find(needle, pos)) >= 0:
                    if pos >= safe_end:
                        break
                    counts[name] += 1
                    pos += 1
            tail = data[safe_end:]
            scanned += len(chunk)
    for name, needle in needles.items():
        pos = 0
        while (pos := tail.find(needle, pos)) >= 0:
            counts[name] += 1
            pos += 1
    out = {"trial_id": truth["trial_id"],
           "method": "post-capture ground-truth-assisted exact-value counts across physical RAM",
           "ground_truth_supplied": True,
           "scanned_bytes": scanned,
           "counts": counts,
           "limitations": "No process provenance or linked-turn reconstruction; investigator PTY, local files, and the captured TUI may contribute."}
    (trial / "cli_ram_physical_counts.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
