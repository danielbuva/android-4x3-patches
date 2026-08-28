"""Proprietary-free tests for Grimvalor's exact native patch module."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _module():
    registry = Registry(REPO_ROOT / "games")
    return registry.module(registry.by_id["grimvalor"])


def _synthetic_native(module):
    data = bytearray(b"\xa5" * 0x500)
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
        0,
        0,
        0,
    )
    struct.pack_into(
        "<IIQQQQQQ",
        data,
        64,
        1,
        5,
        0x100,
        0x1000,
        0x1000,
        0x400,
        0x400,
        0x1000,
    )
    definitions = (
        (
            "invented analytics sink",
            "analytics",
            0x1100,
            0x200,
            bytes(range(0x10, 0x20)),
            bytes.fromhex("0102030405060708"),
            bytes.fromhex("c0035fd61f2003d5"),
            bytes(range(0x20, 0x30)),
        ),
        (
            "invented 4:3 selector",
            "4:3 UI",
            0x1180,
            0x280,
            bytes(range(0x30, 0x40)),
            bytes.fromhex("1112131415161718"),
            bytes.fromhex("20008052c0035fd6"),
            bytes(range(0x40, 0x50)),
        ),
    )
    sites = []
    for name, scope, rva, offset, before, original, patched, after in definitions:
        start = offset - len(before)
        data[start : start + len(before + original + after)] = before + original + after
        sites.append(
            module.NativeSite(
                name,
                scope,
                rva,
                offset,
                before,
                original,
                patched,
                after,
                hashlib.sha256(before + original + after).hexdigest(),
            )
        )
    patched = bytearray(data)
    for site in sites:
        patched[site.offset : site.offset + len(site.original)] = site.patched
    cleaned = bytearray(data)
    for site in sites:
        if site.scope in {"ads", "analytics"}:
            cleaned[site.offset : site.offset + len(site.original)] = site.patched
    spec = module.NativeSpec(
        "lib/arm64-v8a/libil2cpp.so",
        len(data),
        hashlib.sha256(data).hexdigest(),
        hashlib.sha256(cleaned).hexdigest(),
        hashlib.sha256(patched).hexdigest(),
        tuple(sites),
    )
    return bytes(data), bytes(patched), spec


def test_grimvalor_production_targets_have_complete_hash_and_mapping_guards() -> None:
    module = _module()
    spec = module._NATIVE_SPEC

    assert spec.size == 57_192_968
    assert spec.original_sha256 == "4376a6f0fa92e9ddb23b2285de7f79c2ff9d0b412f611378d42791226b1a7d84"
    assert spec.cleanup_sha256 == "d606a689702a3667eafd2470a94268f7b3c616c25d3d9e6141a1ea1baa8c4d2b"
    assert spec.patched_sha256 == "599e80c40aeeb708abdb7c633ac0d46c625473f833b5c4a0c6ed855f6c70592a"
    assert module._CLEANUP_ONLY_SHA256 == "d606a689702a3667eafd2470a94268f7b3c616c25d3d9e6141a1ea1baa8c4d2b"
    assert len(spec.sites) == 10
    for site in spec.sites:
        assert site.rva - site.offset == 0x4000
        assert len(site.original) == len(site.patched)
        assert hashlib.sha256(site.before + site.original + site.after).hexdigest() == site.signature_sha256

    names = {site.name for site in spec.sites}
    assert "UIResolution.get_is4_3" in names
    assert sum(site.scope.startswith("4:3") for site in spec.sites) == 1
    assert not any(
        word in name.casefold()
        for name in names
        for word in ("billing", "purchase", "cloud", "achievement", "playgames")
    )


def test_grimvalor_synthetic_probe_apply_and_partial_finish(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    original, patched, spec = _synthetic_native(module)
    monkeypatch.setattr(module, "_NATIVE_SPEC", spec)

    source = tmp_path / "source" / "libil2cpp.so"
    source.parent.mkdir()
    source.write_bytes(original)
    extracted = {module.LIBRARY_ENTRY: source}

    assert module.probe(extracted)["state"] == "original"
    replacements = module.apply(extracted, tmp_path / "patched")
    assert replacements[module.LIBRARY_ENTRY].read_bytes() == patched
    assert module.probe(replacements)["state"] == "patched"
    assert module.apply(replacements, tmp_path / "already") == {}

    partial = bytearray(original)
    first = spec.sites[0]
    partial[first.offset : first.offset + len(first.original)] = first.patched
    assert module._native_probe_data(partial, spec)["state"] == "original"
    assert module._patch_native_data(bytes(partial), spec) == patched


def test_grimvalor_cleanup_entry_point_keeps_4x3_selector_original(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    original, _patched, spec = _synthetic_native(module)
    monkeypatch.setattr(module, "_NATIVE_SPEC", spec)
    source = tmp_path / "source" / "libil2cpp.so"
    source.parent.mkdir()
    source.write_bytes(original)
    replacements = module.apply_cleanup(
        {module.LIBRARY_ENTRY: source}, tmp_path / "cleaned"
    )
    cleaned = replacements[module.LIBRARY_ENTRY].read_bytes()

    assert hashlib.sha256(cleaned).hexdigest() == spec.cleanup_sha256
    assert module.probe_cleanup(replacements)["state"] == "patched"
    assert module.probe(replacements)["state"] == "original"
    by_name = {site.name: site for site in spec.sites}
    selector = by_name["invented 4:3 selector"]
    assert cleaned[
        selector.offset : selector.offset + len(selector.original)
    ] == selector.original


def test_grimvalor_rejects_unrelated_native_changes_and_moved_signatures() -> None:
    module = _module()
    original, _patched, spec = _synthetic_native(module)

    unrelated = bytearray(original)
    unrelated[-1] ^= 1
    result = module._native_probe_data(unrelated, spec)
    assert result["state"] == "unsupported"
    assert "canonical native SHA-256" in result["reason"]

    duplicated = bytearray(original)
    site = spec.sites[0]
    signature = site.before + site.original + site.after
    duplicated[0x300 : 0x300 + len(signature)] = signature
    result = module._native_probe_data(duplicated, spec)
    assert result["state"] == "ambiguous"


def test_grimvalor_config_is_explicitly_visual_pending() -> None:
    registry = Registry(REPO_ROOT / "games")
    config = registry.by_id["grimvalor"]

    assert config.package_names == ("com.direlight.grimvalor",)
    assert config.experimental is True
    assert config.output_name.endswith("-4x3.apk")
