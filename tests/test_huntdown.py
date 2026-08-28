"""Proprietary-free tests for Huntdown's native, DEX, and data cleanup."""

from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path
from types import SimpleNamespace

from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _module():
    registry = Registry(REPO_ROOT / "games")
    return registry.module(registry.by_id["huntdown"])


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
            "invented analytics coroutine",
            "analytics",
            0x1100,
            0x200,
            bytes(range(0x10, 0x20)),
            bytes.fromhex("0102030405060708"),
            bytes.fromhex("00008052c0035fd6"),
            bytes(range(0x20, 0x30)),
        ),
        (
            "invented force169 branch",
            "4:3 gameplay",
            0x1180,
            0x280,
            bytes(range(0x30, 0x40)),
            bytes.fromhex("20020036"),
            bytes.fromhex("11000014"),
            bytes(range(0x40, 0x50)),
        ),
        (
            "invented video fit mode",
            "4:3 videos",
            0x1200,
            0x300,
            bytes(range(0x50, 0x60)),
            bytes.fromhex("48008052"),
            bytes.fromhex("28008052"),
            bytes(range(0x60, 0x70)),
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
        if site.scope == "analytics":
            cleaned[site.offset : site.offset + len(site.original)] = site.patched
    spec = module.NativeSpec(
        module.LIBRARY_ENTRY,
        len(data),
        hashlib.sha256(data).hexdigest(),
        hashlib.sha256(cleaned).hexdigest(),
        hashlib.sha256(patched).hexdigest(),
        tuple(sites),
    )
    return bytes(data), bytes(patched), spec


def _finish_dex(data: bytes | bytearray) -> bytes:
    result = bytearray(data)
    result[12:32] = hashlib.sha1(result[32:]).digest()
    struct.pack_into("<I", result, 8, zlib.adler32(result[12:]) & 0xFFFFFFFF)
    return bytes(result)


def _synthetic_dex(module):
    original_instructions = bytes.fromhex("12000e000000")
    patched_instructions = b"\x0e\x00" + b"\0" * 4
    code_offset = 0x60
    instruction_offset = code_offset + 16
    data = bytearray(0x180)
    data[:8] = b"dex\n035\0"
    struct.pack_into("<I", data, 0x20, len(data))
    struct.pack_into("<I", data, code_offset + 12, 3)
    data[instruction_offset : instruction_offset + 6] = original_instructions
    original = _finish_dex(data)
    patched = bytearray(original)
    patched[instruction_offset : instruction_offset + 6] = patched_instructions
    patched = _finish_dex(patched)
    spec = module.DexSpec(
        module.DEX_ENTRY,
        len(original),
        "Lsynthetic/save;",
        "extract",
        "(Landroid/content/Context;)V",
        code_offset,
        instruction_offset,
        original_instructions,
        patched_instructions,
        hashlib.sha256(original_instructions).hexdigest(),
        hashlib.sha256(original).hexdigest(),
        hashlib.sha256(patched).hexdigest(),
    )

    class FakeDex:
        def __init__(self, payload):
            self.data = bytearray(payload)

        def methods(self):
            yield SimpleNamespace(
                class_descriptor=spec.class_descriptor,
                name=spec.method_name,
                descriptor=spec.descriptor,
                code_offset=spec.code_offset,
            )

        def finish(self):
            return _finish_dex(self.data)

    return original, patched, spec, FakeDex


def test_huntdown_production_guards_and_preserved_subsystems() -> None:
    module = _module()
    spec = module._NATIVE_SPEC

    assert spec.size == 66_267_936
    assert spec.original_sha256 == "df7ef60193104e4e6f940741569ed398c741d3ed9247b2cf4456db49bc264793"
    assert spec.cleanup_sha256 == "c2b11060ff373173062fccde5efbb3832efd1acebaabb64347c655142e3e18f6"
    assert spec.patched_sha256 == "2bb8decd8cfa5302ac0be008189f49cff53ce9181efee33302c68ce503546317"
    assert module._CLEANUP_ONLY_SHA256 == "c2b11060ff373173062fccde5efbb3832efd1acebaabb64347c655142e3e18f6"
    assert len(spec.sites) == 6
    for site in spec.sites:
        assert site.rva - site.offset == 0x4000
        assert len(site.original) == len(site.patched)
        assert hashlib.sha256(site.before + site.original + site.after).hexdigest() == site.signature_sha256

    analytics = [site for site in spec.sites if site.scope == "analytics"]
    assert len(analytics) == 3
    assert all(site.name.startswith("Analytics.") for site in analytics)
    assert not any(
        word in site.name.casefold()
        for site in spec.sites
        for word in ("billing", "purchase", "cloud", "achievement", "playgames")
    )


def test_huntdown_native_synthetic_probe_patch_and_rejection() -> None:
    module = _module()
    original, patched, spec = _synthetic_native(module)

    assert module._native_probe_data(original, spec)["state"] == "original"
    assert module._patch_native_data(original, spec) == patched
    assert module._native_probe_data(patched, spec)["state"] == "patched"

    changed = bytearray(original)
    changed[-1] ^= 1
    result = module._native_probe_data(changed, spec)
    assert result["state"] == "original"

    changed[spec.sites[1].offset] ^= 1
    result = module._native_probe_data(changed, spec)
    assert result["state"] == "unsupported"
    assert "guarded native signature" in result["reason"]


def test_huntdown_dex_method_identity_instruction_extent_and_checksums(monkeypatch) -> None:
    module = _module()
    original, patched, spec, fake_dex = _synthetic_dex(module)
    monkeypatch.setattr(module, "_DEX_IMAGE", fake_dex)

    result, offset = module._dex_probe_data(original, spec)
    assert result["state"] == "original"
    assert offset == spec.instruction_offset
    output = module._patch_dex_data(original, spec)
    assert output == patched
    assert module._dex_probe_data(output, spec)[0]["state"] == "patched"
    assert output[12:32] == hashlib.sha1(output[32:]).digest()
    assert struct.unpack_from("<I", output, 8)[0] == zlib.adler32(output[12:]) & 0xFFFFFFFF


def test_huntdown_empty_zip_removes_injected_contents_exactly() -> None:
    module = _module()
    spec = module._DATA_SPEC

    assert len(spec.patched) == 22
    assert spec.patched == b"PK\x05\x06" + b"\0" * 18
    assert hashlib.sha256(spec.patched).hexdigest() == spec.patched_sha256
    assert module._data_probe_data(spec.patched)["state"] == "patched"
    assert b"playerprefs" not in spec.patched.lower()
    assert b"device" not in spec.patched.lower()


def test_huntdown_synthetic_apply_finishes_all_three_entries(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    native_original, native_patched, native_spec = _synthetic_native(module)
    dex_original, dex_patched, dex_spec, fake_dex = _synthetic_dex(module)
    source_data = b"invented injected private payload"
    data_spec = module.DataSpec(
        module.INJECTED_DATA_ENTRY,
        len(source_data),
        hashlib.sha256(source_data).hexdigest(),
        module._EMPTY_ZIP,
        hashlib.sha256(module._EMPTY_ZIP).hexdigest(),
    )
    monkeypatch.setattr(module, "_NATIVE_SPEC", native_spec)
    monkeypatch.setattr(module, "_DEX_SPEC", dex_spec)
    monkeypatch.setattr(module, "_DATA_SPEC", data_spec)
    monkeypatch.setattr(module, "_DEX_IMAGE", fake_dex)

    extracted = {}
    for entry, payload in (
        (module.LIBRARY_ENTRY, native_original),
        (module.DEX_ENTRY, dex_original),
        (module.INJECTED_DATA_ENTRY, source_data),
    ):
        path = tmp_path / "source" / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        extracted[entry] = path

    assert module.probe(extracted)["state"] == "original"
    replacements = module.apply(extracted, tmp_path / "patched")
    assert replacements[module.LIBRARY_ENTRY].read_bytes() == native_patched
    assert replacements[module.DEX_ENTRY].read_bytes() == dex_patched
    assert replacements[module.INJECTED_DATA_ENTRY].read_bytes() == module._EMPTY_ZIP
    assert module.probe(replacements)["state"] == "patched"
    assert module.apply(replacements, tmp_path / "already") == {}


def test_huntdown_optional_cleanup_entries_may_be_absent(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    native_original, _native_patched, native_spec = _synthetic_native(module)
    monkeypatch.setattr(module, "_NATIVE_SPEC", native_spec)
    native_path = tmp_path / "source" / module.LIBRARY_ENTRY
    native_path.parent.mkdir(parents=True)
    native_path.write_bytes(native_original)
    extracted = {module.LIBRARY_ENTRY: native_path}

    report = module.probe(extracted)
    assert report["state"] == "original"
    assert all("analytics" not in target["name"] for target in report["targets"])
    replacements = module.apply(extracted, tmp_path / "patched")

    assert set(replacements) == {module.LIBRARY_ENTRY}
    assert module.probe(replacements)["state"] == "patched"


def test_huntdown_unknown_optional_data_is_preserved_and_core_mixed_state_finishes(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    native_original, _native_patched, native_spec = _synthetic_native(module)
    mixed = bytearray(native_original)
    core_sites = module._four_three_sites(native_spec)
    mixed[core_sites[0].offset : core_sites[0].offset + len(core_sites[0].original)] = (
        core_sites[0].patched
    )
    monkeypatch.setattr(module, "_NATIVE_SPEC", native_spec)

    unknown_dex = b"unrecognized launch code that belongs to this APK"
    unknown_data = b"unrecognized launch data that must survive unchanged"
    extracted = {}
    for entry, payload in (
        (module.LIBRARY_ENTRY, bytes(mixed)),
        (module.DEX_ENTRY, unknown_dex),
        (module.INJECTED_DATA_ENTRY, unknown_data),
    ):
        path = tmp_path / "source" / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        extracted[entry] = path

    assert module.probe(extracted)["state"] == "original"
    replacements = module.apply(extracted, tmp_path / "patched")

    assert set(replacements) == {module.LIBRARY_ENTRY}
    assert extracted[module.DEX_ENTRY].read_bytes() == unknown_dex
    assert extracted[module.INJECTED_DATA_ENTRY].read_bytes() == unknown_data
    combined = dict(extracted)
    combined.update(replacements)
    assert module.probe(combined)["state"] == "patched"


def test_huntdown_ambiguous_optional_native_cleanup_is_silently_skipped(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    native_original, _native_patched, native_spec = _synthetic_native(module)
    ambiguous = bytearray(native_original)
    cleanup = module._cleanup_sites(native_spec)[0]
    signature = cleanup.before + cleanup.original + cleanup.after
    duplicate = 0x380
    ambiguous[duplicate : duplicate + len(signature)] = signature
    monkeypatch.setattr(module, "_NATIVE_SPEC", native_spec)
    source = tmp_path / "source" / module.LIBRARY_ENTRY
    source.parent.mkdir(parents=True)
    source.write_bytes(ambiguous)

    replacements = module.apply({module.LIBRARY_ENTRY: source}, tmp_path / "patched")
    output = replacements[module.LIBRARY_ENTRY].read_bytes()

    assert output[cleanup.offset : cleanup.offset + len(cleanup.original)] == cleanup.original
    assert output[duplicate + len(cleanup.before) : duplicate + len(cleanup.before) + len(cleanup.original)] == cleanup.original
    assert module._native_probe_data(output, native_spec)["state"] == "patched"


def test_huntdown_cleanup_entry_point_preserves_4x3_branches(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    native_original, _native_patched, native_spec = _synthetic_native(module)
    dex_original, dex_patched, dex_spec, fake_dex = _synthetic_dex(module)
    source_data = b"invented injected private payload"
    data_spec = module.DataSpec(
        module.INJECTED_DATA_ENTRY,
        len(source_data),
        hashlib.sha256(source_data).hexdigest(),
        module._EMPTY_ZIP,
        hashlib.sha256(module._EMPTY_ZIP).hexdigest(),
    )
    monkeypatch.setattr(module, "_NATIVE_SPEC", native_spec)
    monkeypatch.setattr(module, "_DEX_SPEC", dex_spec)
    monkeypatch.setattr(module, "_DATA_SPEC", data_spec)
    monkeypatch.setattr(module, "_DEX_IMAGE", fake_dex)
    extracted = {}
    for entry, payload in (
        (module.LIBRARY_ENTRY, native_original),
        (module.DEX_ENTRY, dex_original),
        (module.INJECTED_DATA_ENTRY, source_data),
    ):
        path = tmp_path / "source" / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        extracted[entry] = path

    replacements = module.apply_cleanup(extracted, tmp_path / "cleaned")
    native_cleaned = replacements[module.LIBRARY_ENTRY].read_bytes()
    assert hashlib.sha256(native_cleaned).hexdigest() == native_spec.cleanup_sha256
    assert replacements[module.DEX_ENTRY].read_bytes() == dex_patched
    assert replacements[module.INJECTED_DATA_ENTRY].read_bytes() == module._EMPTY_ZIP
    assert module.probe_cleanup(replacements)["state"] == "patched"
    assert module.probe(replacements)["state"] == "original"
    for site in module._four_three_sites(native_spec):
        assert native_cleaned[
            site.offset : site.offset + len(site.original)
        ] == site.original


def test_huntdown_config_is_explicitly_visual_pending() -> None:
    registry = Registry(REPO_ROOT / "games")
    config = registry.by_id["huntdown"]

    assert config.package_names == ("com.coffeestain.huntdown",)
    assert config.experimental is True
    assert config.output_name.endswith("-4x3.apk")
    module = registry.module(config)
    assert module.REQUIRED_ENTRIES == (module.LIBRARY_ENTRY,)
    assert set(config.preferred_entries) == {module.DEX_ENTRY, module.INJECTED_DATA_ENTRY}
