"""Compare bounded records at the same process virtual addresses in a later RAM image.

This is a post-hoc persistence check, not a blind record search. The earlier
parser output supplies the virtual addresses and exact record hashes. No record
text is written to the summary, but the output is kept private because it
contains source addresses and image-specific process details.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from bounded_json import MappedReader, normalize_rows


REPOSITORY = Path(__file__).resolve().parents[2]


def compare(reference, reader, process=None, flags=0):
    observations = []
    for record in reference["records"]:
        expected = record["record_sha256"].lower()
        length = int(record["raw_byte_length"])
        for occurrence_index, address in enumerate(record["source_virtual_addresses"]):
            virtual = int(address)
            data, spans = reader.read(virtual, length)
            actual = hashlib.sha256(data).hexdigest() if len(data) == length else None
            reference_spans = record["source_spans"][occurrence_index]
            observation = {
                "virtual_address": virtual,
                "record_length": length,
                "mapped_length": len(data),
                "record_hash_matches": actual == expected if actual else False,
                "complete_bytes_begin_sse_data": data.startswith(b"data:") if actual else False,
                "same_physical_spans": spans == reference_spans,
                "all_mapped_bytes_zero": bool(data) and not any(data),
                "zero_byte_count": data.count(0),
                "later_physical_spans": spans,
            }
            if process is not None:
                try:
                    independent = process.memory.read(virtual, len(data), flags)
                    observation["memprocfs_bytes_match"] = independent == data
                    observation["memprocfs_translations_match"] = all(
                        process.memory.virt2phys(span["virtual"]) == span["physical"]
                        for span in spans
                    )
                except Exception as error:
                    observation["memprocfs_error"] = type(error).__name__
            observations.append(observation)
    return observations


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--reference", required=True, type=Path)
    cli.add_argument("--later-image", required=True, type=Path)
    cli.add_argument("--later-memmap", required=True, type=Path)
    cli.add_argument("--sdk-root", type=Path)
    cli.add_argument("--pid", type=int)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(REPOSITORY):
        raise ValueError("Post-hoc address output must stay outside the repository")
    if output.exists():
        raise FileExistsError(output)
    reference = json.loads(args.reference.read_text(encoding="utf-8-sig"))
    mappings = json.loads(args.later_memmap.read_text(encoding="utf-8-sig"))
    rows, skipped = normalize_rows(mappings, args.later_image.stat().st_size)
    if bool(args.sdk_root) != bool(args.pid):
        raise ValueError("--sdk-root and --pid must be supplied together")
    vmm = None
    dll_scope = None
    process = None
    flags = 0
    if args.sdk_root:
        sdk = args.sdk_root.resolve(strict=True)
        sys.path.insert(0, str(sdk))
        if os.name == "nt":
            dll_scope = os.add_dll_directory(str(sdk))
        import memprocfs

        vmm = memprocfs.Vmm(["-device", str(args.later_image.resolve(strict=True))])
        process = vmm.process(args.pid)
        flags = memprocfs.FLAG_NOCACHE | memprocfs.FLAG_NOPAGING
    with args.later_image.open("rb") as source:
        observations = compare(reference, MappedReader(source, rows), process, flags)
    result = {
        "scope": "same PID and virtual addresses only; post-hoc, not blind recovery",
        "reference_record_count": len(reference["records"]),
        "later_resident_user_rows": len(rows),
        "later_skipped_kernel_rows": skipped,
        "exact_address_observations": observations,
        "counts": {
            "unmapped": sum(o["mapped_length"] == 0 for o in observations),
            "partially_mapped": sum(0 < o["mapped_length"] < o["record_length"] for o in observations),
            "complete_same_hash": sum(o["record_hash_matches"] for o in observations),
            "complete_changed_hash": sum(
                o["mapped_length"] == o["record_length"] and not o["record_hash_matches"]
                for o in observations
            ),
            "same_physical_spans": sum(o["same_physical_spans"] for o in observations),
            "all_mapped_bytes_zero": sum(o["all_mapped_bytes_zero"] for o in observations),
            "memprocfs_bytes_match": sum(o.get("memprocfs_bytes_match", False) for o in observations),
            "memprocfs_translations_match": sum(
                o.get("memprocfs_translations_match", False) for o in observations
            ),
        },
    }
    with output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, indent=2)
        destination.write("\n")
    print(json.dumps(result["counts"]))
    del process
    del vmm
    if dll_scope is not None:
        dll_scope.close()


if __name__ == "__main__":
    main()
