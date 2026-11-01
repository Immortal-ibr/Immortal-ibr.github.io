"""Post-capture residue audit. Known values are inputs, so output is not a turn recovery.

Example:
  python3 reverse_known_value_audit.py --image memory.raw --values known.json --map chrome-parent=parent-memmap.json --observer-file page-observation.json --output residue.json

The values file is a JSON object of label-to-string pairs. Only selected, already
known synthetic values should be supplied. Observer files are investigator-created
logs whose exact byte context can be compared with hits in RAM.
"""

import argparse
import hashlib
import json
import mmap
from pathlib import Path


def find_all(image, needle):
    result = []
    offset = 0
    while True:
        offset = image.find(needle, offset)
        if offset < 0:
            return result
        result.append(offset)
        offset += 1


def load_map(spec):
    label, separator, filename = spec.partition('=')
    if not separator or not label or not filename:
        raise ValueError('Each --map must be LABEL=PATH')
    rows = json.loads(Path(filename).read_text(encoding='utf-8'))
    ranges = []
    for row in rows:
        virtual = int(row['Virtual'])
        physical = int(row['Physical'])
        size = int(row['Size'])
        if 0 <= virtual < (1 << 47) and physical > 0 and size > 0:
            ranges.append((physical, physical + size, virtual))
    return label, ranges


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--image', type=Path, required=True)
    cli.add_argument('--values', type=Path, required=True)
    cli.add_argument('--field', action='append', default=[], help='Select one string field from a larger values JSON')
    cli.add_argument('--map', action='append', default=[])
    cli.add_argument('--observer-file', action='append', type=Path, default=[])
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--expected-sha256')
    args = cli.parse_args()

    values = json.loads(args.values.read_text(encoding='utf-8'))
    if args.field:
        values = {name: values[name] for name in args.field}
    if not isinstance(values, dict) or not values or not all(isinstance(v, str) and v for v in values.values()):
        raise ValueError('Values must be a nonempty JSON object of label-to-string pairs')
    maps = dict(load_map(spec) for spec in args.map)
    observers = {path.name: path.read_bytes() for path in args.observer_file}

    if args.expected_sha256:
        digest = hashlib.sha256()
        with args.image.open('rb') as source:
            for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
                digest.update(block)
        if digest.hexdigest().lower() != args.expected_sha256.lower():
            raise ValueError('Image SHA-256 mismatch')

    result = {'method': 'post-capture known-value residue audit, not blind turn recovery',
              'image_bytes': args.image.stat().st_size, 'values': {}}
    with args.image.open('rb') as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as image:
        for label, value in values.items():
            result['values'][label] = {}
            for encoding in ('utf-8', 'utf-16-le'):
                needle = value.encode(encoding)
                offsets = find_all(image, needle)
                hits = []
                for offset in offsets:
                    owners = []
                    for map_label, ranges in maps.items():
                        for start, end, virtual in ranges:
                            if start <= offset and offset + len(needle) <= end:
                                owners.append({'map': map_label, 'virtual': hex(virtual + offset - start)})
                    before = max(0, offset - 64)
                    after = min(len(image), offset + len(needle) + 64)
                    context = image[before:after]
                    observer_matches = [name for name, data in observers.items() if context in data]
                    hits.append({'physical': hex(offset), 'mapped_owners': owners,
                                 'exact_observer_context_matches': observer_matches})
                result['values'][label][encoding] = {
                    'value_sha256': hashlib.sha256(needle).hexdigest(),
                    'byte_length': len(needle), 'physical_count': len(offsets), 'hits': hits}
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
