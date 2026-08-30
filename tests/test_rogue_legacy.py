"""Proprietary-free tests for Rogue Legacy's managed-store patch."""

from __future__ import annotations

import struct
from pathlib import Path

import lz4.block
import pytest

from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _module():
    registry = Registry(REPO_ROOT / "games")
    return registry.module(registry.by_id["rogue-legacy"])


def _synthetic_managed_image(module, *, duplicate_region: bool = False) -> bytes:
    """Build a tiny invented PE/CLI image with one #US record."""

    data = bytearray(0x1000)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x14C)
    struct.pack_into("<H", data, 0x86, 1)
    struct.pack_into("<H", data, 0x94, 0xE0)

    optional = 0x98
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<II", data, optional + 96 + 14 * 8, 0x2020, 0x48)
    section = optional + 0xE0
    data[section : section + 8] = b".invented"
    struct.pack_into("<IIII", data, section + 8, 0xE00, 0x2000, 0xE00, 0x200)

    cli = 0x220
    struct.pack_into("<IHHII", data, cli, 0x48, 2, 5, 0x2100, 0x200)
    metadata = 0x300
    data[metadata : metadata + 4] = b"BSJB"
    struct.pack_into("<HHI", data, metadata + 4, 1, 1, 0)
    version = b"v4.0.30319\0\0"
    struct.pack_into("<I", data, metadata + 12, len(version))
    data[metadata + 16 : metadata + 16 + len(version)] = version
    cursor = (metadata + 16 + len(version) + 3) & ~3
    struct.pack_into("<HH", data, cursor, 0, 1)
    cursor += 4
    heap_relative = 0x80
    original_string = "ad".encode("utf-16le")
    heap = b"\0" + bytes([len(original_string) + 1]) + original_string + b"\0"
    struct.pack_into("<II", data, cursor, heap_relative, len(heap))
    data[cursor + 8 : cursor + 12] = b"#US\0"
    data[metadata + heap_relative : metadata + heap_relative + len(heap)] = heap

    invented = b"INVENTED-BEFORE" + b"OLD!" + b"-AFTER-INVENTED"
    data[0x700 : 0x700 + len(invented)] = invented
    second = b"SECOND-BEFORE" + b"old2" + b"-SECOND-AFTER"
    data[0x800 : 0x800 + len(second)] = second
    if duplicate_region:
        data[0x780 : 0x780 + len(invented)] = invented
    return bytes(data)


def _synthetic_store(module, assembly: bytes) -> tuple[bytes, bytes]:
    compressed = lz4.block.compress(
        assembly, mode="high_compression", compression=12, store_size=False
    )
    stored = b"XALZ" + struct.pack("<II", 7, len(assembly)) + compressed
    data_offset = 0x100
    blob = bytearray(data_offset + len(stored) + 0x200)
    struct.pack_into("<5I", blob, 0, module._XABA_MAGIC, 1, 1, 1, 0)
    struct.pack_into("<6I", blob, 20, data_offset, len(stored), 0, 0, 0, 0)
    blob[data_offset : data_offset + len(stored)] = stored
    manifest = (
        b"Hash 32     Hash 64             Blob ID  Blob idx  Name\r\n"
        b"0x12345678  0x123456789abcdef0  000      0000      RogueLegacy.Android\r\n"
    )
    return bytes(blob), manifest


def _install_synthetic_targets(module, monkeypatch) -> None:
    regions = (
        module._Region(
            "Invented.Managed.Method",
            b"INVENTED-BEFORE",
            4,
            b"-AFTER-INVENTED",
            (module._Change("invented virtual height", 0, b"OLD!", b"NEW!"),),
        ),
        module._Region(
            "Invented.Second.Method",
            b"SECOND-BEFORE",
            4,
            b"-SECOND-AFTER",
            (module._Change("invented UI anchor", 0, b"old2", b"new2"),),
        ),
    )
    string = module._StringTarget(
        "invented branding", 0x70000001, "ad", "  ", optional=True
    )
    monkeypatch.setattr(module, "_REGIONS", regions)
    monkeypatch.setattr(module, "_STRING_TARGETS", (string,))


