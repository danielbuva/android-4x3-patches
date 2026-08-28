"""Proprietary-free tests for Death Road to Canada's patch module."""

from __future__ import annotations

import hashlib
import io
import struct
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image

from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _module():
    registry = Registry(REPO_ROOT / "games")
    return registry.module(registry.by_id["death-road-to-canada"])


def _synthetic_elf(module, elf_class, machine):
    data = bytearray(0x300)
    if elf_class == 2:
        data[:16] = b"\x7fELF\x02\x01\x01" + b"\0" * 9
        struct.pack_into(
            "<HHIQQQIHHHHHH",
            data,
            16,
            3,
            machine,
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
    else:
        data[:16] = b"\x7fELF\x01\x01\x01" + b"\0" * 9
        struct.pack_into(
            "<HHIIIIIHHHHHH",
            data,
            16,
            3,
            machine,
            1,
            0,
            52,
            0,
            0,
            52,
            32,
            1,
            40,
            0,
            0,
        )
        struct.pack_into("<IIIIIIII", data, 52, 1, 0, 0, 0, len(data), len(data), 5, 0x1000)
    edit = module.NativeEdit("invented display height", 0x180, 0x180, b"OLD!", b"NEW!")
    data[edit.offset : edit.offset + 4] = edit.original
    patched = bytearray(data)
    patched[edit.offset : edit.offset + 4] = edit.patched
    spec = module.NativeSpec(
        "synthetic",
        f"lib/synthetic-{elf_class}/libmain.so",
        elf_class,
        machine,
        len(data),
        hashlib.sha256(data).hexdigest(),
        hashlib.sha256(patched).hexdigest(),
        (edit,),
    )
    return bytes(data), bytes(patched), spec


def test_death_road_production_targets_cover_both_abis_and_cleanup() -> None:
    drtc = _module()

    assert tuple(spec.abi for spec in drtc._NATIVE_SPECS) == ("arm64-v8a", "armeabi-v7a")
    assert drtc.REQUIRED_ENTRIES == (drtc.DEX_ENTRY, drtc.SPLASH_ENTRY)
    assert len(drtc._DEX_EDITS) == 7
    assert any(edit.method_name == "showMoreGames" for edit in drtc._DEX_EDITS)
    assert any("FlurryContentProvider" in edit.class_descriptor for edit in drtc._DEX_EDITS)


@pytest.mark.parametrize(("elf_class", "machine"), [(2, 183), (1, 40)])
def test_death_road_native_probe_apply_and_postcondition(elf_class, machine) -> None:
    drtc = _module()
    original, patched, spec = _synthetic_elf(drtc, elf_class, machine)

    assert drtc._native_probe_data(original, spec)["state"] == "original"
    assert drtc._patch_native_data(original, spec) == patched
    assert drtc._native_probe_data(patched, spec)["state"] == "patched"

    changed = bytearray(original)
    changed[-1] = 1
    result = drtc._native_probe_data(changed, spec)
    assert result["state"] == "unsupported"
    assert "canonical native SHA-256" in result["reason"]


@pytest.mark.parametrize(("elf_class", "machine"), [(2, 183), (1, 40)])
def test_death_road_accepts_and_patches_each_supported_abi_independently(
    monkeypatch, tmp_path, elf_class, machine
) -> None:
    drtc = _module()
    original, _patched, spec = _synthetic_elf(drtc, elf_class, machine)
    monkeypatch.setattr(drtc, "_NATIVE_SPECS", (spec,))
    monkeypatch.setattr(drtc, "_dex_probe_data", lambda _data: ({"name": drtc.DEX_ENTRY, "state": "patched"}, {}))
    monkeypatch.setattr(drtc, "_png_probe_data", lambda _data, spec=drtc._SPLASH: {"name": spec.entry, "state": "patched"})

    native = tmp_path / spec.entry
    native.parent.mkdir(parents=True)
    native.write_bytes(original)
    dex = tmp_path / drtc.DEX_ENTRY
    dex.write_bytes(b"synthetic dex")
    splash = tmp_path / drtc.SPLASH_ENTRY
    splash.parent.mkdir(parents=True)
    splash.write_bytes(b"synthetic png")
    extracted = {spec.entry: native, drtc.DEX_ENTRY: dex, drtc.SPLASH_ENTRY: splash}

    assert drtc.probe(extracted)["state"] == "original"
    replacements = drtc.apply(extracted, tmp_path / "out")
    assert set(replacements) == {spec.entry}
    combined = dict(extracted)
    combined.update(replacements)
    assert drtc.probe(combined)["state"] == "patched"


def test_death_road_rejects_any_present_unrecognized_native_abi(monkeypatch, tmp_path) -> None:
    drtc = _module()
    original, _patched, spec = _synthetic_elf(drtc, 2, 183)
    monkeypatch.setattr(drtc, "_NATIVE_SPECS", (spec,))
    monkeypatch.setattr(drtc, "_dex_probe_data", lambda _data: ({"name": drtc.DEX_ENTRY, "state": "patched"}, {}))
    monkeypatch.setattr(drtc, "_png_probe_data", lambda _data, spec=drtc._SPLASH: {"name": spec.entry, "state": "patched"})

    paths = {}
    for entry, data in (
        (spec.entry, original),
        ("lib/x86/libmain.so", b"unknown"),
        (drtc.DEX_ENTRY, b"synthetic dex"),
        (drtc.SPLASH_ENTRY, b"synthetic png"),
    ):
        path = tmp_path / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        paths[entry] = path

    result = drtc.probe(paths)
    assert result["state"] == "unsupported"
    unknown = next(target for target in result["targets"] if target.get("entry") == "lib/x86/libmain.so")
    assert "not audited" in unknown["reason"]


@dataclass
class _Method:
    class_descriptor: str
    name: str
    descriptor: str
    code_offset: int


def _fake_dex_type(edits):
    methods = [
        _Method(edit.class_descriptor, edit.method_name, edit.descriptor, 0x40 + index * 0x30)
        for index, edit in enumerate(edits)
    ]

    class FakeDex:
        def __init__(self, data):
            self.data = bytearray(data)

        def methods(self):
            return iter(methods)

        def finish(self):
            return bytes(self.data)

    return FakeDex, methods


def test_death_road_dex_cleanup_probe_apply_already_patched(monkeypatch) -> None:
    drtc = _module()
    edits = (
        drtc.DexEdit("Lexample/Analytics;", "log", "()V", b"OLD1", b"NEW1", "invented analytics"),
        drtc.DexEdit("Lexample/More;", "show", "()V", b"OLD2", b"NEW2", "invented cross-promo"),
    )
    fake, methods = _fake_dex_type(edits)
    monkeypatch.setattr(drtc, "_DEX_IMAGE", fake)
    data = bytearray(0x180)
    for method, edit in zip(methods, edits):
        struct.pack_into("<I", data, method.code_offset + 12, 8)
        data[method.code_offset + 16 : method.code_offset + 20] = edit.original_prefix

    assert drtc._dex_probe_data(bytes(data), edits)[0]["state"] == "original"
    patched = drtc._patch_dex_data(bytes(data), edits)
    assert drtc._dex_probe_data(patched, edits)[0]["state"] == "patched"
    assert drtc._patch_dex_data(patched, edits) == patched

    missing = edits[:1]
    assert drtc._dex_probe_data(bytes(data), missing)[0]["state"] == "original"
    broken = bytearray(data)
    broken[methods[0].code_offset + 16 : methods[0].code_offset + 20] = b"NOPE"
    assert drtc._dex_probe_data(bytes(broken), edits)[0]["state"] == "unsupported"


def _logo_png(size):
    image = Image.new("RGBA", size, (0, 0, 0, 255))
    # Invented colored logo blocks near each side of the crop-safe region.
    for x in range(30, 60):
        for y in range(25, 75):
            image.putpixel((x, y), (255, 0, 0, 255))
    for x in range(size[0] - 60, size[0] - 30):
        for y in range(25, 75):
            image.putpixel((x, y), (0, 255, 0, 255))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_death_road_splash_transform_preserves_aspect_and_is_deterministic() -> None:
    drtc = _module()
    original = _logo_png((160, 100))
    target = (120, 90)
    expected = drtc._cover_crop_png(original, target)
    spec = drtc.PngSpec(
        "invented.png",
        (160, 100),
        target,
        hashlib.sha256(original).hexdigest(),
        hashlib.sha256(expected).hexdigest(),
    )

    patched = drtc._patch_png_data(original, spec)

    assert patched == expected
    assert drtc._png_probe_data(original, spec)["state"] == "original"
    assert drtc._png_probe_data(patched, spec)["state"] == "patched"
    with Image.open(io.BytesIO(patched)) as image:
        assert image.size == (120, 90)
        assert image.width * 3 == image.height * 4
