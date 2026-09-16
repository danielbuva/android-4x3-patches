"""Maintainer tool: derive source-dependent deltas from two local archives.

No archive or standalone texture is copied into the bundle. Applying each XOR
payload requires the matching original arena; hashes verify both endpoints.
"""
import argparse
import json
from pathlib import Path
import zlib

from backgrounds import ARTWORK_PATHS, entries, unpack_refpack, sha256, patch_archive


def members(archive):
    result = {}
    for name,_,_,offset,compressed,size in entries(archive):
        data = archive[offset:offset+(compressed or size)]
        result[name] = unpack_refpack(data,size) if compressed else data
    return result


def generate(original, modified, output):
    before, after = members(original), members(modified)
    if before.keys() != after.keys():
        raise ValueError('Archive member sets differ')
    changed = {name for name in before if before[name] != after[name]}
    if changed != set(ARTWORK_PATHS):
        raise ValueError('Only the four named background arenas may change')
    payloads, targets = {}, {}
    for name in ARTWORK_PATHS:
        a,b = before[name],after[name]
        if len(a) != len(b):
            raise ValueError('Texture arena size changed')
        delta = zlib.compress(bytes(x^y for x,y in zip(a,b)),9)
        digest = sha256(delta)
        payloads[digest+'.xor.zlib'] = delta
        targets[name] = {'size':len(a), 'before_sha256':sha256(a),
                         'after_sha256':sha256(b), 'delta_sha256':digest}
    # Refuse to replace a bundle accidentally; review generated files in Git.
    output.mkdir()
    for name,data in payloads.items():
        (output/name).write_bytes(data)
    (output/'manifest.json').write_text(json.dumps({
        'format':'xor-zlib-v1',
        'description':'Tested 4:3 title outpaint and startup-menu background; source archive required.',
        'targets':targets,
    },indent=2)+'\n')
    if members(patch_archive(original, output)) != after:
        raise ValueError('Generated artwork bundle failed reconstruction')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',type=Path,required=True)
    parser.add_argument('--modified',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    generate(args.original.read_bytes(),args.modified.read_bytes(),args.output)
    print(f'Verified artwork deltas: {args.output}')


if __name__ == '__main__':
    main()