def _write_entries(tmp_path: Path, module, blob: bytes, manifest: bytes):
    blob_path = tmp_path / "source" / "assemblies.blob"
    manifest_path = tmp_path / "source" / "assemblies.manifest"
    blob_path.parent.mkdir(parents=True)
    blob_path.write_bytes(blob)
    manifest_path.write_bytes(manifest)
    return {module.BLOB_ENTRY: blob_path, module.MANIFEST_ENTRY: manifest_path}


def test_rogue_legacy_synthetic_probe_apply_and_postcondition(
    tmp_path: Path, monkeypatch
) -> None:
    rogue = _module()
    _install_synthetic_targets(rogue, monkeypatch)
    assembly = _synthetic_managed_image(rogue)
    blob, manifest = _synthetic_store(rogue, assembly)
    extracted = _write_entries(tmp_path, rogue, blob, manifest)

    assert rogue.probe(extracted)["state"] == "original"
    replacements = rogue.apply(extracted, tmp_path / "patched")

    patched_input = dict(extracted)
    patched_input.update(replacements)
    assert set(replacements) == {rogue.BLOB_ENTRY}
    assert rogue.probe(patched_input)["state"] == "patched"
    assert rogue.apply(patched_input, tmp_path / "already-patched") == {}

    decoded, _info = rogue._assembly_from_store(
        replacements[rogue.BLOB_ENTRY].read_bytes(), manifest
    )
    assert b"INVENTED-BEFORENEW!-AFTER-INVENTED" in decoded
    heap_start, heap_size = rogue._user_string_heap(decoded)
    assert rogue._user_string_record(decoded, heap_start, heap_size, 0x70000001)[3] == "  "


def test_rogue_legacy_rejects_ambiguous_managed_region(
    tmp_path: Path, monkeypatch
) -> None:
    rogue = _module()
    _install_synthetic_targets(rogue, monkeypatch)
    assembly = _synthetic_managed_image(rogue, duplicate_region=True)
    blob, manifest = _synthetic_store(rogue, assembly)
    extracted = _write_entries(tmp_path, rogue, blob, manifest)

    result = rogue.probe(extracted)

    assert result["state"] == "ambiguous"
    assert any(target["state"] == "ambiguous" for target in result["targets"])
    with pytest.raises(RuntimeError, match="ambiguous"):
        rogue.apply(extracted, tmp_path / "refused")


def test_rogue_legacy_rejects_unknown_user_string(
    tmp_path: Path, monkeypatch
) -> None:
    rogue = _module()
    _install_synthetic_targets(rogue, monkeypatch)
    assembly = bytearray(_synthetic_managed_image(rogue))
    heap_start, heap_size = rogue._user_string_heap(assembly)
    payload, old, _kind, _value = rogue._user_string_record(
        assembly, heap_start, heap_size, 0x70000001
    )
    assembly[payload : payload + len(old)] = "zz".encode("utf-16le")
    blob, manifest = _synthetic_store(rogue, bytes(assembly))
    extracted = _write_entries(tmp_path, rogue, blob, manifest)

    result = rogue.probe(extracted)

    assert result["state"] == "original"
    assert not any(target["name"] == "invented branding" for target in result["targets"])
    replacements = rogue.apply(extracted, tmp_path / "patched")
    decoded, _info = rogue._assembly_from_store(
        replacements[rogue.BLOB_ENTRY].read_bytes(), manifest
    )
    heap_start, heap_size = rogue._user_string_heap(decoded)
    assert rogue._user_string_record(decoded, heap_start, heap_size, 0x70000001)[3] == "zz"
    core, _actions = rogue._discover_assembly(decoded)
    assert rogue._overall(core) == "patched"


