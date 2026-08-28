"""Proprietary-free tests for Children of Morta's guarded patch module."""

from __future__ import annotations

import hashlib
import io
import struct
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _module():
    registry = Registry(REPO_ROOT / "games")
    return registry.module(registry.by_id["children-of-morta"])


def _elf64(module, edits):
    data = bytearray(0x400)
    data[:16] = b"\x7fELF\x02\x01\x01" + b"\0" * 9
    struct.pack_into(
        "<HHIQQQIHHHHHH",
        data,
        16,
        3,
        183,
        1,
        0,
        64,
        0,
        0,
        64,
        56,
        1,
        64,
        0,
        0,
    )
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0, len(data), len(data), 0x1000)
    for edit in edits:
        data[edit.offset : edit.offset + len(edit.original)] = edit.original
    patched = bytearray(data)
    for edit in edits:
        patched[edit.offset : edit.offset + len(edit.patched)] = edit.patched
    spec = module.NativeSpec(
        "synthetic/libil2cpp.so",
        183,
        len(data),
        hashlib.sha256(data).hexdigest(),
        hashlib.sha256(patched).hexdigest(),
        edits,
    )
    return bytes(data), bytes(patched), spec


def test_morta_production_metadata_is_proprietary_free_and_guarded() -> None:
    morta = _module()

    assert morta.REQUIRED_ENTRIES == (
        morta.IL2CPP_ENTRY,
        morta.SPLASH_ENTRY,
        morta.CORE_ENTRY,
        morta.HOME_ENTRY,
        morta.RUN_SHARED_ENTRY,
        morta.DATAPACK_ENTRY,
    )
    assert not hasattr(morta, "DEX_ENTRY")
    assert all("provider" not in edit.name.lower() for edit in morta._NATIVE.edits)
    assert morta._NATIVE.size == 61_356_112
    assert len(morta._NATIVE.edits) == 4
    assert sum(mapping.count for mapping in morta._CANVAS_RULES[0].mappings) == 174
    assert morta._CANVAS_RULES[0].neutral == (((800.0, 600.0), 2),)
    for edit in morta._NATIVE.edits:
        assert len(edit.original) == len(edit.patched)
        assert edit.original != edit.patched


def test_morta_synthetic_native_probe_apply_partial_and_postcondition() -> None:
    morta = _module()
    edits = (
        morta.NativeEdit("invented branch", 0x180, 0x180, b"OLD1", b"NEW1"),
        morta.NativeEdit("invented float", 0x1A0, 0x1A0, b"OLD2", b"NEW2", False),
    )
    original, patched, spec = _elf64(morta, edits)

    assert morta._native_probe_data(original, spec)["state"] == "original"
    assert morta._patch_native_data(original, spec) == patched
    assert morta._native_probe_data(patched, spec)["state"] == "patched"

    partial = bytearray(original)
    partial[edits[0].offset : edits[0].offset + 4] = edits[0].patched
    assert morta._native_probe_data(partial, spec)["state"] == "original"
    assert morta._patch_native_data(bytes(partial), spec) == patched

    unrelated = bytearray(original)
    unrelated[-1] = 1
    assert morta._native_probe_data(unrelated, spec)["state"] == "unsupported"


class _FakeObject:
    def __init__(self, path_id, name, raw):
        self.path_id = path_id
        self.type = SimpleNamespace(name="MonoBehaviour")
        self._name = name
        self._raw = bytes(raw)

    def get_raw_data(self):
        return self._raw

    def set_raw_data(self, data):
        self._raw = bytes(data)

    def read(self, check_read=False):
        game_object = SimpleNamespace(m_Name=self._name)
        pointer = SimpleNamespace(path_id=self.path_id, read=lambda: game_object)
        return SimpleNamespace(m_GameObject=pointer)


def _canvas_raw(script, pair):
    raw = bytearray(76)
    raw[12] = 1
    struct.pack_into("<iq", raw, 16, *script)
    struct.pack_into("<i", raw, 32, 1)
    struct.pack_into("<ff", raw, 44, *pair)
    return raw


def test_morta_semantic_canvas_probe_mutation_and_postcondition(tmp_path, monkeypatch) -> None:
    morta = _module()
    script = (0, 12345)
    rule = morta.CanvasRule(
        "assets/invented.bundle",
        script,
        (morta.CanvasMapping((1600.0, 900.0), (1600.0, 1200.0), 2),),
        neutral=(((800.0, 600.0), 1),),
    )
    objects = {
        1: _FakeObject(1, "Menu", _canvas_raw(script, (1600.0, 900.0))),
        2: _FakeObject(2, "HUD", _canvas_raw(script, (1600.0, 900.0))),
        3: _FakeObject(3, "World", _canvas_raw(script, (800.0, 600.0))),
    }
    serialized = SimpleNamespace(objects=objects)

    class Bundle:
        signature = "UnityFS"
        files = {"invented.assets": serialized}

        @staticmethod
        def save(packer="original"):
            assert packer == "original"
            return b"invented UnityFS output"

    monkeypatch.setattr(morta, "_load_bundle", lambda _path: (object(), Bundle()))
    source = tmp_path / "source.bundle"
    source.write_bytes(b"invented")

    report, targets = morta._inspect_bundle(rule, source)
    assert report["state"] == "original"
    output = tmp_path / "patched.bundle"
    morta._patch_bundle(rule, source, output, targets)

    assert morta._inspect_bundle(rule, output)[0]["state"] == "patched"
    assert struct.unpack_from("<ff", objects[1].get_raw_data(), 44) == (1600.0, 1200.0)
    assert struct.unpack_from("<ff", objects[3].get_raw_data(), 44) == (800.0, 600.0)


def _png(size):
    image = Image.new("RGBA", size, (0, 0, 0, 255))
    for x in range(size[0]):
        color = (x % 256, 40, 200, 255)
        for y in range(size[1]):
            image.putpixel((x, y), color)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_morta_splash_cover_crop_is_exact_4x3_without_axis_stretch() -> None:
    morta = _module()
    original = _png((160, 90))
    target_size = (120, 90)
    expected = morta._cover_crop_png(original, target_size)
    spec = morta.PngSpec(
        "invented.png",
        (160, 90),
        target_size,
        hashlib.sha256(original).hexdigest(),
        hashlib.sha256(expected).hexdigest(),
    )

    patched = morta._patch_png_data(original, spec)

    assert morta._png_probe_data(original, spec)["state"] == "original"
    assert morta._png_probe_data(patched, spec)["state"] == "patched"
    with Image.open(io.BytesIO(patched)) as image:
        assert image.size == (120, 90)
        # A 160x90 source is cropped by 20 pixels on each horizontal side;
        # height and pixel geometry are not stretched.
        assert image.getpixel((0, 45))[0] == 20
        assert image.getpixel((119, 45))[0] == 139
