"""Proprietary-free tests for STALKER: Call of Pripyat's 4:3 patch."""

from __future__ import annotations

import math
import struct
from pathlib import Path

import pytest

from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _module():
    registry = Registry(REPO_ROOT / "games")
    return registry.module(registry.by_id["stalker-call-of-pripyat"])


def _synthetic_elf(module, spec, *, duplicate: bool = False) -> bytes:
    data = bytearray(0x1000)
    data[:4] = b"\x7fELF"
    data[4] = spec.elf_class
    data[5] = 1
    struct.pack_into("<H", data, 16, 3)
    struct.pack_into("<H", data, 18, spec.machine)
    if spec.elf_class == 2:
        struct.pack_into("<Q", data, 32, 0x40)
        struct.pack_into("<H", data, 52, 64)
        struct.pack_into("<H", data, 54, 56)
        struct.pack_into("<H", data, 56, 1)
        struct.pack_into(
            "<IIQQQQQQ",
            data,
            0x40,
            1,
            5,
            0,
            0,
            0,
            len(data),
            len(data),
            0x1000,
        )
    else:
        struct.pack_into("<I", data, 28, 0x34)
        struct.pack_into("<H", data, 40, 52)
        struct.pack_into("<H", data, 42, 32)
        struct.pack_into("<H", data, 44, 1)
        struct.pack_into(
            "<IIIIIIII",
            data,
            0x34,
            1,
            0,
            0,
            0,
            len(data),
            len(data),
            5,
            0x1000,
        )

    def install(offset: int) -> None:
        region = spec.region
        data[offset : offset + len(region.before)] = region.before
        base = offset + len(region.before)
        data[base + region.span : base + region.span + len(region.after)] = region.after
        for relative, expected in region.landmarks:
            data[base + relative : base + relative + len(expected)] = expected
        for change in region.changes:
            start = base + change.relative
            data[start : start + len(change.original)] = change.original

    install(0x300)
    if duplicate:
        install(0x600)
    return bytes(data)


@pytest.mark.parametrize("spec_index", [0, 1])
def test_stalker_synthetic_native_probe_patch_and_postcondition(
    tmp_path: Path, spec_index: int
) -> None:
    stalker = _module()
    spec = stalker._NATIVE_SPECS[spec_index]
    original = _synthetic_elf(stalker, spec)
    targets, actions = stalker._discover_native(original, spec)

    assert stalker._overall(targets) == "original"
    assert len(actions) == 6

    source = tmp_path / f"{spec.abi}-original.so"
    destination = tmp_path / f"{spec.abi}-patched.so"
    source.write_bytes(original)
    assert stalker._patch_native(source, destination, spec) is True
    patched_targets, _ = stalker._discover_native(destination.read_bytes(), spec)
    assert stalker._overall(patched_targets) == "patched"


def test_stalker_rejects_ambiguous_native_method_region() -> None:
    stalker = _module()
    spec = stalker._NATIVE_SPECS[0]

    targets, actions = stalker._discover_native(
        _synthetic_elf(stalker, spec, duplicate=True), spec
    )

    assert stalker._overall(targets) == "ambiguous"
    assert actions == []


def _canvas_raw(spec) -> bytearray:
    raw = bytearray(80)
    struct.pack_into("<i", raw, 0x20, 1)
    struct.pack_into("<f", raw, 0x24, 100.0)
    struct.pack_into("<f", raw, 0x28, 1.0)
    struct.pack_into("<ff", raw, 0x2C, spec.width, spec.original_height)
    struct.pack_into("<i", raw, 0x34, spec.screen_match_mode)
    struct.pack_into("<f", raw, 0x38, spec.match)
    return raw


def test_stalker_canvas_scaler_guards_original_patched_and_unknown() -> None:
    stalker = _module()
    spec = stalker._CANVAS_SPECS[0]
    raw = _canvas_raw(spec)

    assert stalker._canvas_state(raw, spec) == "original"
    struct.pack_into("<f", raw, 0x30, spec.patched_height)
    assert stalker._canvas_state(raw, spec) == "patched"
    struct.pack_into("<i", raw, 0x34, 99)
    assert stalker._canvas_state(raw, spec) == "unsupported"


