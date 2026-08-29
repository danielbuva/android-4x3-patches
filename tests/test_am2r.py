"""Proprietary-free tests for AM2R's guarded native patch orchestration."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _module():
    registry = Registry(REPO_ROOT / "games")
    return registry.module(registry.by_id["am2r"])


def _splash(path: Path, size: tuple[int, int] = (1704, 960)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (12, 34, 56)).save(path, format="PNG")
    return path


def _synthetic_elf(module, *, load_virtual_address: int = 0):
    """Create a tiny invented ELF and matching test-only library specification."""

    data = bytearray(0x200)
    data[:16] = b"\x7fELF\x01\x01\x01" + b"\0" * 9
    struct.pack_into(
        "<HHIIIIIHHHHHH",
        data,
        16,
        3,  # ET_DYN
        3,  # EM_386
        1,
        0,
        52,
        0,
        0,
        52,
        32,
        1,
        0,
        0,
        0,
    )
    struct.pack_into(
        "<IIIIIIII",
        data,
        52,
        1,  # PT_LOAD
        0,
        load_virtual_address,
        load_virtual_address,
        len(data),
        len(data),
        5,  # PF_R | PF_X
        0x1000,
    )
    sites = (
        module.PatchSite(
            "invented setting load",
            0x100,
            0x100,
            b"OLD1",
            b"NEW1",
        ),
        module.PatchSite(
            "invented setting toggle",
            0x120,
            0x120,
            b"OLD-TWO!",
            b"NEW-TWO!",
        ),
    )
    for site in sites:
        data[site.offset : site.offset + len(site.original)] = site.original

    patched = bytearray(data)
    for site in sites:
        patched[site.offset : site.offset + len(site.original)] = site.patched

    spec = module.LibrarySpec(
        abi="synthetic-x86",
        entry="lib/synthetic/libyoyo.so",
        machine=3,
        size=len(data),
        original_sha256=hashlib.sha256(data).hexdigest(),
        patched_sha256=hashlib.sha256(patched).hexdigest(),
        sites=sites,
    )
    return bytes(data), bytes(patched), spec


def test_am2r_production_metadata_guards_every_bundled_abi() -> None:
    am2r = _module()

    assert tuple(spec.abi for spec in am2r._LIBRARIES) == (
        "armeabi",
        "armeabi-v7a",
        "mips",
        "x86",
    )
    assert am2r.REQUIRED_ENTRIES == (am2r.SPLASH_ENTRY,)
    for spec in am2r._LIBRARIES:
        assert len(spec.original_sha256) == 64
        assert len(spec.patched_sha256) == 64
        assert spec.original_sha256 != spec.patched_sha256
        for site in spec.sites:
            assert site.offset == site.virtual_address
            assert site.offset + len(site.original) <= spec.size
            assert len(site.original) == len(site.patched)
            assert site.original != site.patched

    config = Registry(REPO_ROOT / "games").by_id["am2r"]
    assert config.experimental
    assert config.preferred_entries == ("lib/*/libyoyo.so",)
    assert config.entry_globs == ("lib/*/libyoyo.so",)


def test_am2r_synthetic_probe_apply_and_postcondition(tmp_path: Path, monkeypatch) -> None:
    am2r = _module()
    original, patched, spec = _synthetic_elf(am2r)
    monkeypatch.setattr(am2r, "_LIBRARIES", (spec,))
    monkeypatch.setattr(am2r, "REQUIRED_ENTRIES", (spec.entry,))

    source = tmp_path / "original" / "libyoyo.so"
    source.parent.mkdir()
    source.write_bytes(original)
    extracted = {spec.entry: source}

    assert am2r.probe(extracted)["state"] == "original"
    replacements = am2r.apply(extracted, tmp_path / "patched")
    assert replacements[spec.entry].read_bytes() == patched
    assert am2r.probe(replacements)["state"] == "patched"
    assert am2r.apply(replacements, tmp_path / "already-patched") == {}


def test_am2r_accepts_and_patches_one_present_audited_abi(
    tmp_path: Path, monkeypatch
) -> None:
    am2r = _module()
    original, patched, present = _synthetic_elf(am2r)
    absent = replace(
        present,
        abi="synthetic-absent",
        entry="lib/synthetic-absent/libyoyo.so",
    )
    monkeypatch.setattr(am2r, "_LIBRARIES", (present, absent))

    empty = am2r.probe({})
    assert empty["state"] == "unsupported"
    assert "no discoverable" in empty["detail"]

    source = tmp_path / present.entry
    source.parent.mkdir(parents=True)
    source.write_bytes(original)
    extracted = {
        present.entry: source,
        am2r.SPLASH_ENTRY: _splash(tmp_path / am2r.SPLASH_ENTRY),
    }

    result = am2r.probe(extracted)
    assert result["state"] == "original"
    assert {target["entry"] for target in result["targets"]} == {
        present.entry,
        am2r.SPLASH_ENTRY,
    }
    replacements = am2r.apply(extracted, tmp_path / "patched-subset")
    assert set(replacements) == {present.entry, am2r.SPLASH_ENTRY}
    assert replacements[present.entry].read_bytes() == patched
    assert am2r.probe(replacements)["state"] == "patched"


def test_am2r_startup_image_is_center_cropped_without_squishing(tmp_path: Path) -> None:
    am2r = _module()
    source = _splash(tmp_path / "wide.png")
    original = source.read_bytes()

    assert am2r._splash_state(original)["state"] == "original"
    patched = am2r._crop_splash_to_4x3(original)
    assert am2r._splash_state(patched)["state"] == "patched"
    output = tmp_path / "cropped.png"
    output.write_bytes(patched)
    with Image.open(output) as image:
        assert image.size == (1280, 960)
        assert image.getpixel((0, 0)) == (12, 34, 56)


def test_am2r_rejects_present_unrecognized_abi(
    tmp_path: Path, monkeypatch
) -> None:
    am2r = _module()
    original, _patched, spec = _synthetic_elf(am2r)
    monkeypatch.setattr(am2r, "_LIBRARIES", (spec,))

    supported = tmp_path / spec.entry
    supported.parent.mkdir(parents=True)
    supported.write_bytes(original)
    unknown_entry = "lib/arm64-v8a/libyoyo.so"
    unknown = tmp_path / unknown_entry
    unknown.parent.mkdir(parents=True)
    unknown.write_bytes(original)
    extracted = {spec.entry: supported, unknown_entry: unknown}

    result = am2r.probe(extracted)
    assert result["state"] == "unsupported"
    unknown_target = next(
        target for target in result["targets"] if target["entry"] == unknown_entry
    )
    assert "not an audited" in unknown_target["reason"]
    with pytest.raises(RuntimeError, match="unsupported"):
        am2r.apply(extracted, tmp_path / "refused-unknown-abi")


def test_am2r_rejects_unknown_hash_even_when_patch_bytes_are_recognizable(
    tmp_path: Path, monkeypatch
) -> None:
    am2r = _module()
    original, _patched, spec = _synthetic_elf(am2r)
    monkeypatch.setattr(am2r, "_LIBRARIES", (spec,))
    monkeypatch.setattr(am2r, "REQUIRED_ENTRIES", (spec.entry,))
    changed = bytearray(original)
    changed[-1] = 1
    source = tmp_path / "changed-libyoyo.so"
    source.write_bytes(changed)
    extracted = {spec.entry: source}

    result = am2r.probe(extracted)

    assert result["state"] == "unsupported"
    assert "SHA-256" in result["targets"][0]["reason"]
    with pytest.raises(RuntimeError, match="unsupported"):
        am2r.apply(extracted, tmp_path / "refused")


def test_am2r_rejects_hash_instruction_disagreement() -> None:
    am2r = _module()
    original, _patched, spec = _synthetic_elf(am2r)
    changed = bytearray(original)
    changed[spec.sites[0].offset : spec.sites[0].offset + 4] = b"NOPE"
    contradictory = replace(
        spec,
        original_sha256=hashlib.sha256(changed).hexdigest(),
    )

    result = am2r._probe_data(changed, contradictory)

    assert result["state"] == "unsupported"
    assert result["reason"] == "library hash and guarded instruction state disagree"


def test_am2r_rejects_changed_elf_offset_to_virtual_address_mapping() -> None:
    am2r = _module()
    original, _patched, spec = _synthetic_elf(am2r, load_virtual_address=0x1000)

    result = am2r._probe_data(original, spec)

    assert result["state"] == "unsupported"
    assert "ELF mapping changed" in result["reason"]
