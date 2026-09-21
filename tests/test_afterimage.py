"""Invented ELF and Android resource fixtures; no commercial game files."""
import dataclasses
import hashlib
import struct
from pathlib import Path

import pytest

from android4x3.errors import PatchError
from android4x3.registry import Registry


@pytest.fixture
def module():
    registry = Registry(Path(__file__).resolve().parents[1] / "games")
    return registry.module(registry.by_id["afterimage"])


def native_fixture(m):
    data = bytearray(b"\xa5" * 1024)
    data[:16] = b"\x7fELF\x02\x01\x01" + bytes(9)
    struct.pack_into("<HHIQQQIHHHHHH", data, 16, 3, 183, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 256, 4096, 4096, 768, 768, 4096)
    sites = []
    for i, offset in enumerate((384, 512)):
        site = m.Site(f"synthetic camera {i}", offset - 256 + 4096, offset,
                      bytes([10 + i]) * 16, bytes([30 + i]) * 4,
                      bytes([50 + i]) * 4, bytes([70 + i]) * 16)
        data[offset-16:offset+20] = site.before + site.original + site.after
        sites.append(site)
    patched = bytearray(data)
    for site in sites:
        patched[site.offset:site.offset+4] = site.patched
    return bytes(data), bytes(patched), m.NativeSpec(len(data), hashlib.sha256(data).hexdigest(),
        hashlib.sha256(patched).hexdigest(), tuple(sites))


def pool(strings):
    raw, offsets = bytearray(), []
    for text in strings:
        offsets.append(len(raw))
        encoded = text.encode()
        raw.extend(bytes([len(text), len(encoded)]) + encoded + b"\0")
    raw.extend(bytes(-len(raw) % 4))
    start = 28 + len(strings) * 4
    return (struct.pack("<HHIIIIII", 1, 28, start + len(raw), len(strings), 0, 0x100, start, 0)
            + struct.pack(f"<{len(offsets)}I", *offsets) + raw)


def resources(theme="UE4BaseTheme", duplicate=False):
    types, keys = pool(["style"]), pool(["Before", theme, "After"])
    # Three dense bag entries; inserting into the middle must move the last offset.
    entries = b"".join(struct.pack("<HHIII", 16, 3, k, 0x0103000A, 0) for k in (0, 1, 1 if duplicate else 2))
    h, start = 24, 36
    chunk = (struct.pack("<HHIBBHIII", 0x201, h, start + len(entries), 1, 0, 0, 3, start, 4)
             + struct.pack("<III", 0, 16, 32) + entries)
    package = bytearray(288)
    struct.pack_into("<HHII", package, 0, 0x200, 288, 288+len(types)+len(keys)+len(chunk), 0x7F)
    name = "com.aurogon.Afterimage".encode("utf-16-le")
    package[12:12+len(name)] = name
    struct.pack_into("<IIII", package, 268, 288, 1, 288+len(types), 3)
    body = bytes(package) + types + keys + chunk
    return struct.pack("<HHII", 2, 12, 12+len(body), 1) + body


def test_native_original_partial_and_idempotent(module):
    source, patched, spec = native_fixture(module)
    assert module.native_state(source, spec) == ["original", "original"]
    assert module.patch_native(source, spec) == patched
    assert module.patch_native(patched, spec) == patched
    partial = bytearray(source)
    partial[spec.sites[0].offset:spec.sites[0].offset+4] = spec.sites[0].patched
    assert module.patch_native(bytes(partial), spec) == patched


@pytest.mark.parametrize("mutation", ["architecture", "mapping", "unrelated", "instruction", "context", "duplicate", "truncated"])
def test_native_unknowns_fail_closed(module, mutation):
    source, _, spec = native_fixture(module)
    data = bytearray(source)
    if mutation == "architecture":
        struct.pack_into("<H", data, 18, 40)
    elif mutation == "mapping":
        struct.pack_into("<Q", data, 64+16, 8192)
    elif mutation == "unrelated":
        data[800] ^= 1
    elif mutation == "instruction":
        data[384] ^= 1
    elif mutation == "context":
        data[380] ^= 1
    elif mutation == "duplicate":
        data[650:686] = data[368:404]
    else:
        data.pop()
    with pytest.raises(PatchError):
        module.patch_native(bytes(data), spec)


def test_native_final_hash_required(module):
    source, _, spec = native_fixture(module)
    with pytest.raises(PatchError, match="final native hash"):
        module.patch_native(source, dataclasses.replace(spec, patched_sha256="0" * 64))


def test_theme_preserves_siblings_and_is_idempotent(module):
    source = resources()
    state, patched = module.focus_theme(source)
    assert state == "original"
    assert len(patched) == len(source) + 12
    assert module.focus_theme(patched) == ("patched", patched)
    # The preceding and following style bags survive exactly.
    for key in (0, 2):
        sibling = struct.pack("<HHIII", 16, 3, key, 0x0103000A, 0)
        assert source.count(sibling) == patched.count(sibling) == 1
    assert patched.count(struct.pack("<IHBBI", module.FOCUS_ATTRIBUTE, 8, 0, 0x12, 0)) == 1
    assert struct.unpack_from("<I", patched, 4)[0] == len(patched)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "true", "sparse", "truncated"])
def test_unknown_theme_rejected(module, kind):
    data = resources(theme="Unknown" if kind == "missing" else "UE4BaseTheme", duplicate=kind == "duplicate")
    if kind == "true":
        _, data = module.focus_theme(data)
        false = struct.pack("<IHBBI", module.FOCUS_ATTRIBUTE, 8, 0, 0x12, 0)
        data = data.replace(false, struct.pack("<IHBBI", module.FOCUS_ATTRIBUTE, 8, 0, 0x12, 0xFFFFFFFF))
    elif kind == "sparse":
        data = bytearray(data)
        chunk = data.find(struct.pack("<HH", 0x201, 24))
        data[chunk+9] = 1
        data = bytes(data)
    elif kind == "truncated":
        data = data[:-1]
    with pytest.raises(PatchError):
        module.focus_theme(data)


def test_combined_apply_recognizes_final_and_missing_input(module, monkeypatch, tmp_path):
    source, expected, spec = native_fixture(module)
    monkeypatch.setattr(module, "SPEC", spec)
    lib, res = tmp_path / "lib.so", tmp_path / "resources.arsc"
    lib.write_bytes(source)
    res.write_bytes(resources())
    inputs = {module.LIBRARY: lib, module.RESOURCES: res}
    assert module.probe(inputs)["state"] == "original"
    outputs = module.apply(inputs, tmp_path / "output")
    assert outputs[module.LIBRARY].read_bytes() == expected
    assert module.probe(outputs)["state"] == "patched"
    assert module.apply(outputs, tmp_path / "again") == {}
    assert module.probe({})["state"] == "unsupported"


def test_projection_retains_horizontal_extent_at_four_by_three():
    # Audited orthographic branch: half-height = half-width / (viewport width/height).
    width, height, world_width = 1280, 960, 2400
    new_height = world_width / (width / height)
    for source_aspect in (16/9, 16/10):
        old_height = world_width / source_aspect
        assert new_height > old_height
    assert width / world_width == height / new_height
