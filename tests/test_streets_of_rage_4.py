from __future__ import annotations

import hashlib
import math
import shutil
import struct
import subprocess
from pathlib import Path

import lz4.block
import pytest

from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _module():
    registry = Registry(REPO_ROOT / "games")
    return registry.module(registry.by_id["streets-of-rage-4"])


def _managed_fixture(module) -> bytes:
    size = max(item.offset + len(item.original) for item in module._MANAGED_PATCHES)
    data = bytearray(b"\xa5" * size)
    for item in module._MANAGED_PATCHES:
        data[item.offset : item.offset + len(item.original)] = item.original
    return bytes(data)


def _randomish(size: int) -> bytes:
    blocks = []
    counter = 0
    while sum(map(len, blocks)) < size:
        blocks.append(hashlib.sha256(counter.to_bytes(4, "little")).digest())
        counter += 1
    return b"".join(blocks)[:size]


def _synthetic_store(module, name: str, raw: bytes) -> bytes:
    prefix = bytearray(0x4000)
    prefix[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", prefix, 18, 183)  # EM_AARCH64

    encoded_name = name.encode("utf-8")
    index = b"\0" * 24
    data_offset = 20 + len(index) + 28 + 4 + len(encoded_name)
    compressed = lz4.block.compress(
        raw, mode="high_compression", compression=12, store_size=False
    )
    block = module._XALZ_HEADER.pack(module._XALZ_MAGIC, 0, len(raw)) + compressed
    header = module._STORE_HEADER.pack(
        module._XABA_MAGIC,
        module._XABA_VERSION,
        1,
        2,
        len(index),
    )
    descriptor = module._STORE_DESCRIPTOR.pack(
        0, data_offset, len(block), 0, 0, 0, 0
    )
    names = struct.pack("<I", len(encoded_name)) + encoded_name
    return bytes(prefix) + header + index + descriptor + names + block


def _seven_bit_int(value: int) -> bytes:
    result = bytearray()
    while value >= 0x80:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def _bigfile_string(value: str) -> bytes:
    encoded = value.encode("utf-16le")
    return _seven_bit_int(len(encoded)) + encoded


def _bigfile_record(asset_type: str, asset_path: str, payload: bytes) -> bytes:
    return (
        _bigfile_string(asset_type)
        + _bigfile_string(asset_path)
        + struct.pack("<i", len(payload))
        + payload
    )


def _synthetic_bigfile_raw(module, states: tuple[str, ...]) -> bytes:
    assert len(states) == len(module._BIGFILE_PATCHES)
    records = [("OtherData", "unrelated/asset", b"preserve-me")]
    grouped: dict[str, list[tuple[object, str]]] = {}
    for patch, state in zip(module._BIGFILE_PATCHES, states):
        grouped.setdefault(patch.asset_path, []).append((patch, state))
    for asset_path, items in grouped.items():
        root = next((item for item in items if item[0].root_transform), None)
        body = bytearray()
        if root is not None:
            patch, state = root
            body += patch.original if state == "original" else patch.replacement
        for patch, state in items:
            if patch.root_transform:
                continue
            target = patch.original if state == "original" else patch.replacement
            body += b"prefix" + target + b"suffix"
        if root is not None:
            payload = b"\x32" + _seven_bit_int(len(body)) + bytes(body)
        else:
            payload = bytes(body)
        records.append(("GuiNodeData", asset_path, payload))
    result = bytearray(struct.pack("<i", len(records)))
    for asset_type, asset_path, payload in records:
        result += _bigfile_record(asset_type, asset_path, payload)
    return bytes(result)


def test_sor4_managed_patch_layout_is_guarded_and_resumable(monkeypatch) -> None:
    module = _module()
    original = _managed_fixture(module)
    monkeypatch.setattr(module, "_ORIGINAL_ASSEMBLY_SHA256", module._sha256(original))

    assert module._patch_layout_state(original) == "original"
    patched = module._rewrite_managed_layout(original)
    assert module._patch_layout_state(patched) == "patched"
    assert module._managed_state(patched)[0] == "patched"
    assert original != patched

    by_name = {item.name: item for item in module._MANAGED_PATCHES}
    assert patched[by_name["camera-vertical-fov"].offset :][:5] == bytes.fromhex(
        "22 2e 2d 81 3f"
    )
    cleanup = by_name["more-games-analytics-event"]
    assert patched[cleanup.offset : cleanup.offset + len(cleanup.replacement)] == (
        cleanup.replacement
    )
    assert tuple(item.name for item in module._OPTIONAL_CLEANUP_PATCHES) == (
        "more-games-analytics-event",
    )

    mixed = bytearray(original)
    first = module._DISPLAY_PATCHES[0]
    mixed[first.offset : first.offset + len(first.replacement)] = first.replacement
    assert module._patch_layout_state(mixed) == "mixed"
    assert module._managed_state(bytes(mixed))[0] == "original"
    completed = module._rewrite_managed_layout(bytes(mixed))
    assert module._patch_layout_state(completed) == "patched"


def test_sor4_optional_cleanup_is_non_gating_and_preserved(monkeypatch) -> None:
    module = _module()
    original = _managed_fixture(module)
    monkeypatch.setattr(module, "_ORIGINAL_ASSEMBLY_SHA256", module._sha256(original))
    cleanup = module._OPTIONAL_CLEANUP_PATCHES[0]

    independently_cleaned = bytearray(original)
    independently_cleaned[
        cleanup.offset : cleanup.offset + len(cleanup.original)
    ] = b"\xcc" * len(cleanup.original)
    assert module._optional_cleanup_state(independently_cleaned) == "modified"
    assert module._managed_state(bytes(independently_cleaned))[0] == "original"

    patched = module._rewrite_managed_layout(bytes(independently_cleaned))
    assert module._patch_layout_state(patched) == "patched"
    assert patched[cleanup.offset : cleanup.offset + len(cleanup.original)] == (
        b"\xcc" * len(cleanup.original)
    )


def test_sor4_unrecognized_display_bytes_fail_closed(monkeypatch) -> None:
    module = _module()
    original = _managed_fixture(module)
    monkeypatch.setattr(module, "_ORIGINAL_ASSEMBLY_SHA256", module._sha256(original))
    target = module._DISPLAY_PATCHES[0]
    changed = bytearray(original)
    changed[target.offset : target.offset + len(target.original)] = b"\xcc" * len(
        target.original
    )

    assert module._patch_layout_state(changed) == "unsupported"
    assert module._managed_state(bytes(changed))[0] == "unsupported"
    with pytest.raises(module.PatchError, match="audited managed image"):
        module._rewrite_managed_layout(bytes(changed))


def test_sor4_camera_constants_are_vert_plus_not_horizontal_crop() -> None:
    module = _module()
    by_name = {item.name: item for item in module._MANAGED_PATCHES}
    fov = by_name["camera-vertical-fov"]
    old_fov = struct.unpack("<f", fov.original[1:])[0]
    new_fov = struct.unpack("<f", fov.replacement[1:])[0]

    old_horizontal_tangent = math.tan(old_fov / 2.0) * (16.0 / 9.0)
    new_horizontal_tangent = math.tan(new_fov / 2.0) * (4.0 / 3.0)
    assert new_horizontal_tangent == pytest.approx(old_horizontal_tangent, rel=1e-6)
    assert 14.4 * (4.0 / 3.0) == pytest.approx(10.8 * (16.0 / 9.0))


def test_sor4_mobile_border_fillers_are_suppressed_at_both_draw_sites() -> None:
    module = _module()
    by_name = {item.name: item for item in module._DISPLAY_PATCHES}

    backbuffer = by_name["mobile-border-filler-backbuffer-draw"]
    hud = by_name["mobile-border-filler-hud-draw"]
    assert (backbuffer.offset, hud.offset) == (0x32B0B, 0x52BB6)
    assert backbuffer.original == hud.original == bytes.fromhex("28 d5 05 00 06")
    assert backbuffer.replacement == hud.replacement == b"\0" * 5
    # Filler XNBs remain packaged and loadable; only these no-argument draw
    # calls are removed from the 4:3 managed presentation path.
    assert not any("filler" in entry.lower() for entry in module.REQUIRED_ENTRIES)


def test_sor4_pre_filler_first_pass_is_resumable(monkeypatch) -> None:
    module = _module()
    original = _managed_fixture(module)
    monkeypatch.setattr(module, "_ORIGINAL_ASSEMBLY_SHA256", module._sha256(original))

    first_pass = bytearray(original)
    for patch in module._MANAGED_PATCHES:
        if not patch.name.startswith("mobile-border-filler-"):
            first_pass[patch.offset : patch.offset + len(patch.replacement)] = (
                patch.replacement
            )

    assert module._patch_layout_state(first_pass) == "mixed"
    assert module._managed_state(bytes(first_pass))[0] == "original"
    completed = module._rewrite_managed_layout(bytes(first_pass))
    assert module._patch_layout_state(completed) == "patched"


def test_sor4_bigfile_center_crops_backgrounds_and_moves_button_legend() -> None:
    module = _module()
    title, main, desktop_legend, mobile_legend = module._BIGFILE_PATCHES[:4]

    assert title.asset_path == "gui/menus/gui_title_screen"
    assert main.asset_path == "gui/menus/main_menu_background"
    assert struct.unpack("<f", title.original[31:35])[0] == 0.0
    assert struct.unpack("<f", title.replacement[31:35])[0] == -320.0
    assert struct.unpack("<f", title.original[41:45])[0] == 1.0
    assert struct.unpack("<f", title.replacement[41:45])[0] == pytest.approx(4 / 3)
    assert struct.unpack("<f", main.original[3:7])[0] == 0.0
    assert struct.unpack("<f", main.replacement[3:7])[0] == -320.0
    assert struct.unpack("<f", main.original[13:17])[0] == 1.0
    assert struct.unpack("<f", main.replacement[13:17])[0] == pytest.approx(4 / 3)
    assert desktop_legend.asset_path == "gui/menus/gui_main_sub"
    assert mobile_legend.asset_path == "gui/menus/mobile/gui_main_sub"
    for legend in (desktop_legend, mobile_legend):
        assert struct.unpack("<f", legend.original[8:12])[0] == 540.0
        assert struct.unpack("<f", legend.replacement[8:12])[0] == 900.0
        assert legend.original[:8] == legend.replacement[:8]
        assert legend.original[12:] == legend.replacement[12:]

    root_patches = [item for item in module._BIGFILE_PATCHES if item.root_transform]
    assert len(root_patches) == 18
    assert {item.asset_path for item in root_patches} >= {
        "gui/menus/gui_title_screen",
        "gui/menus/gui_menu_character_select",
        "gui/menus/gui_story",
        "gui/gui_cutscene_skip",
        "gui/gui_loading_screen",
    }
    for item in root_patches:
        assert struct.unpack("<f", item.original[8:12])[0] == 1080.0
        assert struct.unpack("<f", item.replacement[8:12])[0] == 1440.0


def test_sor4_bigfile_patch_round_trips_and_preserves_every_other_byte() -> None:
    module = _module()
    original_raw = _synthetic_bigfile_raw(
        module, tuple("original" for _ in module._BIGFILE_PATCHES)
    )
    compressed = module._compress_bigfile(original_raw)

    assert module._bigfile_patch_locations(original_raw)[0] == "original"
    assert module._bigfile_state(compressed)[0] == "original"
    patched = module._rewrite_bigfile(compressed)
    patched_raw = module._decompress_bigfile(patched)

    expected = bytearray(original_raw)
    layout, locations = module._bigfile_patch_locations(original_raw)
    assert layout == "original"
    for item, state, offset in locations:
        assert state == "original"
        expected[offset : offset + len(item.original)] = item.replacement
    assert patched_raw == bytes(expected)
    assert len(patched_raw) == len(original_raw)
    assert module._bigfile_patch_locations(patched_raw)[0] == "patched"
    assert module._bigfile_state(patched)[0] == "patched"


def test_sor4_bigfile_mixed_state_is_resumable_and_detection_is_loose() -> None:
    module = _module()
    mixed_raw = bytearray(
        _synthetic_bigfile_raw(
            module,
            ("patched", *("original" for _ in module._BIGFILE_PATCHES[1:])),
        )
    )
    unrelated = mixed_raw.index(b"preserve-me")
    mixed_raw[unrelated : unrelated + len(b"preserve-me")] = b"keep-this!!"
    mixed = module._compress_bigfile(bytes(mixed_raw))

    assert module._bigfile_patch_locations(bytes(mixed_raw))[0] == "mixed"
    assert module._bigfile_state(mixed)[0] == "original"
    completed = module._decompress_bigfile(module._rewrite_bigfile(mixed))
    assert module._bigfile_patch_locations(completed)[0] == "patched"
    assert b"keep-this!!" in completed


def test_sor4_bigfile_unrecognized_or_duplicate_target_fails_closed() -> None:
    module = _module()
    all_original = tuple("original" for _ in module._BIGFILE_PATCHES)
    raw = bytearray(_synthetic_bigfile_raw(module, all_original))
    target = module._BIGFILE_PATCHES[0]
    offset = raw.index(target.original)
    raw[offset + 31 : offset + 35] = struct.pack("<f", -123.0)
    compressed = module._compress_bigfile(bytes(raw))

    assert module._bigfile_patch_locations(bytes(raw))[0] == "unsupported"
    assert module._bigfile_state(compressed)[0] == "unsupported"
    with pytest.raises(module.PatchError, match="not the audited image"):
        module._rewrite_bigfile(compressed)

    duplicate = bytearray(_synthetic_bigfile_raw(module, all_original))
    struct.pack_into("<i", duplicate, 0, struct.unpack_from("<i", duplicate)[0] + 1)
    duplicate += _bigfile_record(
        "GuiNodeData", target.asset_path, b"duplicate" + target.original
    )
    assert module._bigfile_patch_locations(bytes(duplicate))[0] == "unsupported"

    invalid_root = bytearray(_synthetic_bigfile_raw(module, all_original))
    root_path = next(
        item.asset_path for item in module._BIGFILE_PATCHES if item.root_transform
    )
    root_entry = next(
        item
        for item in module._parse_bigfile_raw(bytes(invalid_root))
        if item.asset_type == "GuiNodeData" and item.asset_path == root_path
    )
    assert invalid_root[root_entry.payload_offset] == 0x32
    invalid_root[root_entry.payload_offset + 1] = 0
    assert module._bigfile_patch_locations(bytes(invalid_root))[0] == "unsupported"


def test_xamarin_xalz_store_replacement_round_trips_without_moving_entries() -> None:
    module = _module()
    original = _randomish(4096)
    replacement = b"\0" * len(original)
    wrapper = _synthetic_store(module, "Fixture.dll", original)
    store = module._XamarinStore(wrapper)

    assert store.assembly("Fixture.dll") == original
    replaced = store.replace("Fixture.dll", replacement)

    assert len(replaced) == len(wrapper)
    assert module._XamarinStore(replaced).assembly("Fixture.dll") == replacement
    old_size = store.entries["Fixture.dll"].data_size
    new_size = module._XamarinStore(replaced).entries["Fixture.dll"].data_size
    assert new_size < old_size


def test_xamarin_xalz_store_refuses_a_replacement_that_exceeds_its_slot() -> None:
    module = _module()
    original = b"\0" * 4096
    replacement = _randomish(len(original))
    store = module._XamarinStore(_synthetic_store(module, "Fixture.dll", original))

    with pytest.raises(module.PatchError, match="grew beyond"):
        store.replace("Fixture.dll", replacement)


def test_sor4_video_states_and_recipe_use_a_proportional_center_crop() -> None:
    module = _module()
    common = dict(
        codec="h264",
        height=720,
        sample_aspect_ratio="1:1",
        frame_rate="30/1",
        frames=30,
        duration=1.0,
        audio=(("aac", "48000", 2),),
    )
    assert module._video_state(module._VideoInfo(width=1280, **common)) == "original"
    assert module._video_state(module._VideoInfo(width=960, **common)) == "patched"
    assert module._video_state(module._VideoInfo(width=1024, **common)) == "unsupported"

    command = module._video_command(Path("source.mp4"), Path("output.mp4"), "ffmpeg")
    assert "crop=960:720:160:0,setsar=1" in command
    assert command[command.index("-c:a") + 1] == "copy"
    assert command[command.index("-threads:v") + 1] == "1"
    assert command[command.index("-map_metadata") + 1] == "-1"


def _ffmpeg_with_x264() -> bool:
    executable = shutil.which("ffmpeg")
    if executable is None or shutil.which("ffprobe") is None:
        return False
    completed = subprocess.run(
        [executable, "-hide_banner", "-encoders"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return completed.returncode == 0 and "libx264" in completed.stdout


@pytest.mark.skipif(not _ffmpeg_with_x264(), reason="ffmpeg/libx264 is not available")
def test_sor4_video_transform_is_deterministic_on_a_synthetic_clip(tmp_path: Path) -> None:
    module = _module()
    source = tmp_path / "synthetic-source.mp4"
    first = tmp_path / "synthetic-first.mp4"
    second = tmp_path / "synthetic-second.mp4"
    subprocess.run(
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x204060:s=1280x720:r=2:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=1",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-y",
            str(source),
        ],
        check=True,
    )

    module._patch_video(source, first)
    module._patch_video(source, second)

    assert module._video_state(module._probe_video(first)) == "patched"
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(
        second.read_bytes()
    ).digest()
