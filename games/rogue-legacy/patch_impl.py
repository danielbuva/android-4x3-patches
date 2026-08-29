"""Guarded Rogue Legacy 4:3 patch with optional porter-branding cleanup.

The Android port stores ``RogueLegacy.Android`` in a Xamarin XABA v1 assembly
store.  This module resolves that assembly by name from
``assemblies.manifest``, decodes its XALZ payload, and finds audited IL regions
through invariant neighboring bytecode.  It does not depend on APK hashes,
signatures, or fixed offsets in either the APK or the managed DLL.

The 4:3 transformation keeps the 1320-pixel horizontal view and raises the
virtual height from 720 to 990.  That is expanded-vertical framing: gameplay
and touch conversion share the taller virtual screen, while fixed 16:9 title
art remains proportional instead of being stretched or horizontally cropped.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BLOB_ENTRY = "assemblies/assemblies.blob"
MANIFEST_ENTRY = "assemblies/assemblies.manifest"
REQUIRED_ENTRIES = (BLOB_ENTRY, MANIFEST_ENTRY)

_ASSEMBLY_NAME = "RogueLegacy.Android"
_XABA_MAGIC = 0x41424158
_XABA_VERSION = 1


class PatchError(RuntimeError):
    """The supplied entries do not contain one safely recognizable target."""


@dataclass(frozen=True)
class _Change:
    name: str
    relative: int
    original: bytes
    patched: bytes
    optional: bool = False


@dataclass(frozen=True)
class _Region:
    name: str
    before: bytes
    span: int
    after: bytes
    changes: tuple[_Change, ...]
    landmarks: tuple[tuple[int, bytes], ...] = ()


@dataclass(frozen=True)
class _StringTarget:
    name: str
    token: int
    original: str
    patched: str
    optional: bool = False


def _hx(value: str) -> bytes:
    return bytes.fromhex(value)


def _i4(value: int) -> bytes:
    return b"\x20" + struct.pack("<i", value)


def _r4(value: float) -> bytes:
    return b"\x22" + struct.pack("<f", value)


# A region begins immediately after ``before``.  ``span`` reaches the first
# byte of ``after``.  This permits every mutable instruction to be in an
# original or already-patched state without weakening method identification.
_REGIONS = (
    _Region(
        "RCScreenManager.Initialize",
        _hx("330a00060228ff170006022028050000"),
        0x5,
        _hx("02280a1800066f7101000a73460d0006"),
        (_Change("virtual-screen height", 0, _i4(720), _i4(990)),),
    ),
    # The port normally refreshes EngineEV.ScreenHeight, camera metrics, input
    # conversion, effects, and render targets only when UpdateVirtualSize()
    # reports that it changed the dimensions.  Our constructor patch starts at
    # 1320x990 already, so the first refresh used to return false and leave the
    # old 720-pixel metrics active until a later screen transition.  Return true
    # for that one dirty no-size-change path so the initial screen, touch input,
    # overlays, and menus all receive the 990-pixel metrics immediately.
    _Region(
        "VirtualScreen.UpdateVirtualSize",
        _hx("060228540d0006330b070228560d00063302"),
        0x1,
        _hx("2a020628550d0006"),
        (
            _Change(
                "refresh metrics when the requested size is already active",
                0,
                b"\x16",  # ldc.i4.0
                b"\x17",  # ldc.i4.1
            ),
        ),
    ),
    _Region(
        "BlitWorksSplashScreen.LoadContent",
        _hx("7d7b120004027b7b1200042200002544"),
        0x3B,
        _hx("2200002042027b7b1200046f07160006"),
        (
            _Change("BlitWorks logo center", 0x0, _r4(360), _r4(495)),
            _Change("BlitWorks loading center", 0x36, _r4(360), _r4(495)),
        ),
        (
            (0x0E, _hx("06027b7b120004176f1e1600")),
            (0x1D, _hx("199e017073091700067d7c12")),
        ),
    ),
    _Region(
        "CDGSplashScreen.LoadContent",
        _hx("7d7e120004027b7e1200042200002544"),
        0x99,
        _hx("73ea00000a6ffa150006027b7f120004"),
        (
            _Change("CDG logo center", 0x0, _r4(360), _r4(495)),
            _Change("CDG loading bottom anchor", 0x94, _r4(630), _r4(900)),
        ),
        (
            (0x26, _hx("6f1e160006027e6811000473")),
            (0x4C, _hx("7b7f120004197d9918000402")),
            (0x72, _hx("06027b7f1200041f641f641f")),
        ),
    ),
    _Region(
        "OptionsScreen.OnEnter",
        _hx("188da200000125167222240070a22517"),
        0xEB,
        _hx("0b1201286701000aa228060000062609"),
        (
            _Change("options enter tween center", 0x0, _r4(360), _r4(495)),
            # These are relative slide distances, not screen centers. The
            # previous 495 values left the option rows 135 pixels above their
            # parchment. Clean 360 values already satisfy the corrected state;
            # 495 is accepted only so that earlier patch outputs can upgrade.
            _Change("options list slide distance", 0x9F, _r4(495), _r4(360)),
            # The return tween deliberately travels 135 pixels farther than
            # the initial upward offset. That moves the final option rows with
            # the parchment from the old 360-line center to the new 495-line
            # center without changing this tiny method's fixed-size layout.
            _Change("options return slide distance", 0xE6, _r4(360), _r4(495)),
        ),
        (
            (0x3A, _hx("061e00000673010000062580")),
            (0x75, _hx("c8000000120228d203000a0d")),
            (0xB0, _hx("6f2016000609220000003f7e")),
        ),
    ),
    _Region(
        "OptionsScreen.ExitTransition",
        _hx("0700000626027b931300042200002544"),
        0x122,
        _hx("0d1203286701000aa228060000062608"),
        (
            _Change("options exit container center", 0x0, _r4(360), _r4(495)),
            _Change("options exit slide distance", 0x11D, _r4(-495), _r4(-360)),
        ),
        (
            (0x48, _hx("00000125167222240070a225")),
            (0x91, _hx("240070a225177256240070a2")),
            (0xD9, _hx("5a586b6ff815000608220000")),
        ),
    ),
    _Region(
        "OptionsScreen.ApplyOptionsLayout",
        _hx("92130004066fcc03000a256ff9150006"),
        0x5,
        _hx("596ff81500060617580a06027b921300"),
        (_Change("options layout slide distance", 0, _r4(495), _r4(360)),),
    ),
    # Map and teleporter modes share MapScreen. Expand their alpha-map surface
    # from the old 1220x620 inset to the equivalent 1220x890 inset in the
    # 1320x990 virtual screen. MapObj must also allocate the complete 990-line
    # render target; otherwise its rect-derived fallback is only 956 lines and
    # the final presentation is scaled slightly in the vertical direction.
    _Region(
        "MapObj.InitializeAlphaMap",
        _hx("0f01284d01000a1f105828ec01000a0a"),
        0x5,
        _hx("0f01284e01000a1f105828ec01000a0b"),
        (
            _Change(
                "map and teleporter render-target height", 0, _i4(720), _i4(990)
            ),
        ),
    ),
    _Region(
        "MapScreen..ctor",
        _hx("027b81130004187d99180004027b81130004"),
        0xA,
        _hx("027b811300046ff11500066b"),
        (_Change("map unknown-room label center", 0x5, _r4(360), _r4(495)),),
    ),
    _Region(
        "MapScreen.FindRoomTitlePos",
        _hx("057bc000000a"),
        0x5,
        _hx("5b22000000425a73ea00000a"),
        # This is the 720-pixel world-room grid, not the display height. An
        # earlier patch changed it to 990 and is accepted here only so those
        # outputs can be upgraded back to the correct 1:1 map coordinate.
        (_Change("map title world-grid normalization", 0, _r4(990), _r4(720)),),
    ),
    _Region(
        "MapScreen.LoadContent",
        _hx("13300500bd09000021020011027b78130004"),
        0x162,
        _hx("6ffa15000672529d0070"),
        (
            _Change("map and teleporter surface height", 0x9, _i4(620), _i4(890)),
            _Change("map and teleporter camera center", 0x29, _r4(360), _r4(495)),
            _Change("map legend bottom edge", 0x148, _i4(720), _i4(990)),
        ),
    ),
    _Region(
        "MapScreen.ReinitializeRTs",
        _hx("c6027b78130004"),
        0x13,
        _hx("0228fd1700066f2f040006"),
        (_Change("reinitialized map surface height", 0x9, _i4(620), _i4(890)),),
    ),
    _Region(
        "PauseScreen.LayoutPauseIcons",
        _hx("0500610100002d020011220000a5440a"),
        0x5,
        _hx("0b027ba8130004027ba81300046ff015"),
        (_Change("pause layout height", 0, _r4(720), _r4(990)),),
    ),
    _Region(
        "TitleScreen.InitializePostProcessingResources",
        _hx("0228fd1700066f7101000a2028050000"),
        0x5,
        _hx("161616161773de00000a7da014000402"),
        (_Change("title post-process target height", 0, _i4(720), _i4(990)),),
    ),
    _Region(
        "TitleScreen.LoadContent",
        _hx("7d91140004027b911400042200002544"),
        0xAFD,
        _hx("73ea00000a6ffa150006027bbc140004"),
        (
            _Change("title logo center", 0x0, _r4(360), _r4(495)),
            _Change("title loading bottom anchor", 0x5E, _i4(720), _i4(990)),
            _Change("title decoration bottom anchor A", 0x159, _i4(720), _i4(990)),
            _Change("title menu bottom anchor A", 0x190, _i4(720), _i4(990)),
            _Change("title menu bottom anchor B", 0x1CD, _i4(720), _i4(990)),
            _Change("title decoration bottom anchor B", 0x213, _i4(720), _i4(990)),
            _Change("title copyright bottom anchor", 0x2E4, _i4(720), _i4(990)),
            _Change(
                "title porter-credit bottom anchor",
                0x3C6,
                _i4(720),
                _i4(990),
                optional=True,
            ),
            _Change("title primary-menu center", 0x58E, _r4(560), _r4(695)),
            _Change("title touch-button bottom anchor", 0x697, _i4(720), _i4(990)),
            _Change("title auxiliary-menu center", 0xAF8, _r4(310), _r4(445)),
        ),
        (
            (0x2BF, _hx("9e14000472edf801706f3c17")),
            (0x57E, _hx("7d99180004027b9c14000422")),
            (0x83D, _hx("0006027ba8140004176f1e16")),
        ),
    ),
    _Region(
        "TitleScreen.OnEnter",
        _hx("6f20160006027b911400042200002544"),
        0x2D9,
        _hx("2d211780b0140004027f741100047be3"),
        (
            _Change("title save-selection center", 0x0, _r4(310), _r4(445)),
            _Change("title secondary-selection center", 0xAE, _r4(200), _r4(335)),
            _Change("title achievement-selection center", 0x180, _r4(267), _r4(402)),
            _Change("title camera center", 0x21E, _r4(360), _r4(495)),
            _Change(
                "disable first-run developer promo",
                0x2D4,
                _hx("7eb0140004"),
                _hx("1700000000"),
                optional=True,
            ),
        ),
        (
            (0xB6, _hx("000a6ffa150006027bad1400")),
            (0x16C, _hx("140004176fd7150006027bbc")),
            (0x232, _hx("0472f0960070160a120028e2")),
        ),
    ),
    _Region(
        "TitleScreen.UpdateCopyrightText",
        _hx("6f3c170006027b9e140004220000a041"),
        0x5,
        _hx("027b9e1400046ff1150006591f0a596b"),
        (_Change("dynamic copyright bottom anchor", 0, _i4(720), _i4(990)),),
    ),
    _Region(
        "TitleScreen.Draw",
        _hx("00067e4e1100041ff61ff62078050000"),
        0x5,
        _hx("73f300000a284a01000a027bb6140004"),
        (_Change("title fade coverage height", 0, _i4(800), _i4(1070)),),
    ),
    _Region(
        "OptionsScreen.EnsureTelegramButtonTexture",
        _hx("13300300510000002a020011"),
        0x1,
        _hx("7b8c1300042d150228e81700062c0d02"),
        (
            _Change(
                "disable Telegram texture loader",
                0,
                b"\x02",
                b"\x2a",
                optional=True,
            ),
        ),
    ),
)


_STRING_TARGETS = (
    _StringTarget("title camera tween", 0x7001FAFD, "360", "495"),
    _StringTarget(
        "options porter credit",
        0x7001D2EB,
        "ported by t.me/gene_brawl",
        " " * len("ported by t.me/gene_brawl"),
        optional=True,
    ),
    _StringTarget(
        "Telegram URL",
        0x7001D4C5,
        "https://t.me/gene_brawl",
        " " * len("https://t.me/gene_brawl"),
        optional=True,
    ),
    _StringTarget(
        "Telegram texture name",
        0x7001D53D,
        "Touch/touch_telegram",
        " " * len("Touch/touch_telegram"),
        optional=True,
    ),
    _StringTarget(
        "title porter credit",
        0x7001F94F,
        "port from t.me/gene_brawl",
        " " * len("port from t.me/gene_brawl"),
        optional=True,
    ),
    _StringTarget(
        "developer promo heading",
        0x7001F983,
        "Join The Developer Channel",
        " " * len("Join The Developer Channel"),
        optional=True,
    ),
    _StringTarget(
        "developer promo action",
        0x7001F9B9,
        "Tap this window to open t.me/gene_brawl",
        " " * len("Tap this window to open t.me/gene_brawl"),
        optional=True,
    ),
)


def _find_all(data: bytes | bytearray, needle: bytes):
    start = 0
    while True:
        found = data.find(needle, start)
        if found < 0:
            return
        yield found
        start = found + 1


def _locate_region(data: bytes | bytearray, region: _Region) -> list[int]:
    matches: list[int] = []
    for anchor in _find_all(data, region.before):
        base = anchor + len(region.before)
        if data[base + region.span : base + region.span + len(region.after)] != region.after:
            continue
        if any(
            data[base + relative : base + relative + len(expected)] != expected
            for relative, expected in region.landmarks
        ):
            continue
        matches.append(base)
    return matches


def _value_state(actual: bytes, original: bytes, patched: bytes) -> str:
    if actual == original:
        return "original"
    if actual == patched:
        return "patched"
    return "unsupported"


def _overall(targets: list[dict[str, Any]]) -> str:
    states = {str(target["state"]) for target in targets}
    if "ambiguous" in states:
        return "ambiguous"
    if "unsupported" in states:
        return "unsupported"
    if states == {"patched"}:
        return "patched"
    return "original"


def _rva_to_offset(data: bytes | bytearray, rva: int) -> int:
    if len(data) < 0x40 or bytes(data[:2]) != b"MZ":
        raise PatchError("managed assembly has no DOS/PE header")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data) or bytes(data[pe : pe + 4]) != b"PE\0\0":
        raise PatchError("managed assembly has no PE signature")
    section_count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    section_table = pe + 24 + optional_size
    if section_table + section_count * 40 > len(data):
        raise PatchError("managed assembly section table is truncated")
    for index in range(section_count):
        offset = section_table + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, offset + 8
        )
        extent = max(virtual_size, raw_size)
        if virtual_address <= rva < virtual_address + extent:
            result = raw_offset + rva - virtual_address
            if result > len(data):
                break
            return result
    raise PatchError(f"managed assembly RVA 0x{rva:x} is not file-backed")


def _user_string_heap(data: bytes | bytearray) -> tuple[int, int]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    if magic == 0x10B:
        directory = optional + 96
    elif magic == 0x20B:
        directory = optional + 112
    else:
        raise PatchError("managed assembly has an unsupported PE optional header")
    cli_rva, cli_size = struct.unpack_from("<II", data, directory + 14 * 8)
    if not cli_rva or cli_size < 16:
        raise PatchError("managed assembly has no CLI header")
    cli = _rva_to_offset(data, cli_rva)
    metadata_rva, metadata_size = struct.unpack_from("<II", data, cli + 8)
    metadata = _rva_to_offset(data, metadata_rva)
    if metadata + metadata_size > len(data) or bytes(data[metadata : metadata + 4]) != b"BSJB":
        raise PatchError("managed metadata root is missing or truncated")
    version_size = struct.unpack_from("<I", data, metadata + 12)[0]
    cursor = (metadata + 16 + version_size + 3) & ~3
    if cursor + 4 > metadata + metadata_size:
        raise PatchError("managed metadata stream table is truncated")
    stream_count = struct.unpack_from("<H", data, cursor + 2)[0]
    cursor += 4
    for _ in range(stream_count):
        if cursor + 8 > metadata + metadata_size:
            raise PatchError("managed metadata stream header is truncated")
        relative, size = struct.unpack_from("<II", data, cursor)
        name_start = cursor + 8
        name_end = data.find(b"\0", name_start, min(name_start + 32, len(data)))
        if name_end < 0:
            raise PatchError("managed metadata stream name is malformed")
        try:
            name = bytes(data[name_start:name_end]).decode("ascii")
        except UnicodeDecodeError as exc:
            raise PatchError("managed metadata stream name is not ASCII") from exc
        cursor = (name_end + 4) & ~3
        if name == "#US":
            start = metadata + relative
            if start + size > metadata + metadata_size:
                raise PatchError("#US heap is outside the metadata root")
            return start, size
    raise PatchError("managed assembly has no #US heap")


def _compressed_uint(data: bytes | bytearray, offset: int, limit: int) -> tuple[int, int]:
    if offset >= limit:
        raise PatchError("compressed metadata integer is truncated")
    first = data[offset]
    if first & 0x80 == 0:
        return first, 1
    if first & 0xC0 == 0x80:
        if offset + 2 > limit:
            raise PatchError("compressed metadata integer is truncated")
        return ((first & 0x3F) << 8) | data[offset + 1], 2
    if first & 0xE0 == 0xC0:
        if offset + 4 > limit:
            raise PatchError("compressed metadata integer is truncated")
        return (
            ((first & 0x1F) << 24)
            | (data[offset + 1] << 16)
            | (data[offset + 2] << 8)
            | data[offset + 3],
            4,
        )
    raise PatchError("invalid compressed metadata integer")


def _user_string_record(
    data: bytes | bytearray, heap_start: int, heap_size: int, token: int
) -> tuple[int, bytes, int, str]:
    relative = token & 0x00FFFFFF
    if token >> 24 != 0x70 or relative >= heap_size:
        raise PatchError(f"invalid #US token 0x{token:08x}")
    limit = heap_start + heap_size
    length, prefix = _compressed_uint(data, heap_start + relative, limit)
    payload_start = heap_start + relative + prefix
    payload_end = payload_start + length
    if length < 1 or payload_end > limit or (length - 1) % 2:
        raise PatchError(f"malformed #US record for token 0x{token:08x}")
    payload = bytes(data[payload_start : payload_end - 1])
    try:
        value = payload.decode("utf-16le")
    except UnicodeDecodeError as exc:
        raise PatchError(f"invalid UTF-16 #US record for token 0x{token:08x}") from exc
    return payload_start, payload, data[payload_end - 1], value


def _discover_assembly(
    data: bytes | bytearray,
) -> tuple[list[dict[str, Any]], list[tuple[int, bytes, bytes]]]:
    """Return required 4:3 states plus safe core/optional edit actions.

    Porter branding is source-specific. Its absence, duplication, or an
    unfamiliar value is deliberately a silent no-op and cannot affect the
    returned compatibility state.
    """

    targets: list[dict[str, Any]] = []
    actions: list[tuple[int, bytes, bytes]] = []

    for region in _REGIONS:
        matches = _locate_region(data, region)
        if len(matches) != 1:
            if any(not change.optional for change in region.changes):
                targets.append(
                    {
                        "name": region.name,
                        "state": "ambiguous" if len(matches) > 1 else "unsupported",
                        "matches": len(matches),
                    }
                )
            continue
        base = matches[0]
        for change in region.changes:
            offset = base + change.relative
            actual = bytes(data[offset : offset + len(change.original)])
            state = _value_state(actual, change.original, change.patched)
            if not change.optional:
                targets.append(
                    {
                        "name": change.name,
                        "method": region.name,
                        "state": state,
                        "matches": 1,
                    }
                )
            if state in ("original", "patched"):
                actions.append((offset, change.original, change.patched))

    try:
        heap_start, heap_size = _user_string_heap(data)
    except Exception as exc:
        if any(not target.optional for target in _STRING_TARGETS):
            targets.append(
                {"name": "managed #US heap", "state": "unsupported", "reason": str(exc)}
            )
    else:
        for target in _STRING_TARGETS:
            try:
                offset, payload, _kind, _value = _user_string_record(
                    data, heap_start, heap_size, target.token
                )
            except Exception as exc:
                if not target.optional:
                    targets.append(
                        {
                            "name": target.name,
                            "state": "unsupported",
                            "reason": str(exc),
                        }
                    )
                continue
            original = target.original.encode("utf-16le")
            patched = target.patched.encode("utf-16le")
            if len(original) != len(patched) or len(payload) != len(original):
                state = "unsupported"
            else:
                state = _value_state(payload, original, patched)
            if not target.optional:
                targets.append(
                    {
                        "name": target.name,
                        "state": state,
                        "token": f"0x{target.token:08x}",
                    }
                )
            if state in ("original", "patched"):
                actions.append((offset, original, patched))

    return targets, actions


def _manifest_index(data: bytes) -> int:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PatchError("assemblies.manifest is not UTF-8 text") from exc
    pattern = re.compile(
        r"^0x[0-9a-fA-F]+\s+0x[0-9a-fA-F]+\s+(\d+)\s+(\d+)\s+"
        + re.escape(_ASSEMBLY_NAME)
        + r"\s*$",
        re.MULTILINE,
    )
    matches = pattern.findall(text)
    if len(matches) != 1:
        raise PatchError(
            f"assemblies.manifest has {len(matches)} {_ASSEMBLY_NAME!r} mappings"
        )
    blob_id, blob_index = (int(value, 10) for value in matches[0])
    if blob_id != 0:
        raise PatchError(f"{_ASSEMBLY_NAME} is in unsupported blob ID {blob_id}")
    return blob_index


def _assembly_from_store(
    blob: bytes | bytearray, manifest: bytes
) -> tuple[bytes, dict[str, int]]:
    if len(blob) < 20:
        raise PatchError("assemblies.blob is truncated")
    magic, version, entry_count, index_count, index_size = struct.unpack_from(
        "<5I", blob, 0
    )
    if magic != _XABA_MAGIC or version != _XABA_VERSION:
        raise PatchError(
            f"unsupported XABA header magic=0x{magic:08x}, version={version}"
        )
    if not entry_count or index_count < entry_count or index_size != 0:
        raise PatchError("unsupported XABA v1 index layout")
    descriptor_end = 20 + entry_count * 24
    if descriptor_end > len(blob):
        raise PatchError("XABA descriptor table is truncated")
    assembly_index = _manifest_index(manifest)
    if not 0 <= assembly_index < entry_count:
        raise PatchError("assembly manifest index is outside the XABA descriptor table")
    descriptor_offset = 20 + assembly_index * 24
    data_offset, stored_size, debug_offset, debug_size, config_offset, config_size = (
        struct.unpack_from("<6I", blob, descriptor_offset)
    )
    if data_offset < descriptor_end or stored_size < 12 or data_offset + stored_size > len(blob):
        raise PatchError("managed assembly XABA descriptor is invalid")
    if (debug_offset == 0) != (debug_size == 0) or (config_offset == 0) != (config_size == 0):
        raise PatchError("managed assembly debug/config descriptor is inconsistent")
    stored = bytes(blob[data_offset : data_offset + stored_size])
    if stored[:4] != b"XALZ":
        raise PatchError("managed assembly is not XALZ-compressed")
    mapping_index, uncompressed_size = struct.unpack_from("<II", stored, 4)
    try:
        import lz4.block

        assembly = lz4.block.decompress(
            stored[12:], uncompressed_size=uncompressed_size
        )
    except (ImportError, RuntimeError, ValueError) as exc:
        raise PatchError(f"cannot decode managed XALZ payload: {exc}") from exc
    if len(assembly) != uncompressed_size:
        raise PatchError("managed XALZ payload decoded to an unexpected size")

    occupied_offsets: list[int] = [len(blob)]
    for index in range(entry_count):
        values = struct.unpack_from("<6I", blob, 20 + index * 24)
        for offset in (values[0], values[2], values[4]):
            if offset > data_offset:
                occupied_offsets.append(offset)
    capacity = min(occupied_offsets) - data_offset
    if capacity < stored_size:
        raise PatchError("managed assembly allocation overlaps another XABA entry")
    return assembly, {
        "assembly_index": assembly_index,
        "descriptor_offset": descriptor_offset,
        "data_offset": data_offset,
        "stored_size": stored_size,
        "capacity": capacity,
        "mapping_index": mapping_index,
    }


def _pack_assembly(blob: bytes, manifest: bytes, patched_assembly: bytes) -> bytes:
    _old, info = _assembly_from_store(blob, manifest)
    try:
        import lz4.block

        compressed = lz4.block.compress(
            patched_assembly,
            mode="high_compression",
            compression=12,
            store_size=False,
        )
    except (ImportError, RuntimeError, ValueError) as exc:
        raise PatchError(f"cannot encode managed XALZ payload: {exc}") from exc
    stored = (
        b"XALZ"
        + struct.pack("<II", info["mapping_index"], len(patched_assembly))
        + compressed
    )
    if len(stored) > info["capacity"]:
        raise PatchError(
            f"patched managed assembly needs {len(stored)} bytes; "
            f"XABA slot has {info['capacity']}"
        )
    result = bytearray(blob)
    start = info["data_offset"]
    result[start : start + info["capacity"]] = stored + b"\0" * (
        info["capacity"] - len(stored)
    )
    struct.pack_into("<I", result, info["descriptor_offset"] + 4, len(stored))

    decoded, verify_info = _assembly_from_store(result, manifest)
    if decoded != patched_assembly or verify_info["stored_size"] != len(stored):
        raise PatchError("repacked managed assembly failed its read-back check")
    return bytes(result)


def _probe_pair(blob: bytes, manifest: bytes) -> dict[str, Any]:
    assembly, info = _assembly_from_store(blob, manifest)
    targets, _actions = _discover_assembly(assembly)
    targets.insert(
        0,
        {
            "name": _ASSEMBLY_NAME,
            "state": "patched" if _overall(targets) == "patched" else "original",
            "entry": BLOB_ENTRY,
            "assembly_index": info["assembly_index"],
        },
    )
    # The informational assembly row should not override a failed target.
    return {"state": _overall(targets[1:]), "targets": targets}


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Inspect the named managed assembly without APK hash or signature gates."""

    missing = [
        entry
        for entry in REQUIRED_ENTRIES
        if entry not in extracted or not Path(extracted[entry]).is_file()
    ]
    if missing:
        return {
            "state": "unsupported",
            "targets": [
                {"name": entry, "state": "unsupported", "reason": "required entry missing"}
                for entry in missing
            ],
        }
    try:
        return _probe_pair(
            Path(extracted[BLOB_ENTRY]).read_bytes(),
            Path(extracted[MANIFEST_ENTRY]).read_bytes(),
        )
    except Exception as exc:
        return {
            "state": "unsupported",
            "targets": [
                {"name": _ASSEMBLY_NAME, "state": "unsupported", "reason": str(exc)}
            ],
        }


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Patch recognized original targets and emit one rebuilt assembly-store entry."""

    initial = probe(extracted)
    if initial["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"Rogue Legacy targets are {initial['state']}; refusing to guess")
    blob = Path(extracted[BLOB_ENTRY]).read_bytes()
    manifest = Path(extracted[MANIFEST_ENTRY]).read_bytes()
    assembly, _info = _assembly_from_store(blob, manifest)
    targets, actions = _discover_assembly(assembly)
    if _overall(targets) in ("unsupported", "ambiguous"):
        raise PatchError("managed targets changed during patch application")
    patched = bytearray(assembly)
    changed = False
    for offset, original, replacement in actions:
        actual = bytes(patched[offset : offset + len(original)])
        if actual == replacement:
            continue
        if actual != original:
            raise PatchError("managed target changed during patch application")
        patched[offset : offset + len(original)] = replacement
        changed = True
    if not changed:
        return {}
    verify_targets, _ = _discover_assembly(patched)
    if _overall(verify_targets) != "patched":
        raise PatchError("managed assembly postcondition failed")

    rebuilt = _pack_assembly(blob, manifest, bytes(patched))
    verify = _probe_pair(rebuilt, manifest)
    if verify["state"] != "patched":
        raise PatchError(f"assembly-store postcondition failed: {verify['state']}")

    destination = Path(output_dir) / BLOB_ENTRY
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(rebuilt)
    return {BLOB_ENTRY: destination}
