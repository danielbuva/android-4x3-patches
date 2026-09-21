"""Synthetic ELF fixtures; no game binaries or assets."""
import hashlib
import struct
from pathlib import Path

import pytest
from android4x3.errors import PatchError
from android4x3.registry import Registry


@pytest.fixture
def module():
    r = Registry(Path(__file__).resolve().parents[1] / 'games')
    return r.module(r.by_id['hyper-light-drifter'])


def elf():
    b = bytearray(512)
    b[:7] = b'\x7fELF\x02\x01\x01'
    struct.pack_into('<H', b, 18, 183)
    struct.pack_into('<Q', b, 32, 64)
    struct.pack_into('<HH', b, 54, 56, 2)
    struct.pack_into('<IIQQQQQQ', b, 64, 1, 5, 0, 0, 0, 512, 1024, 4096)
    struct.pack_into('<IIQQQQQQ', b, 120, 4, 4, 256, 256, 256, 16, 16, 4)
    b[256:272] = bytes(range(16))
    return b


def test_payload_preserves_load_and_original_bytes(module):
    data = elf()
    original = bytes(data)
    module.append_payload(data)
    assert data[:120] == original[:120]
    assert data[176:512] == original[176:]
    header = struct.unpack_from('<IIQQQQQQ', data, 120)
    assert header[:5] == (1, 5, 65536, module.PAYLOAD_ADDRESS, module.PAYLOAD_ADDRESS)
    assert header[5] == header[6] == len(data) - 65536
    assert header[7] == 65536
    assert not header[1] & 2  # Executable payload is never writable.
    assert hashlib.sha256(data[65536:]).hexdigest() == module.FINGERPRINTS['payload_sha256']
    assert data[512:65536] == bytes(65536-512)


@pytest.mark.parametrize('damage', ['architecture', 'headers', 'missing_note', 'overlap'])
def test_unsafe_elf_rejected(module, damage):
    data = elf()
    if damage == 'architecture':
        struct.pack_into('<H', data, 18, 40)
    elif damage == 'headers':
        struct.pack_into('<H', data, 54, 32)
    elif damage == 'missing_note':
        struct.pack_into('<I', data, 120, 0)
    else:
        struct.pack_into('<Q', data, 64+40, module.PAYLOAD_ADDRESS+1)
    with pytest.raises(PatchError):
        module.append_payload(data)


def test_corrupt_payload_rejected(module, monkeypatch, tmp_path):
    (tmp_path/'native').mkdir()
    (tmp_path/'native/payload.hex').write_text('00000000')
    monkeypatch.setattr(module, 'DIRECTORY', tmp_path)
    with pytest.raises(PatchError, match='damaged patch payload'):
        module.append_payload(elf())


def test_branch_encoding_and_bounds(module):
    data = bytearray(struct.pack('<I', 123))
    module.branch(data, 0, 123, 16)
    assert struct.unpack('<I', data)[0] == 0x94000004
    for target in (3, 1 << 27, -(1 << 27)-4):
        with pytest.raises(PatchError, match='out of range'):
            module.branch(bytearray(4), 0, 0, target)
    with pytest.raises(PatchError, match='instruction mismatch'):
        module.branch(bytearray(4), 0, 123, 16)


def test_unknown_inputs_fail_before_mutation(module):
    for transform in (module.patch_native, module.patch_game):
        with pytest.raises(PatchError, match='unsupported'):
            transform(bytes(512))
    assert module.probe({})['state'] == 'unsupported'


def test_idempotency_and_mixed_revisions(module, monkeypatch, tmp_path):
    native, game = b'synthetic patched native', b'synthetic patched data'
    fp = dict(module.FINGERPRINTS, native_4x3=module.digest(native), game_4x3=module.digest(game))
    monkeypatch.setattr(module, 'FINGERPRINTS', fp)
    assert module.patch_native(native) == native
    assert module.patch_game(game) == game
    with pytest.raises(PatchError, match='Original-aspect'):
        module.patch_native(native, original_aspect=True)
    paths = {}
    for entry, data in ((module.LIBRARY, native), (module.GAME, game)):
        path = tmp_path/entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        paths[entry] = path
    assert module.probe(paths)['state'] == 'patched'
    assert module.apply(paths, tmp_path/'output') == {}
    fp['game_original'], fp['game_4x3'] = fp['game_4x3'], 'unknown'
    assert module.probe(paths)['state'] == 'unsupported'