def test_rogue_legacy_absent_optional_cleanup_does_not_gate_core(
    tmp_path: Path, monkeypatch
) -> None:
    rogue = _module()
    _install_synthetic_targets(rogue, monkeypatch)
    monkeypatch.setattr(rogue, "_STRING_TARGETS", ())
    # An optional method from a different source is also allowed to be absent.
    optional_region = rogue._Region(
        "Absent.Porter.Method",
        b"NO-SUCH-BEFORE",
        4,
        b"NO-SUCH-AFTER",
        (rogue._Change("optional promo", 0, b"old!", b"new!", optional=True),),
    )
    monkeypatch.setattr(rogue, "_REGIONS", rogue._REGIONS + (optional_region,))
    blob, manifest = _synthetic_store(rogue, _synthetic_managed_image(rogue))
    extracted = _write_entries(tmp_path, rogue, blob, manifest)

    assert rogue.probe(extracted)["state"] == "original"
    replacements = rogue.apply(extracted, tmp_path / "patched")
    combined = dict(extracted)
    combined.update(replacements)
    assert rogue.probe(combined)["state"] == "patched"


def test_rogue_legacy_mixed_core_state_finishes_and_recognized_cleanup_runs(
    tmp_path: Path, monkeypatch
) -> None:
    rogue = _module()
    _install_synthetic_targets(rogue, monkeypatch)
    assembly = bytearray(_synthetic_managed_image(rogue))
    assembly[0x700 + len(b"INVENTED-BEFORE") : 0x700 + len(b"INVENTED-BEFORE") + 4] = b"NEW!"
    blob, manifest = _synthetic_store(rogue, bytes(assembly))
    extracted = _write_entries(tmp_path, rogue, blob, manifest)

    assert rogue.probe(extracted)["state"] == "original"
    replacements = rogue.apply(extracted, tmp_path / "patched")
    combined = dict(extracted)
    combined.update(replacements)
    assert rogue.probe(combined)["state"] == "patched"
    decoded, _info = rogue._assembly_from_store(
        replacements[rogue.BLOB_ENTRY].read_bytes(), manifest
    )
    assert b"SECOND-BEFOREnew2-SECOND-AFTER" in decoded
    heap_start, heap_size = rogue._user_string_heap(decoded)
    assert rogue._user_string_record(decoded, heap_start, heap_size, 0x70000001)[3] == "  "


def test_rogue_legacy_requires_one_named_manifest_mapping(
    tmp_path: Path, monkeypatch
) -> None:
    rogue = _module()
    _install_synthetic_targets(rogue, monkeypatch)
    blob, _manifest = _synthetic_store(rogue, _synthetic_managed_image(rogue))
    extracted = _write_entries(
        tmp_path,
        rogue,
        blob,
        b"Hash 32 Hash 64 Blob ID Blob idx Name\n0x1 0x2 000 0000 Other.Game\n",
    )

    result = rogue.probe(extracted)

    assert result["state"] == "unsupported"
    assert "0 'RogueLegacy.Android' mappings" in result["targets"][0]["reason"]


