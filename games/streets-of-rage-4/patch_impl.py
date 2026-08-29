"""Guarded Streets of Rage 4 Xamarin/MonoGame 4:3 patch.

Only replacements for user-supplied APK entries are emitted.  APK rebuilding,
optional APKVision cleanup, alignment, signing, and final archive verification
remain the responsibility of the shared framework.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lz4.block


STORE_ENTRY = "lib/arm64-v8a/libassemblies.arm64-v8a.blob.so"
ASSEMBLY_NAME = "SOR4.dll"
BIGFILE_ENTRY = "assets/bigfile"

VIDEO_ENTRIES = (
    "assets/videos/game_intro.mp4",
    "assets/videos/game_intro_logos.mp4",
    "assets/videos/max_boss_intro.mp4",
    "assets/videos/playdigious.mp4",
    "assets/videos/stage10_intro.mp4",
    "assets/videos/stage11_intro.mp4",
    "assets/videos/stage12_intro.mp4",
    "assets/videos/stage1_intro.mp4",
    "assets/videos/stage1_intro_bk.mp4",
    "assets/videos/stage2_intro.mp4",
    "assets/videos/stage3_intro.mp4",
    "assets/videos/stage4_intro.mp4",
    "assets/videos/stage5_intro.mp4",
    "assets/videos/stage6_intro.mp4",
    "assets/videos/stage7_intro.mp4",
    "assets/videos/stage8_intro.mp4",
    "assets/videos/stage9_intro.mp4",
)

REQUIRED_ENTRIES = (STORE_ENTRY, BIGFILE_ENTRY, *VIDEO_ENTRIES)
PREFERRED_ENTRIES: tuple[str, ...] = ()

_ORIGINAL_ASSEMBLY_SHA256 = (
    "45b06ce7e8f51ef7c21cb35c45597d8ac868dde9ee091819a25810830d4a7205"
)
_PATCHED_ASSEMBLY_SHA256 = (
    "b6b304e9151b55d23a2a6da51fcb11553bb9f38f50c6d16a728b34e9963f336d"
)
_XABA_MAGIC = 0x41424158
_XABA_VERSION = 0x80010002
_XALZ_MAGIC = b"XALZ"
_STORE_HEADER = struct.Struct("<5I")
_STORE_DESCRIPTOR = struct.Struct("<7I")
_XALZ_HEADER = struct.Struct("<4sII")


class PatchError(RuntimeError):
    """The input does not contain the exact audited patch targets."""


@dataclass(frozen=True)
class _BinaryPatch:
    name: str
    offset: int
    original: bytes
    replacement: bytes


@dataclass(frozen=True)
class _BigfilePatch:
    name: str
    asset_path: str
    original: bytes
    replacement: bytes
    root_transform: bool = False


def _change(name: str, offset: int, original: str, replacement: str) -> _BinaryPatch:
    before = bytes.fromhex(original)
    after = bytes.fromhex(replacement)
    if len(before) != len(after):  # pragma: no cover - module authoring invariant
        raise ValueError(f"{name}: in-place patch length changed")
    return _BinaryPatch(name, offset, before, after)


# Every offset below is constrained by a canonical fingerprint of the complete
# decompressed SOR4.dll. The optional cleanup range is excluded from that
# fingerprint so an independently cleaned source cannot prevent the display
# patch from being applied. All display ranges retain exact before/after guards.
_OPTIONAL_CLEANUP_PATCHES = (
    # Cleanup: suppress only the isolated FirebaseAnalytics.LogEvent call made
    # when More Games is opened. Keep FirebaseApp/provider initialization,
    # Remote Config, the More Games WebView, billing, cloud, Play Games, EOS,
    # and support intact. Four stack-producing instructions are replaced by
    # equal-length nops, so the following WebView body executes unchanged.
    _change(
        "more-games-analytics-event",
        0x9B358,
        "28 d0 00 00 06 72 22 3b 01 70 14 6f 61 09 00 0a",
        "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00",
    ),
)

_DISPLAY_PATCHES = (
    # 1920x1080 default GUI canvas -> 1920x1440.
    _change("gui-default-height", 0x2364, "22 00 00 87 44", "22 00 00 b4 44"),
    # Perspective calculations which spell 16:9 as 16 / 9.  Replacing 16 with
    # 12 yields 4:3 while the increased vertical FOV retains horizontal view.
    _change("gui-child-camera-ratio", 0x1D7E8, "22 00 00 80 41", "22 00 00 40 41"),
    _change("game-grid-ratio-float", 0x50FD4, "22 00 00 80 41", "22 00 00 40 41"),
    _change("game-grid-ratio-fix", 0x5103F, "1f 10", "1f 0c"),
    _change("hud-camera-ratio", 0x51FF5, "22 00 00 80 41", "22 00 00 40 41"),
    _change("camera-width-ratio-float", 0x7095, "22 00 00 80 41", "22 00 00 40 41"),
    _change("camera-width-ratio-fix", 0x70A4, "1f 10", "1f 0c"),
    # Default camera/culling height 10.8 -> 14.4 (14 + 4/10).  Together with
    # the 4:3 width helpers this preserves the old 19.2-unit horizontal view.
    _change(
        "decor-camera-height",
        0x4D618,
        "1f 0a 1e 6a 1f 0a 6a",
        "1f 0e 1a 6a 1f 0a 6a",
    ),
    _change(
        "camera-default-height",
        0x56A98,
        "1f 0a 1e 6a 1f 0a 6a",
        "1f 0e 1a 6a 1f 0a 6a",
    ),
    # 45-degree vertical FOV -> 57.8224016 degrees in radians.  This is Vert+:
    # tan(new/2) = tan(old/2) * (16/9) / (4/3).
    _change("camera-vertical-fov", 0x56AF1, "22 db 0f 49 3f", "22 2e 2d 81 3f"),
    # Direct 16:9 renderer/currentRenderRect constants -> 4:3.
    _change("gui-child-render-aspect", 0x1D904, "22 39 8e e3 3f", "22 ab aa aa 3f"),
    _change("preloading-render-aspect", 0x405AB, "22 39 8e e3 3f", "22 ab aa aa 3f"),
    _change("main-target-setup-aspect", 0x50C88, "22 39 8e e3 3f", "22 ab aa aa 3f"),
    _change("main-target-draw-aspect", 0x50E19, "22 39 8e e3 3f", "22 ab aa aa 3f"),
    _change("game-begin-aspect", 0x50ED3, "22 39 8e e3 3f", "22 ab aa aa 3f"),
    _change("game-end-aspect", 0x52B6A, "22 39 8e e3 3f", "22 ab aa aa 3f"),
    _change("window-render-aspect", 0xA1090, "22 39 8e e3 3f", "22 ab aa aa 3f"),
    _change("target-render-aspect", 0xA10C4, "22 39 8e e3 3f", "22 ab aa aa 3f"),
    # The mobile compositor invokes this GUI both on the cleared backbuffer and
    # while building the HUD render target.  Its bottom_filler.xnb is the blue
    # comic panel seen over the lower quarter of menus/gameplay on a 4:3 device.
    # Keep every packaged asset and Content.Load path intact; suppress only the
    # two exact draw calls.  The already-patched 4:3 game/HUD targets then show
    # through instead of being covered by source artwork.
    _change(
        "mobile-border-filler-backbuffer-draw",
        0x32B0B,
        "28 d5 05 00 06",
        "00 00 00 00 00",
    ),
    _change(
        "mobile-border-filler-hud-draw",
        0x52BB6,
        "28 d5 05 00 06",
        "00 00 00 00 00",
    ),
)

_MANAGED_PATCHES = _OPTIONAL_CLEANUP_PATCHES + _DISPLAY_PATCHES


def _bigfile_change(
    name: str,
    asset_path: str,
    original: str,
    replacement: str,
    *,
    root_transform: bool = False,
) -> _BigfilePatch:
    before = bytes.fromhex(original)
    after = bytes.fromhex(replacement)
    if len(before) != len(after):  # pragma: no cover - module authoring invariant
        raise ValueError(f"{name}: in-place bigfile patch length changed")
    return _BigfilePatch(name, asset_path, before, after, root_transform)


def _bigfile_root_height(name: str, asset_path: str) -> _BigfilePatch:
    return _bigfile_change(
        name,
        asset_path,
        "0a 0a 0d 00 00 f0 44 15 00 00 87 44",
        "0a 0a 0d 00 00 f0 44 15 00 00 b4 44",
        root_transform=True,
    )


# The mobile title and main-menu screens are composed from protobuf-net GUI
# roots stored in a raw-DEFLATE bigfile. Their Android render surface is already
# full-screen, but two background nodes retain a 1920x1080 transform and
# therefore cover only the upper 720 pixels of a 1280x960 display. Scale only
# the non-interactive backgrounds by 4/3 and move them left by 320 logical
# pixels. The 1920x1080 art becomes 2560x1440 and is center-cropped to the
# 1920x1440 canvas.
#
# The Back/Select legend is shared by desktop and mobile main-menu subtrees.
# Its parent remained at y=540 on the new 1440-high canvas, leaving the legend
# at the old widescreen bottom. Move that parent to y=900 while retaining the
# child layout and touch targets.
_BIGFILE_PATCHES = (
    _bigfile_change(
        "title-screen-background-center-crop",
        "gui/menus/gui_title_screen",
        """
        12 47 3a 18 0a 12 0a 10
        67 75 69 2f 74 69 74 6c 65 5f 73 63 72 65 65 6e
        10 00 18 00
        0a 0a 0d 00 00 00 00 15 00 00 00 00
        1d 00 00 80 3f
        2a 0c 08 ff 01 10 ff 01 18 ff 01 20 ff 01
        52 0a 0d 00 00 00 00 15 00 00 00 00 58 00
        """,
        """
        12 47 3a 18 0a 12 0a 10
        67 75 69 2f 74 69 74 6c 65 5f 73 63 72 65 65 6e
        10 00 18 00
        0a 0a 0d 00 00 a0 c3 15 00 00 00 00
        1d ab aa aa 3f
        2a 0c 08 ff 01 10 ff 01 18 ff 01 20 ff 01
        52 0a 0d 00 00 00 00 15 00 00 00 00 58 00
        """,
    ),
    _bigfile_change(
        "main-menu-background-center-crop",
        "gui/menus/main_menu_background",
        """
        0a 0a 0d 00 00 00 00 15 00 00 00 00
        1d 00 00 80 3f
        2a 0c 08 ff 01 10 ff 01 18 ff 01 20 ff 01
        4a 19 aa 01 16 0a 14 0d 00 00 00 00 15 00 00 00 00
        1d 00 00 96 46 25 00 00 87 44
        52 0a 0d 00 00 00 00 15 00 00 00 00 58 00
        """,
        """
        0a 0a 0d 00 00 a0 c3 15 00 00 00 00
        1d ab aa aa 3f
        2a 0c 08 ff 01 10 ff 01 18 ff 01 20 ff 01
        4a 19 aa 01 16 0a 14 0d 00 00 00 00 15 00 00 00 00
        1d 00 00 96 46 25 00 00 87 44
        52 0a 0d 00 00 00 00 15 00 00 00 00 58 00
        """,
    ),
    _bigfile_change(
        "main-menu-button-legend-bottom",
        "gui/menus/gui_main_sub",
        """
        0a 0a 0d 00 00 70 44 15 00 00 07 44
        12 08 63 6f 6e 74 72 6f 6c 73
        1d 00 00 80 3f
        2a 0c 08 ff 01 10 ff 01 18 ff 01 20 ff 01
        4a 0a ea 01 07 10 5e 10 c1 01 18 01
        52 0a 0d 00 00 00 00 15 00 00 00 00 58 00
        """,
        """
        0a 0a 0d 00 00 70 44 15 00 00 61 44
        12 08 63 6f 6e 74 72 6f 6c 73
        1d 00 00 80 3f
        2a 0c 08 ff 01 10 ff 01 18 ff 01 20 ff 01
        4a 0a ea 01 07 10 5e 10 c1 01 18 01
        52 0a 0d 00 00 00 00 15 00 00 00 00 58 00
        """,
    ),
    _bigfile_change(
        "mobile-main-menu-button-legend-bottom",
        "gui/menus/mobile/gui_main_sub",
        """
        0a 0a 0d 00 00 70 44 15 00 00 07 44
        12 08 63 6f 6e 74 72 6f 6c 73
        1d 00 00 80 3f
        2a 0c 08 ff 01 10 ff 01 18 ff 01 20 ff 01
        4a 0a ea 01 07 10 5e 10 c1 01 18 01
        52 0a 0d 00 00 00 00 15 00 00 00 00 58 00
        """,
        """
        0a 0a 0d 00 00 70 44 15 00 00 61 44
        12 08 63 6f 6e 74 72 6f 6c 73
        1d 00 00 80 3f
        2a 0c 08 ff 01 10 ff 01 18 ff 01 20 ff 01
        4a 0a ea 01 07 10 5e 10 c1 01 18 01
        52 0a 0d 00 00 00 00 15 00 00 00 00 58 00
        """,
    ),
    # These named pre-game records retained a 1920x1080 outer root even after
    # the renderer moved to 1920x1440. Change only that outer transform; nested
    # templates, artwork, animations, and the gameplay HUD remain untouched.
    _bigfile_root_height("title-screen-root-height", "gui/menus/gui_title_screen"),
    _bigfile_root_height(
        "main-menu-background-root-height", "gui/menus/main_menu_background"
    ),
    _bigfile_root_height(
        "main-menu-screen-root-height", "gui/menus/gui_main_menu_screen"
    ),
    _bigfile_root_height(
        "mobile-main-menu-screen-root-height",
        "gui/menus/mobile/gui_main_menu_screen",
    ),
    _bigfile_root_height("main-menu-sub-root-height", "gui/menus/gui_main_sub"),
    _bigfile_root_height(
        "mobile-main-menu-sub-root-height", "gui/menus/mobile/gui_main_sub"
    ),
    _bigfile_root_height(
        "arcade-difficulty-root-height", "gui/menus/gui_main_arcade_difficulty"
    ),
    _bigfile_root_height(
        "mobile-arcade-difficulty-root-height",
        "gui/menus/mobile/gui_main_arcade_difficulty",
    ),
    _bigfile_root_height(
        "new-game-difficulty-root-height", "gui/menus/popup_newgame_difficulty"
    ),
    _bigfile_root_height(
        "mobile-new-game-difficulty-root-height",
        "gui/menus/mobile/popup_newgame_difficulty",
    ),
    _bigfile_root_height(
        "character-select-root-height", "gui/menus/gui_menu_character_select"
    ),
    _bigfile_root_height(
        "mobile-character-select-root-height",
        "gui/menus/mobile/gui_menu_character_select",
    ),
    _bigfile_root_height(
        "player-select-root-height", "gui/gui_player_select_screen"
    ),
    _bigfile_root_height("story-root-height", "gui/menus/gui_story"),
    _bigfile_root_height("mobile-story-root-height", "gui/menus/mobile/gui_story"),
    _bigfile_root_height("cutscene-skip-root-height", "gui/gui_cutscene_skip"),
    _bigfile_root_height("loading-screen-root-height", "gui/gui_loading_screen"),
    _bigfile_root_height("loading-overlay-root-height", "gui/gui_loading_overlay"),
)

_BIGFILE_MAX_RAW_SIZE = 256 * 1024 * 1024


@dataclass(frozen=True)
class _StoreEntry:
    index: int
    name: str
    descriptor_offset: int
    mapping_index: int
    data_offset: int
    data_size: int
    debug_offset: int
    debug_size: int
    config_offset: int
    config_size: int


@dataclass(frozen=True)
class _BigfileEntry:
    asset_type: str
    asset_path: str
    payload_offset: int
    payload_size: int


class _XamarinStore:
    """Minimal, strict reader/writer for this MonoVM XABA v2 store."""

    def __init__(self, wrapper: bytes):
        self.wrapper = bytes(wrapper)
        if len(wrapper) < 0x4000 or wrapper[:6] != b"\x7fELF\x02\x01":
            raise PatchError("assembly store wrapper is not a little-endian ELF64 image")
        if struct.unpack_from("<H", wrapper, 18)[0] != 183:
            raise PatchError("assembly store wrapper is not AArch64")

        locations: list[int] = []
        cursor = 0
        magic = struct.pack("<I", _XABA_MAGIC)
        while True:
            cursor = wrapper.find(magic, cursor)
            if cursor < 0:
                break
            locations.append(cursor)
            cursor += 1
        if len(locations) != 1 or locations[0] % 0x4000:
            raise PatchError("assembly store payload is absent, duplicated, or not 16K aligned")
        self.payload_offset = locations[0]

        if self.payload_offset + _STORE_HEADER.size > len(wrapper):
            raise PatchError("truncated XABA header")
        magic_value, version, count, index_count, index_size = _STORE_HEADER.unpack_from(
            wrapper, self.payload_offset
        )
        if magic_value != _XABA_MAGIC or version != _XABA_VERSION:
            raise PatchError(f"unsupported XABA store version: 0x{version:08x}")
        if not 0 < count <= 4096 or index_count != count * 2:
            raise PatchError("invalid XABA assembly/index counts")
        if index_size != index_count * 12:
            raise PatchError("unexpected AArch64 XABA v2 index layout")

        descriptors_offset = self.payload_offset + _STORE_HEADER.size + index_size
        names_offset = descriptors_offset + count * _STORE_DESCRIPTOR.size
        if names_offset > len(wrapper):
            raise PatchError("truncated XABA descriptor table")

        rows: list[tuple[int, ...]] = []
        for index in range(count):
            offset = descriptors_offset + index * _STORE_DESCRIPTOR.size
            rows.append(_STORE_DESCRIPTOR.unpack_from(wrapper, offset))

        data_offsets = [value for row in rows for value in (row[1], row[3], row[5]) if value]
        if not data_offsets:
            raise PatchError("XABA store contains no assembly data")
        first_data = self.payload_offset + min(data_offsets)

        names: list[str] = []
        cursor = names_offset
        for _index in range(count):
            if cursor + 4 > first_data:
                raise PatchError("truncated XABA assembly-name table")
            length = struct.unpack_from("<I", wrapper, cursor)[0]
            cursor += 4
            if not length or length > 1024 or cursor + length > first_data:
                raise PatchError("invalid XABA assembly name")
            try:
                name = wrapper[cursor : cursor + length].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise PatchError("invalid UTF-8 in XABA assembly name") from exc
            cursor += length
            names.append(name)
        if len(set(names)) != len(names):
            raise PatchError("duplicate XABA assembly names")

        entries: dict[str, _StoreEntry] = {}
        for index, (name, row) in enumerate(zip(names, rows)):
            mapping, data_off, data_size, debug_off, debug_size, config_off, config_size = row
            for relative, size in (
                (data_off, data_size),
                (debug_off, debug_size),
                (config_off, config_size),
            ):
                if bool(relative) != bool(size):
                    raise PatchError(f"{name}: inconsistent XABA offset/size pair")
                if relative and self.payload_offset + relative + size > len(wrapper):
                    raise PatchError(f"{name}: XABA data range exceeds wrapper")
            entries[name] = _StoreEntry(
                index,
                name,
                descriptors_offset + index * _STORE_DESCRIPTOR.size,
                mapping,
                data_off,
                data_size,
                debug_off,
                debug_size,
                config_off,
                config_size,
            )
        self.entries = entries

    def assembly(self, name: str) -> bytes:
        entry = self.entries.get(name)
        if entry is None:
            raise PatchError(f"XABA store is missing {name}")
        start = self.payload_offset + entry.data_offset
        block = self.wrapper[start : start + entry.data_size]
        if len(block) < _XALZ_HEADER.size:
            raise PatchError(f"{name}: truncated XALZ block")
        magic, descriptor_index, raw_size = _XALZ_HEADER.unpack_from(block)
        if magic != _XALZ_MAGIC or descriptor_index != entry.index or not raw_size:
            raise PatchError(f"{name}: unsupported XALZ header")
        try:
            raw = lz4.block.decompress(
                block[_XALZ_HEADER.size :], uncompressed_size=raw_size
            )
        except (ValueError, lz4.block.LZ4BlockError) as exc:
            raise PatchError(f"{name}: invalid XALZ payload") from exc
        if len(raw) != raw_size:
            raise PatchError(f"{name}: XALZ decompressed-size mismatch")
        return raw

    def replace(self, name: str, replacement: bytes) -> bytes:
        entry = self.entries.get(name)
        if entry is None:
            raise PatchError(f"XABA store is missing {name}")
        original = self.assembly(name)
        if len(replacement) != len(original):
            raise PatchError(f"{name}: managed image size changed")

        compressed = lz4.block.compress(
            replacement,
            mode="high_compression",
            compression=12,
            store_size=False,
        )
        block = _XALZ_HEADER.pack(_XALZ_MAGIC, entry.index, len(replacement)) + compressed
        if len(block) > entry.data_size:
            raise PatchError(
                f"{name}: recompressed XALZ block grew beyond its {entry.data_size}-byte slot"
            )

        result = bytearray(self.wrapper)
        start = self.payload_offset + entry.data_offset
        result[start : start + entry.data_size] = block + b"\0" * (
            entry.data_size - len(block)
        )
        # data_size is the compressed XALZ block length; offsets are absolute
        # within the store, so the following assembly need not move.
        struct.pack_into("<I", result, entry.descriptor_offset + 8, len(block))

        verified = _XamarinStore(bytes(result)).assembly(name)
        if verified != replacement:
            raise PatchError(f"{name}: replacement store verification failed")
        return bytes(result)


def _read_7bit_int(data: bytes, cursor: int, limit: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 35, 7):
        if cursor >= limit:
            raise PatchError("truncated bigfile string length")
        octet = data[cursor]
        cursor += 1
        value |= (octet & 0x7F) << shift
        if not octet & 0x80:
            if value > 0x7FFFFFFF:
                raise PatchError("bigfile string length exceeds Int32")
            return value, cursor
    raise PatchError("invalid bigfile string length")


def _read_bigfile_string(data: bytes, cursor: int, limit: int) -> tuple[str, int]:
    size, cursor = _read_7bit_int(data, cursor, limit)
    if size > 0x10000 or size % 2 or cursor + size > limit:
        raise PatchError("invalid bigfile UTF-16 string")
    try:
        value = data[cursor : cursor + size].decode("utf-16le")
    except UnicodeDecodeError as exc:
        raise PatchError("invalid bigfile UTF-16 string") from exc
    return value, cursor + size


def _parse_bigfile_raw(data: bytes) -> tuple[_BigfileEntry, ...]:
    if len(data) < 4:
        raise PatchError("truncated SOR4 bigfile")
    count = struct.unpack_from("<i", data)[0]
    if not 0 < count <= 100_000:
        raise PatchError("invalid SOR4 bigfile asset count")

    entries: list[_BigfileEntry] = []
    cursor = 4
    for _index in range(count):
        asset_type, cursor = _read_bigfile_string(data, cursor, len(data))
        asset_path, cursor = _read_bigfile_string(data, cursor, len(data))
        if not asset_type or not asset_path or cursor + 4 > len(data):
            raise PatchError("invalid SOR4 bigfile asset header")
        payload_size = struct.unpack_from("<i", data, cursor)[0]
        cursor += 4
        if payload_size < 0 or cursor + payload_size > len(data):
            raise PatchError("invalid SOR4 bigfile asset payload")
        entries.append(
            _BigfileEntry(asset_type, asset_path, cursor, payload_size)
        )
        cursor += payload_size
    if cursor != len(data):
        raise PatchError("unexpected trailing bytes in SOR4 bigfile")
    return tuple(entries)


def _decompress_bigfile(data: bytes) -> bytes:
    try:
        decoder = zlib.decompressobj(wbits=-15)
        raw = decoder.decompress(data, _BIGFILE_MAX_RAW_SIZE + 1)
        if len(raw) > _BIGFILE_MAX_RAW_SIZE or decoder.unconsumed_tail:
            raise PatchError("SOR4 bigfile decompressed size exceeds limit")
        raw += decoder.flush()
    except zlib.error as exc:
        raise PatchError("invalid raw-DEFLATE SOR4 bigfile") from exc
    if len(raw) > _BIGFILE_MAX_RAW_SIZE:
        raise PatchError("SOR4 bigfile decompressed size exceeds limit")
    if not decoder.eof or decoder.unused_data:
        raise PatchError("truncated or concatenated SOR4 bigfile stream")
    _parse_bigfile_raw(raw)
    return raw


def _compress_bigfile(data: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    return compressor.compress(data) + compressor.flush()


def _bigfile_patch_locations(
    raw: bytes,
) -> tuple[str, tuple[tuple[_BigfilePatch, str, int], ...]]:
    entries = _parse_bigfile_raw(raw)
    locations: list[tuple[_BigfilePatch, str, int]] = []
    states: list[str] = []
    for patch in _BIGFILE_PATCHES:
        candidates = [
            item
            for item in entries
            if item.asset_type == "GuiNodeData" and item.asset_path == patch.asset_path
        ]
        if len(candidates) != 1:
            return "unsupported", ()
        entry = candidates[0]
        payload = raw[
            entry.payload_offset : entry.payload_offset + entry.payload_size
        ]
        if patch.root_transform:
            if not payload or payload[0] != 0x32:
                return "unsupported", ()
            outer_size, local_offset = _read_7bit_int(payload, 1, len(payload))
            if (
                outer_size < len(patch.original)
                or local_offset + outer_size > len(payload)
            ):
                return "unsupported", ()
            actual = payload[local_offset : local_offset + len(patch.original)]
            if actual == patch.original:
                state = "original"
            elif actual == patch.replacement:
                state = "patched"
            else:
                return "unsupported", ()
        else:
            original_count = payload.count(patch.original)
            patched_count = payload.count(patch.replacement)
            if (original_count, patched_count) == (1, 0):
                state = "original"
                local_offset = payload.find(patch.original)
            elif (original_count, patched_count) == (0, 1):
                state = "patched"
                local_offset = payload.find(patch.replacement)
            else:
                return "unsupported", ()
        states.append(state)
        locations.append((patch, state, entry.payload_offset + local_offset))
    if len(set(states)) == 1:
        return states[0], tuple(locations)
    return "mixed", tuple(locations)


def _bigfile_raw_state(raw: bytes) -> tuple[str, str]:
    # Do not gate on a whole-bigfile digest: source variants may add or change
    # unrelated records. Strict parsing, unique named records, and the exact
    # before/after protobuf contexts above are the compatibility boundary.
    digest = _sha256(raw)
    layout, _locations = _bigfile_patch_locations(raw)
    if layout == "unsupported":
        return "unsupported", digest
    if layout == "patched":
        return "patched", digest
    # Complete a recognized original/mixed source on the next apply pass.
    return "original", digest


def _bigfile_state(data: bytes) -> tuple[str, str]:
    try:
        raw = _decompress_bigfile(data)
    except PatchError:
        return "unsupported", _sha256(data)
    return _bigfile_raw_state(raw)


def _rewrite_bigfile(data: bytes) -> bytes:
    raw = _decompress_bigfile(data)
    state, digest = _bigfile_raw_state(raw)
    if state == "unsupported":
        raise PatchError(f"assets/bigfile is not the audited image ({digest})")

    result = bytearray(raw)
    layout, locations = _bigfile_patch_locations(raw)
    if layout == "unsupported":  # pragma: no cover - covered by state guard
        raise PatchError("bigfile GUI targets changed during patching")
    for patch, patch_state, offset in locations:
        if patch_state == "original":
            result[offset : offset + len(patch.original)] = patch.replacement

    result_bytes = bytes(result)
    if _bigfile_patch_locations(result_bytes)[0] != "patched":
        raise PatchError("bigfile GUI patch layout verification failed")

    compressed = _compress_bigfile(result_bytes)
    if _decompress_bigfile(compressed) != result_bytes:
        raise PatchError("bigfile recompression verification failed")
    if _bigfile_state(compressed)[0] != "patched":
        raise PatchError("bigfile patched-state verification failed")
    return compressed


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _patch_layout_state(data: bytes) -> str:
    states: list[str] = []
    for patch in _DISPLAY_PATCHES:
        actual = data[patch.offset : patch.offset + len(patch.original)]
        if actual == patch.original:
            states.append("original")
        elif actual == patch.replacement:
            states.append("patched")
        else:
            return "unsupported"
    if len(set(states)) == 1:
        return states[0]
    return "mixed"


def _optional_cleanup_state(data: bytes) -> str:
    states: list[str] = []
    for patch in _OPTIONAL_CLEANUP_PATCHES:
        actual = data[patch.offset : patch.offset + len(patch.original)]
        if actual == patch.original:
            states.append("original")
        elif actual == patch.replacement:
            states.append("patched")
        else:
            states.append("modified")
    if len(set(states)) == 1:
        return states[0]
    return "mixed"


def _canonical_managed_digest(data: bytes) -> str | None:
    """Fingerprint the audited image while normalizing recognized edit slots."""

    if _patch_layout_state(data) == "unsupported":
        return None
    canonical = bytearray(data)
    for patch in _DISPLAY_PATCHES:
        actual = bytes(canonical[patch.offset : patch.offset + len(patch.original)])
        if actual not in (patch.original, patch.replacement):
            return None
        canonical[patch.offset : patch.offset + len(patch.original)] = patch.original
    # Cleanup is deliberately non-gating. Normalize its fixed-size range even
    # when another cleanup tool has produced bytes we do not recognize.
    for patch in _OPTIONAL_CLEANUP_PATCHES:
        if patch.offset + len(patch.original) > len(canonical):
            return None
        canonical[patch.offset : patch.offset + len(patch.original)] = patch.original
    return _sha256(bytes(canonical))


def _managed_state(data: bytes) -> tuple[str, str]:
    digest = _sha256(data)
    layout = _patch_layout_state(data)
    canonical_digest = _canonical_managed_digest(data)
    if canonical_digest != _ORIGINAL_ASSEMBLY_SHA256:
        return "unsupported", digest
    if layout == "patched":
        return "patched", digest
    # A recognized mixture is an interrupted/independent patch, not an
    # unsupported binary. Treat it as work remaining so apply() completes it.
    return "original", digest


def _rewrite_managed_layout(data: bytes) -> bytes:
    state, digest = _managed_state(data)
    if state == "unsupported":
        raise PatchError(f"SOR4.dll is not the audited managed image ({digest})")
    result = bytearray(data)
    for patch in _DISPLAY_PATCHES:
        actual = bytes(result[patch.offset : patch.offset + len(patch.original)])
        if actual == patch.original:
            result[patch.offset : patch.offset + len(patch.original)] = patch.replacement
        elif actual != patch.replacement:
            raise PatchError(f"{patch.name}: source bytes changed during patching")
    for patch in _OPTIONAL_CLEANUP_PATCHES:
        actual = bytes(result[patch.offset : patch.offset + len(patch.original)])
        if actual == patch.original:
            result[patch.offset : patch.offset + len(patch.original)] = patch.replacement
        # A third-party cleanup at this optional range is preserved verbatim.
    if _patch_layout_state(result) != "patched":
        raise PatchError("managed patch layout verification failed")
    if _canonical_managed_digest(bytes(result)) != _ORIGINAL_ASSEMBLY_SHA256:
        raise PatchError("managed image changed outside audited patch ranges")
    return bytes(result)


def _patch_managed(data: bytes) -> bytes:
    state, digest = _managed_state(data)
    if state == "unsupported":
        raise PatchError(f"SOR4.dll is not the audited managed image ({digest})")
    result = _rewrite_managed_layout(data)
    if (
        _optional_cleanup_state(result) == "patched"
        and _sha256(result) != _PATCHED_ASSEMBLY_SHA256
    ):
        raise PatchError("SOR4.dll patched fingerprint mismatch")
    if _managed_state(result)[0] != "patched":
        raise PatchError("SOR4.dll patched state verification failed")
    return result


@dataclass(frozen=True)
class _VideoInfo:
    codec: str
    width: int
    height: int
    sample_aspect_ratio: str
    frame_rate: str
    frames: int | None
    duration: float | None
    audio: tuple[tuple[str, str, int], ...]


def _media_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise PatchError(
            f"{name} is required for the Streets of Rage 4 intro-video patch"
        )
    return path


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _probe_video(path: Path) -> _VideoInfo:
    command = [
        _media_tool("ffprobe"),
        "-v",
        "error",
        "-show_entries",
        (
            "stream=codec_type,codec_name,width,height,sample_aspect_ratio,"
            "avg_frame_rate,nb_frames,duration,sample_rate,channels:format=duration"
        ),
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip().splitlines()
        raise PatchError(
            f"{path.name}: ffprobe failed: {detail[-1] if detail else 'unknown error'}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PatchError(f"{path.name}: ffprobe returned invalid JSON") from exc
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list):
        raise PatchError(f"{path.name}: ffprobe returned no stream list")
    video = [item for item in streams if item.get("codec_type") == "video"]
    if len(video) != 1:
        raise PatchError(f"{path.name}: expected exactly one video stream")
    stream = video[0]
    audio = tuple(
        (
            str(item.get("codec_name") or ""),
            str(item.get("sample_rate") or ""),
            int(item.get("channels") or 0),
        )
        for item in streams
        if item.get("codec_type") == "audio"
    )
    duration = _optional_float(stream.get("duration"))
    if duration is None and isinstance(payload.get("format"), dict):
        duration = _optional_float(payload["format"].get("duration"))
    return _VideoInfo(
        codec=str(stream.get("codec_name") or ""),
        width=int(stream.get("width") or 0),
        height=int(stream.get("height") or 0),
        sample_aspect_ratio=str(stream.get("sample_aspect_ratio") or "1:1"),
        frame_rate=str(stream.get("avg_frame_rate") or ""),
        frames=_optional_int(stream.get("nb_frames")),
        duration=duration,
        audio=audio,
    )


def _video_state(info: _VideoInfo) -> str:
    if info.codec != "h264" or info.sample_aspect_ratio not in ("1:1", "N/A"):
        return "unsupported"
    if (info.width, info.height) == (1280, 720):
        return "original"
    if (info.width, info.height) == (960, 720):
        return "patched"
    return "unsupported"


def _video_command(source: Path, output: Path, executable: str | None = None) -> list[str]:
    """Return the deterministic, center-crop encoding command."""

    return [
        executable or _media_tool("ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-vf",
        "crop=960:720:160:0,setsar=1",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-threads:v",
        "1",
        "-x264-params",
        "threads=1:lookahead_threads=1:sliced_threads=0:sync-lookahead=0",
        "-fps_mode",
        "passthrough",
        "-c:a",
        "copy",
        "-fflags",
        "+bitexact",
        "-flags:v",
        "+bitexact",
        "-movflags",
        "+faststart",
        str(output),
    ]


def _frame_seconds(rate: str) -> float:
    try:
        numerator, denominator = rate.split("/", 1)
        fps = float(numerator) / float(denominator)
        return 1.0 / fps if fps > 0 else 0.05
    except (ValueError, ZeroDivisionError):
        return 0.05


def _patch_video(source: Path, output: Path) -> None:
    original = _probe_video(source)
    if _video_state(original) != "original":
        raise PatchError(f"{source.name}: video is not the audited 1280x720 source shape")
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        _video_command(source, output),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode:
        output.unlink(missing_ok=True)
        detail = completed.stderr.strip().splitlines()
        raise PatchError(
            f"{source.name}: ffmpeg crop failed: {detail[-1] if detail else 'unknown error'}"
        )

    patched = _probe_video(output)
    tolerance = max(0.05, _frame_seconds(original.frame_rate))
    timing_ok = (
        original.frame_rate == patched.frame_rate
        and (
            original.frames is None
            or patched.frames is None
            or original.frames == patched.frames
        )
        and (
            original.duration is None
            or patched.duration is None
            or abs(original.duration - patched.duration) <= tolerance
        )
    )
    if (
        _video_state(patched) != "patched"
        or not timing_ok
        or original.audio != patched.audio
    ):
        output.unlink(missing_ok=True)
        raise PatchError(f"{source.name}: cropped-video verification failed")


def _normal_entries(extracted: dict[str, Path]) -> dict[str, tuple[str, Path]]:
    return {
        name.replace("\\", "/").lower(): (name.replace("\\", "/"), Path(path))
        for name, path in extracted.items()
    }


def _entry(
    extracted: dict[str, Path], wanted: str
) -> tuple[str, Path] | None:
    return _normal_entries(extracted).get(wanted.lower())


def _replacement_path(output_dir: Path, entry: str) -> Path:
    path = Path(output_dir).joinpath(*entry.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _analyse(extracted: dict[str, Path]) -> tuple[dict[str, Any], dict[str, str]]:
    states: dict[str, str] = {}
    targets: list[dict[str, Any]] = []
    details: list[str] = []

    store_item = _entry(extracted, STORE_ENTRY)
    if store_item is None:
        store_state = "unsupported"
        details.append(f"missing {STORE_ENTRY}")
    else:
        try:
            store = _XamarinStore(store_item[1].read_bytes())
            managed = store.assembly(ASSEMBLY_NAME)
            store_state, digest = _managed_state(managed)
            if store_state == "unsupported":
                details.append(f"unrecognized SOR4.dll fingerprint {digest}")
        except (OSError, PatchError, struct.error) as exc:
            store_state = "unsupported"
            details.append(str(exc))
    states[STORE_ENTRY] = store_state
    targets.append(
        {
            "name": "managed-4x3-and-cleanup",
            "entry": STORE_ENTRY,
            "state": store_state,
            "matches": 1 if store_state != "unsupported" else 0,
        }
    )

    bigfile_item = _entry(extracted, BIGFILE_ENTRY)
    if bigfile_item is None:
        bigfile_state = "unsupported"
        details.append(f"missing {BIGFILE_ENTRY}")
    else:
        try:
            bigfile_state, digest = _bigfile_state(bigfile_item[1].read_bytes())
            if bigfile_state == "unsupported":
                details.append(
                    f"{BIGFILE_ENTRY}: unrecognized menu GUI targets ({digest})"
                )
        except OSError as exc:
            bigfile_state = "unsupported"
            details.append(str(exc))
    states[BIGFILE_ENTRY] = bigfile_state
    targets.append(
        {
            "name": "title-and-main-menu-background-center-crop",
            "entry": BIGFILE_ENTRY,
            "state": bigfile_state,
            "matches": 1 if bigfile_state != "unsupported" else 0,
        }
    )

    for video_entry in VIDEO_ENTRIES:
        item = _entry(extracted, video_entry)
        if item is None:
            state = "unsupported"
            details.append(f"missing {video_entry}")
        else:
            try:
                state = _video_state(_probe_video(item[1]))
                if state == "unsupported":
                    details.append(f"{video_entry}: expected H.264 1280x720 or 960x720")
            except (OSError, PatchError) as exc:
                state = "unsupported"
                details.append(str(exc))
        states[video_entry] = state
        targets.append(
            {
                "name": "intro-video-center-crop",
                "entry": video_entry,
                "state": state,
                "matches": 1 if state != "unsupported" else 0,
            }
        )

    values = list(states.values())
    if "unsupported" in values:
        overall = "unsupported"
    elif all(value == "patched" for value in values):
        overall = "patched"
    else:
        overall = "original"
    report: dict[str, Any] = {"state": overall, "targets": targets}
    if details:
        report["detail"] = "; ".join(details[:4])
    return report, states


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Classify every audited managed, serialized-GUI, and video target."""

    report, _states = _analyse(extracted)
    return report


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Emit replacements for every recognized original-state target."""

    report, states = _analyse(extracted)
    if report["state"] not in ("original", "patched"):
        raise PatchError(
            "Streets of Rage 4 targets are unsupported: "
            + str(report.get("detail") or "required target mismatch")
        )

    replacements: dict[str, Path] = {}
    store_item = _entry(extracted, STORE_ENTRY)
    if states[STORE_ENTRY] == "original" and store_item is not None:
        store = _XamarinStore(store_item[1].read_bytes())
        patched_managed = _patch_managed(store.assembly(ASSEMBLY_NAME))
        patched_wrapper = store.replace(ASSEMBLY_NAME, patched_managed)
        destination = _replacement_path(Path(output_dir), store_item[0])
        destination.write_bytes(patched_wrapper)
        if _managed_state(_XamarinStore(patched_wrapper).assembly(ASSEMBLY_NAME))[0] != "patched":
            raise PatchError("managed-store post-patch verification failed")
        replacements[store_item[0]] = destination

    bigfile_item = _entry(extracted, BIGFILE_ENTRY)
    if states[BIGFILE_ENTRY] == "original" and bigfile_item is not None:
        patched_bigfile = _rewrite_bigfile(bigfile_item[1].read_bytes())
        destination = _replacement_path(Path(output_dir), bigfile_item[0])
        destination.write_bytes(patched_bigfile)
        if _bigfile_state(patched_bigfile)[0] != "patched":
            raise PatchError("bigfile post-patch verification failed")
        replacements[bigfile_item[0]] = destination

    for video_entry in VIDEO_ENTRIES:
        item = _entry(extracted, video_entry)
        if states[video_entry] != "original" or item is None:
            continue
        destination = _replacement_path(Path(output_dir), item[0])
        _patch_video(item[1], destination)
        replacements[item[0]] = destination

    return replacements