def test_stalker_settings_font_sizes_are_scaled_and_idempotently_classified() -> None:
    stalker = _module()
    raw = bytearray(stalker._TEXT_FONT_SIZE_OFFSET + 4)

    expected = {11: 19, 12: 21, 14: 24, 15: 26}
    assert stalker._SETTINGS_FONT_SIZES == expected
    for original, patched in expected.items():
        struct.pack_into("<i", raw, stalker._TEXT_FONT_SIZE_OFFSET, original)
        state, value = stalker._settings_font_state(raw)
        assert value == original
        assert state == ("ambiguous" if original == 15 else "original")

        struct.pack_into("<i", raw, stalker._TEXT_FONT_SIZE_OFFSET, patched)
        state, value = stalker._settings_font_state(raw)
        assert value == patched
        assert state == ("ambiguous" if patched == 19 else "patched")

    for legacy in (16, 20):
        struct.pack_into("<i", raw, stalker._TEXT_FONT_SIZE_OFFSET, legacy)
        assert stalker._settings_font_state(raw) == ("original", legacy)

    struct.pack_into("<i", raw, stalker._TEXT_FONT_SIZE_OFFSET, 99)
    assert stalker._settings_font_state(raw) == ("unsupported", 99)


def test_stalker_dropdown_labels_are_length_preserving_and_idempotent() -> None:
    stalker = _module()
    spec = stalker._DROPDOWN_SPECS[1]
    raw = bytearray(b"invented\0DropVideoQuality\0")
    for original, _patched in spec.options:
        raw.extend(stalker._option_record(original))

    targets, actions = stalker._dropdown_states(bytes(raw), spec)
    assert stalker._overall(targets) == "original"
    assert len(actions) == 3
    for offset, original, patched in actions:
        assert len(original) == len(patched)
        assert raw[offset : offset + len(original)] == original
        raw[offset : offset + len(original)] = patched

    patched_targets, _ = stalker._dropdown_states(bytes(raw), spec)
    assert stalker._overall(patched_targets) == "patched"


def test_stalker_dropdown_rejects_wrong_callback() -> None:
    stalker = _module()
    spec = stalker._DROPDOWN_SPECS[0]
    raw = b"WrongCallback" + b"".join(
        stalker._option_record(original) for original, _patched in spec.options
    )

    targets, actions = stalker._dropdown_states(raw, spec)

    assert stalker._overall(targets) == "unsupported"
    assert actions == []


class _FakeRawReader:
    def __init__(self, data: bytes):
        self.source = data
        self.data: bytes | None = None

    def get_raw_data(self) -> bytes:
        # Match UnityPy: this continues to expose the source stream after a
        # staged set_raw_data call.
        return self.source

    def set_raw_data(self, data: bytes) -> None:
        self.data = data


class _FakeBundle:
    def __init__(self):
        self.saved = False

    def save(self, *, packer: str) -> bytes:
        assert packer == "original"
        self.saved = True
        return b"invented UnityFS output"


def test_stalker_unity_raw_changes_are_batched_per_reader(
    tmp_path: Path, monkeypatch
) -> None:
    stalker = _module()
    reader = _FakeRawReader(b"OLD1--OLD2")
    bundle = _FakeBundle()
    actions = [
        {
            "kind": "raw",
            "reader": reader,
            "offset": 0,
            "original": b"OLD1",
            "patched": b"NEW1",
            "state": "original",
            "name": "invented first option",
        },
        {
            "kind": "raw",
            "reader": reader,
            "offset": 6,
            "original": b"OLD2",
            "patched": b"NEW2",
            "state": "original",
            "name": "invented second option",
        },
    ]
    monkeypatch.setattr(stalker, "_load_bundle", lambda _path: (object(), bundle))
    monkeypatch.setattr(
        stalker,
        "_discover_unity",
        lambda _bundle: ([{"name": "invented", "state": "original"}], actions),
    )

    destination = tmp_path / "patched.bundle"
    assert stalker._patch_unity(tmp_path / "source.bundle", destination) is True

    assert reader.data == b"NEW1--NEW2"
    assert destination.read_bytes() == b"invented UnityFS output"
    assert bundle.saved is True


def test_stalker_field_of_view_preserves_original_horizontal_view() -> None:
    stalker = _module()
    original_horizontal = 2.0 * math.atan(
        math.tan(math.radians(60.0) / 2.0) * 2.0
    )
    patched_horizontal = 2.0 * math.atan(
        math.tan(math.radians(stalker._FOV_4X3) / 2.0) * (4.0 / 3.0)
    )

    assert math.isclose(original_horizontal, patched_horizontal, abs_tol=1e-6)
    assert math.isclose(stalker._FOV_4X3, 81.786789, abs_tol=1e-5)
    assert stalker._FOV_4X3 > 60.0


