"""Opt-in ARM64 camera experiment, deliberately outside the game registry."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from android4x3.apk import inspect_apk, repack_with_optional_branding, verify_zip
from android4x3.errors import PatchError
from android4x3.signing import align_apk, sign_apk

ENTRY = 'lib/arm64-v8a/libil2cpp.so'
METADATA = 'assets/bin/Data/Managed/Metadata/global-metadata.dat'
SOURCE = '240589d66bc746c4b58c66b227b54fc96990338bb774e59fe6502bcb0ccef420'
PATCHED = '9fdfa1c84874198c0faa8b3d56b1d0a48c30231372080888ebe3704372f15581'
META_HASH = '32cf8e85a7a81c3ef57eeec063d6db5a68c82f34c1c79de849817e09c31cc7f2'
PAYLOAD_HASH = 'a838e9030ca9ed298a35a1daa30afc7fe63dea167a726b3cc5b90864bd6003cc'
HOOK = 0xa0fc44
VADDR = 0x2740000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def payload():
    data = bytes.fromhex(Path(__file__).with_name('payload.hex').read_text())
    if digest(data) != PAYLOAD_HASH:
        raise PatchError('Probe payload differs from the reviewed build')
    return data


def inject(data):
    checksum = digest(data)
    if checksum == PATCHED:
        return data
    if checksum != SOURCE:
        raise PatchError('Unsupported ARM64 libil2cpp.so; no changes made')
    if data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise PatchError('Expected little-endian ARM64 ELF')
    if data[HOOK:HOOK+4] != bytes.fromhex('01000014'):
        raise PatchError('Unexpected AbstractCupheadCamera.LateUpdate branch')
    phoff = struct.unpack_from('<Q', data, 32)[0]
    entsize, count = struct.unpack_from('<HH', data, 54)
    if entsize != 56 or count != 6:
        raise PatchError('Unexpected program-header layout')
    headers = [struct.unpack_from('<IIQQQQQQ', data, phoff+i*entsize) for i in range(count)]
    notes = [i for i,h in enumerate(headers) if h[0] == 4]
    if len(notes) != 1 or VADDR < max(h[3]+h[6] for h in headers if h[0] == 1):
        raise PatchError('No safe independent payload segment')
    code = payload()
    offset = (len(data)+0xffff) & ~0xffff
    result = bytearray(data)
    # Replace the optional note header; retain every existing load segment/address.
    struct.pack_into('<IIQQQQQQ', result, phoff+notes[0]*entsize,
                     1, 5, offset, VADDR, VADDR, len(code), len(code), 0x10000)
    delta = VADDR-HOOK
    if delta % 4 or not -(1<<27) <= delta < (1<<27):
        raise PatchError('Hook branch is out of range')
    struct.pack_into('<I', result, HOOK, 0x14000000 | ((delta//4) & 0x3ffffff))
    result.extend(bytes(offset-len(result)))
    result.extend(code)
    if digest(result) != PATCHED:
        raise PatchError('Unexpected patched library checksum')
    return bytes(result)


def inspect(source):
    info = inspect_apk(source)
    if info.package != 'com.gabedeveloper.cuphead':
        raise PatchError('Expected com.gabedeveloper.cuphead')
    with zipfile.ZipFile(source) as archive:
        try:
            if digest(archive.read(METADATA)) != META_HASH:
                raise PatchError('Unsupported IL2CPP metadata')
            original = archive.read(ENTRY)
        except KeyError as exc:
            raise PatchError('Required ARM64 game entries are missing') from exc
    result = inject(original)
    return result, digest(original) == PATCHED


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if not args.check and args.output is None:
            raise PatchError('Use --check or supply --output for the experimental APK')
        if args.output and (args.output.exists() or args.output.resolve() == args.apk.resolve()):
            raise PatchError('Output must be a new file, separate from the source')
        result, already = inspect(args.apk)
        print('Compatible ARM64 camera probe' + (' (already applied)' if already else ''))
        if args.check:
            return 0
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='cuphead-camera-') as folder:
            work = Path(folder)
            library = work/'libil2cpp.so'
            library.write_bytes(result)
            unsigned, aligned, signed = (work/name for name in ('unsigned.apk','aligned.apk','signed.apk'))
            repack_with_optional_branding(ROOT, args.apk, unsigned, {ENTRY: library})
            align_apk(unsigned, aligned)
            sign_apk(aligned, signed)
            verify_zip(signed, full=True, allow_signatures=True)
            # Exclusive creation avoids overwriting an output created during the build.
            import shutil
            with signed.open('rb') as src, args.output.open('xb') as dst:
                shutil.copyfileobj(src, dst, 1024*1024)
        print('Experimental gameplay APK written. ARMv7 is unchanged; UI is unfinished.')
        return 0
    except (PatchError, OSError, zipfile.BadZipFile, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
