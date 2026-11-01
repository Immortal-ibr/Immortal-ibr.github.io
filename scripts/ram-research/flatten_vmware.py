"""Convert a matched VMEM/VMSN pair to flat guest-physical bytes.

Uses the installed Volatility VMware layer to read the memory-region metadata.
This is format conversion, not artifact recovery. Keep the input pair and the
conversion manifest: VMEM file offsets are not necessarily guest-physical offsets.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

BLOCK_SIZE = 8 * 1024 * 1024


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(BLOCK_SIZE):
            digest.update(block)
    return digest.hexdigest()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--vmem", required=True, type=Path)
    cli.add_argument("--metadata", required=True, type=Path)
    cli.add_argument("--volatility-root", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--manifest", required=True, type=Path)
    args = cli.parse_args()
    vmem = args.vmem.resolve(strict=True)
    metadata = args.metadata.resolve(strict=True)
    output = args.output.resolve()
    manifest = args.manifest.resolve()
    if output.exists() or manifest.exists():
        raise SystemExit("Refusing to overwrite a conversion output or manifest")
    if len({vmem, metadata, output, manifest}) != 4:
        raise SystemExit("Source and destination paths must differ")
    sys.path.insert(0, str(args.volatility_root.resolve(strict=True)))
    from volatility3.framework import contexts
    from volatility3.framework.layers.physical import FileLayer
    from volatility3.framework.layers.vmware import VmwareLayer

    context = contexts.Context()
    context.config["conversion.vmem.location"] = vmem.as_uri()
    context.config["conversion.meta.location"] = metadata.as_uri()
    context.layers.add_layer(FileLayer(context, "conversion.vmem", "VmwareBase"))
    context.layers.add_layer(FileLayer(context, "conversion.meta", "VmwareMeta"))
    context.config["conversion.vmware.base_layer"] = "VmwareBase"
    context.config["conversion.vmware.meta_layer"] = "VmwareMeta"
    layer = VmwareLayer(context, "conversion.vmware", "GuestPhysical")
    context.layers.add_layer(layer)
    mappings = list(layer.mapping(0, layer.maximum_address + 1, ignore_errors=True))
    segments = []
    source_size = vmem.stat().st_size
    for guest_offset, guest_size, file_offset, file_size, backing in mappings:
        if backing != "VmwareBase" or guest_size != file_size or file_offset + file_size > source_size:
            raise SystemExit("Unexpected VMware mapping; refusing an approximate conversion")
        segments.append({"guest_physical": guest_offset, "vmem_offset": file_offset, "size": file_size})
    segments.sort(key=lambda value: value["guest_physical"])
    for previous, current in zip(segments, segments[1:]):
        if previous["guest_physical"] + previous["size"] > current["guest_physical"]:
            raise SystemExit("Overlapping guest-physical regions")
    with vmem.open("rb") as source, output.open("xb") as target:
        for segment in segments:
            source.seek(segment["vmem_offset"])
            target.seek(segment["guest_physical"])
            remaining = segment["size"]
            while remaining:
                block = source.read(min(BLOCK_SIZE, remaining))
                if not block:
                    raise SystemExit("Short source read; incomplete conversion retained")
                target.write(block)
                remaining -= len(block)
        target.truncate(layer.maximum_address + 1)
    result = {
        "conversion_method": "Volatility VmwareLayer region mappings; gaps zero-filled, not guessed",
        "source_vmem_sha256": file_hash(vmem),
        "source_metadata_sha256": file_hash(metadata),
        "source_vmem_bytes": source_size,
        "raw_logical_bytes": output.stat().st_size,
        "raw_sha256": file_hash(output),
        "regions": segments,
        "compatibility_verified": False,
        "required_next_check": "Compare windows.info DTB, kernel base, architecture and SystemTime on both representations",
    }
    with manifest.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
