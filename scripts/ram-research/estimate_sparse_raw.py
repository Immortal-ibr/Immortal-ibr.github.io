"""Estimate worst-case NTFS allocation of a gzip image at fixed block size.

Only an all-zero block would be skipped by the corresponding sparse inflator;
this estimate is deliberately conservative and does not write an image.
"""

import argparse
import gzip
import json
from pathlib import Path


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--archive", type=Path, required=True)
    cli.add_argument("--block-mib", type=int, default=1)
    args = cli.parse_args()
    size = args.block_mib * 1024 * 1024
    if size <= 0:
        raise ValueError("Block size must be positive")
    logical = allocated_upper = zero_blocks = nonzero_blocks = 0
    with gzip.open(args.archive, "rb") as source:
        while block := source.read(size):
            logical += len(block)
            if block.count(0) == len(block):
                zero_blocks += 1
            else:
                nonzero_blocks += 1
                allocated_upper += len(block)
    print(json.dumps({"logical_bytes": logical, "nonzero_block_bytes_upper_bound": allocated_upper,
                      "zero_blocks": zero_blocks, "nonzero_blocks": nonzero_blocks,
                      "block_bytes": size}))


if __name__ == "__main__":
    main()