def test_rogue_legacy_production_targets_are_guarded_and_length_preserving() -> None:
    rogue = _module()

    assert len(rogue._REGIONS) >= 10
    assert len(rogue._STRING_TARGETS) >= 6
    assert any("Telegram" in item.name for item in rogue._STRING_TARGETS)
    assert any(item.optional for item in rogue._STRING_TARGETS)
    assert any(change.optional for region in rogue._REGIONS for change in region.changes)
    changes = {
        change.name: change
        for region in rogue._REGIONS
        for change in region.changes
    }
    assert changes["map and teleporter surface height"].original == rogue._i4(620)
    assert changes["map and teleporter surface height"].patched == rogue._i4(890)
    assert changes["reinitialized map surface height"].original == rogue._i4(620)
    assert changes["reinitialized map surface height"].patched == rogue._i4(890)
    assert changes["map and teleporter render-target height"].original == rogue._i4(720)
    assert changes["map and teleporter render-target height"].patched == rogue._i4(990)
    assert changes["map and teleporter camera center"].original == rogue._r4(360)
    assert changes["map and teleporter camera center"].patched == rogue._r4(495)
    assert changes["map unknown-room label center"].original == rogue._r4(360)
    assert changes["map unknown-room label center"].patched == rogue._r4(495)
    assert changes["map title world-grid normalization"].original == rogue._r4(990)
    assert changes["map title world-grid normalization"].patched == rogue._r4(720)
    assert changes["map legend bottom edge"].original == rogue._i4(720)
    assert changes["map legend bottom edge"].patched == rogue._i4(990)
    assert changes["options list slide distance"].original == rogue._r4(495)
    assert changes["options list slide distance"].patched == rogue._r4(360)
    assert changes["options return slide distance"].original == rogue._r4(360)
    assert changes["options return slide distance"].patched == rogue._r4(495)
    assert changes["options exit slide distance"].original == rogue._r4(-360)
    assert changes["options exit slide distance"].patched == rogue._r4(-495)
    gate_setup = changes["proportional right-aligned loading gate setup"]
    assert len(gate_setup.original) == 96
    assert len(gate_setup.patched) == 96
    assert gate_setup.patched.count(rogue._r4(2.75)) == 2
    assert rogue._r4(-495) in gate_setup.patched
    assert gate_setup.patched.index(rogue._r4(-495)) > gate_setup.patched.index(
        rogue._r4(2.75)
    )
    assert len(changes["top-anchored death spotlight vertical scale"].original) == 76
    assert len(changes["top-anchored death spotlight vertical scale"].patched) == 76
    assert rogue._r4(1.55) in changes[
        "top-anchored death spotlight vertical scale"
    ].patched
    assert len(changes["top-anchored boss-death spotlight vertical scale"].original) == 76
    assert len(changes["top-anchored boss-death spotlight vertical scale"].patched) == 76
    assert rogue._r4(1.55) in changes[
        "top-anchored boss-death spotlight vertical scale"
    ].patched
    assert changes["preserve loading-text X after gate alignment"].original == rogue._r4(
        995
    )
    assert changes["preserve loading-text X after gate alignment"].patched == rogue._r4(
        1490
    )
    assert changes["hide lineage touch stick"].patched == b"\0" * 6
    assert changes["hide lineage touch select button"].patched == b"\0" * 18
    assert changes["hide map touch buttons"].patched == b"\0" * 12
    assert changes["dock side projectile marker at bottom edge"].original == bytes.fromhex(
        "3615"
    )
    assert changes["dock side projectile marker at bottom edge"].patched == b"\0\0"
    assert changes["projectile edge-marker bottom clamp"].original == rogue._i4(720)
    assert changes["projectile edge-marker bottom clamp"].patched == rogue._i4(990)
    assert len(changes["pause dimmer top anchor"].original) == 24
    assert len(changes["pause dimmer top anchor"].patched) == 24
    assert changes["pause dimmer height from SetWidth"].patched == bytes.fromhex(
        "7ef917000400"
    )
    assert changes["pause dimmer height from SetHeight"].patched == bytes.fromhex(
        "7ef917000400"
    )
    assert changes["pause dimmer vertical overscan from SetWidth"].original == rogue._i4s(
        20
    )
    assert changes["pause dimmer vertical overscan from SetWidth"].patched == rogue._i4s(
        127
    )
    exit_rows = changes["preserve centered option rows on exit"]
    assert len(exit_rows.original) == 22
    assert exit_rows.patched == b"\0" * 22
    for region in rogue._REGIONS:
        assert region.before and region.after
        for change in region.changes:
            assert len(change.original) == len(change.patched)
            assert change.original != change.patched
            assert 0 <= change.relative < region.span
    for target in rogue._STRING_TARGETS:
        assert len(target.original.encode("utf-16le")) == len(
            target.patched.encode("utf-16le")
        )


def test_rogue_legacy_initial_metrics_refresh_is_guarded() -> None:
    rogue = _module()
    region = next(
        item for item in rogue._REGIONS
        if item.name == "VirtualScreen.UpdateVirtualSize"
    )

    assert region.span == 1
    assert len(region.changes) == 1
    change = region.changes[0]
    assert change.original == b"\x16"  # ldc.i4.0
    assert change.patched == b"\x17"   # ldc.i4.1
    assert region.before and region.after