def test_stalker_optional_cleanup_never_blocks_core_state() -> None:
    stalker = _module()
    core = [{"name": "core", "state": "patched"}]
    assert stalker._overall(core + [{"name": "VK absent", "state": "absent", "optional": True}]) == "patched"
    assert stalker._overall(core + [{"name": "VK changed", "state": "unrecognized", "optional": True}]) == "patched"
    assert stalker._overall(
        [{"name": "core", "state": "unsupported"}, {"name": "VK", "state": "patched", "optional": True}]
    ) == "unsupported"


def test_stalker_probe_report_ignores_optional_artifact_variants(
    tmp_path: Path, monkeypatch
) -> None:
    stalker = _module()
    lib = tmp_path / "libil2cpp.so"
    lib.write_bytes(_synthetic_elf(stalker, stalker._NATIVE_SPECS[0]))
    data = tmp_path / "data.unity3d"
    data.write_bytes(b"synthetic unity payload")

    core_targets = [
        {"name": "Unity core", "state": "original", "entry": stalker.DATA_ENTRY},
    ]

    monkeypatch.setattr(stalker, "_discover_native", lambda _data, _spec: ([], []))
    monkeypatch.setattr(stalker, "_unity_targets", lambda _path: core_targets + [
        {"name": "VK absent", "state": "absent", "optional": True},
        {"name": "intro video", "state": "ambiguous", "optional": True},
    ])

    present = stalker.probe({stalker.DATA_ENTRY: data, stalker.ARM64_ENTRY: lib})
    monkeypatch.setattr(stalker, "_unity_targets", lambda _path: core_targets + [])
    missing = stalker.probe({stalker.DATA_ENTRY: data, stalker.ARM64_ENTRY: lib})
    monkeypatch.setattr(stalker, "_unity_targets", lambda _path: core_targets + [
        {"name": "VK", "state": "unrecognized", "optional": True},
        {"name": "intro video", "state": "absent", "optional": True},
        {"name": "VK 2", "state": "patched", "optional": True},
    ])
    unfamiliar = stalker.probe({stalker.DATA_ENTRY: data, stalker.ARM64_ENTRY: lib})

    assert present["state"] == missing["state"] == unfamiliar["state"] == "original"
    assert present["targets"] == missing["targets"] == unfamiliar["targets"] == core_targets
    assert not any(target.get("optional", False) for target in present["targets"])


def test_stalker_production_specs_cover_both_abis_and_all_three_tiers() -> None:
    stalker = _module()

    assert tuple(spec.abi for spec in stalker._NATIVE_SPECS) == (
        "arm64-v8a",
        "armeabi-v7a",
    )
    assert stalker.REQUIRED_ENTRIES == (stalker.DATA_ENTRY,)
    for spec in stalker._NATIVE_SPECS:
        assert len(spec.region.changes) == 6
        assert spec.region.before and spec.region.after and spec.region.landmarks
        for change in spec.region.changes:
            assert len(change.original) == len(change.patched) == 4
            assert change.original != change.patched
    assert len(stalker._CAMERA_SPECS) == 3
    assert len(stalker._CANVAS_SPECS) == 3
    assert tuple(spec.tested_count for spec in stalker._SETTINGS_TEXT_SPECS) == (68, 70)
    assert len(stalker._VK_SPECS) == 2


@pytest.mark.parametrize("present_index", [0, 1])
def test_stalker_probe_accepts_each_audited_abi_independently(
    tmp_path: Path, monkeypatch, present_index: int
) -> None:
    stalker = _module()
    monkeypatch.setattr(
        stalker, "_unity_targets", lambda _path: [{"name": "Unity core", "state": "patched"}]
    )
    data = tmp_path / "data.unity3d"
    data.write_bytes(b"synthetic")
    spec = stalker._NATIVE_SPECS[present_index]
    library = tmp_path / f"{spec.abi}.so"
    library.write_bytes(_synthetic_elf(stalker, spec))
    extracted = {stalker.DATA_ENTRY: data, spec.entry: library}

    result = stalker.probe(extracted)
    assert result["state"] == "original"
    assert not any(target.get("reason", "").startswith("neither") for target in result["targets"])


def test_stalker_probe_rejects_present_unrecognized_abi(tmp_path: Path, monkeypatch) -> None:
    stalker = _module()
    monkeypatch.setattr(
        stalker, "_unity_targets", lambda _path: [{"name": "Unity core", "state": "patched"}]
    )
    data = tmp_path / "data.unity3d"
    data.write_bytes(b"synthetic")
    bad = tmp_path / "bad.so"
    bad.write_bytes(b"not an audited ELF")
    result = stalker.probe({stalker.DATA_ENTRY: data, stalker.ARM64_ENTRY: bad})
    assert result["state"] == "unsupported"
