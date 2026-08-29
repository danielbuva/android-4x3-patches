"""Target-driven 4:3 patch for STALKER: Call of Pripyat Mobile.

The tested port is Unity 2021 IL2CPP.  Its ``GameSettings.DropVideoQuality``
method forces one of three 2:1 resolutions on both bundled ABIs.  This module
locates that method through invariant instruction neighborhoods and changes the
three tiers to 4:3.  Unity objects are resolved by hierarchy path, component
type, and script identity rather than PathID.
"""

from __future__ import annotations

import gc
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATA_ENTRY = "assets/bin/Data/data.unity3d"
ARM64_ENTRY = "lib/arm64-v8a/libil2cpp.so"
ARMV7_ENTRY = "lib/armeabi-v7a/libil2cpp.so"
REQUIRED_ENTRIES = (DATA_ENTRY,)

_FOV_4X3 = struct.unpack(
    "<f",
    struct.pack(
        "<f",
        math.degrees(
            2.0
            * math.atan(
                math.tan(math.radians(60.0) / 2.0)
                * 2.0
                / (4.0 / 3.0)
            )
        ),
    ),
)[0]


class PatchError(RuntimeError):
    """The supplied entries do not contain one safely recognizable target."""


@dataclass(frozen=True)
class _Change:
    name: str
    relative: int
    original: bytes
    patched: bytes


@dataclass(frozen=True)
class _Region:
    name: str
    before: bytes
    span: int
    after: bytes
    changes: tuple[_Change, ...]
    landmarks: tuple[tuple[int, bytes], ...] = ()


@dataclass(frozen=True)
class _NativeSpec:
    entry: str
    abi: str
    elf_class: int
    machine: int
    region: _Region


@dataclass(frozen=True)
class _CanvasSpec:
    name: str
    serialized: str
    path: str
    width: float
    original_height: float
    patched_height: float
    screen_match_mode: int
    match: float


@dataclass(frozen=True)
class _DropdownSpec:
    name: str
    serialized: str
    path: str
    options: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _CameraSpec:
    name: str
    serialized: str
    path: str


@dataclass(frozen=True)
class _VkSpec:
    name: str
    serialized: str
    path: str


@dataclass(frozen=True)
class _SettingsTextSpec:
    name: str
    serialized: str
    root: str
    tested_count: int


def _hx(value: str) -> bytes:
    return bytes.fromhex(value)


_NATIVE_SPECS = (
    _NativeSpec(
        ARM64_ENTRY,
        "arm64-v8a",
        2,
        183,
        _Region(
            "GameSettings.DropVideoQuality",
            _hx("680e40f9c80400b4092141b909010035"),
            0x58,
            _hx("22008052e3031faaa7fa3494680e40f9"),
            (
                _Change("low-tier width 720 to 640", 0x00, _hx("005a8052"), _hx("00508052")),
                _Change("low-tier height 360 to 480", 0x04, _hx("012d8052"), _hx("013c8052")),
                _Change("medium-tier width 1440 to 1280", 0x28, _hx("00b48052"), _hx("00a08052")),
                _Change("medium-tier height 720 to 960", 0x2C, _hx("015a8052"), _hx("01788052")),
                _Change("high-tier width 2160 to 1920", 0x50, _hx("000e8152"), _hx("00f08052")),
                _Change("high-tier height 1080 to 1440", 0x54, _hx("01878052"), _hx("01b48052")),
            ),
            (
                (0x08, _hx("22008052e3031faabbfa3494")),
                (0x18, _hx("a80300b4092141b93f050071")),
                (0x30, _hx("22008052e3031faab1fa3494")),
                (0x40, _hx("680200b4092141b93f090071")),
            ),
        ),
    ),
    _NativeSpec(
        ARMV7_ENTRY,
        "armeabi-v7a",
        1,
        40,
        _Region(
            "GameSettings.DropVideoQuality",
            _hx("6a2afeebc40095e5000050e30400001a"),
            0x68,
            _hx("0120a0e30030a0e3a81b41eb0c4094e5"),
            (
                _Change("low-tier width 720 to 640", 0x00, _hx("2d0ea0e3"), _hx("800200e3")),
                _Change("low-tier height 360 to 480", 0x04, _hx("5a1fa0e3"), _hx("e01100e3")),
                _Change("medium-tier width 1440 to 1280", 0x30, _hx("5a0ea0e3"), _hx("000500e3")),
                _Change("medium-tier height 720 to 960", 0x34, _hx("2d1ea0e3"), _hx("c01300e3")),
                _Change("high-tier width 2160 to 1920", 0x60, _hx("870ea0e3"), _hx("800700e3")),
                _Change("high-tier height 1080 to 1440", 0x64, _hx("381400e3"), _hx("a01500e3")),
            ),
            (
                (0x08, _hx("0120a0e30030a0e3c01b41eb")),
                (0x18, _hx("000055e30000001a5e2afeeb")),
                (0x38, _hx("0120a0e30030a0e3b41b41eb")),
                (0x40, _hx("b41b41eb0c5094e5000055e3")),
            ),
        ),
    ),
)


_CANVAS_SPECS = (
    _CanvasSpec(
        "author/credits CanvasScaler",
        "level0",
        "Author",
        1920.0,
        1080.0,
        1440.0,
        0,
        1.0,
    ),
    _CanvasSpec(
        "main-menu CanvasScaler",
        "level0",
        "Canvas",
        1280.0,
        720.0,
        960.0,
        2,
        1.0,
    ),
    _CanvasSpec(
        "gameplay/pause CanvasScaler",
        "level1",
        "Player/UI",
        1920.0,
        1080.0,
        1440.0,
        0,
        1.0,
    ),
)


_DROPDOWN_SPECS = (
    _DropdownSpec(
        "main-menu resolution labels",
        "level0",
        "Canvas/Setting/VideoSettings/Resolution",
        (
            ("720x360", "640x480"),
            ("1440х720", "1280х960"),
            ("2160х1080", "1920х1440"),
        ),
    ),
    _DropdownSpec(
        "pause-menu resolution labels",
        "level1",
        "Player/UI/Pause/Setting/VideoSettings/Resolution",
        (
            ("720х360", "640х480"),
            ("1440х720", "1280х960"),
            ("2160х1080", "1920х1440"),
        ),
    ),
)


_CAMERA_SPECS = (
    _CameraSpec("main-menu perspective camera", "level0", "MainCamera"),
    _CameraSpec("character perspective camera", "level1", "Player/CharacterCam"),
    _CameraSpec(
        "first-person gun perspective camera",
        "level1",
        "Player/CharacterCam/GunCamera",
    ),
)


_VK_SPECS = (
    _VkSpec("main-menu VK promo button", "level0", "Canvas/Glavnaia/Button"),
    _VkSpec("pause-menu VK promo button", "level1", "Player/UI/Pause/Button"),
)


_SETTINGS_TEXT_SPECS = (
    _SettingsTextSpec(
        "main-menu settings text scale",
        "level0",
        "Canvas/Setting",
        68,
    ),
    _SettingsTextSpec(
        "pause-menu settings text scale",
        "level1",
        "Player/UI/Pause/Setting",
        70,
    ),
)

# Unity UI Text serializes FontData.m_FontSize at 0x64 in this Unity 2021
# build. Scale only the four font sizes used below the two uniquely named
# settings roots; gameplay HUD and unrelated menus are intentionally untouched.
_TEXT_FONT_SIZE_OFFSET = 0x64
_SETTINGS_FONT_SIZES = {11: 15, 12: 16, 14: 19, 15: 20}


_INTRO_RECTS = (
    ("intro root stretch", "Player/UI/intro"),
    ("intro image stretch", "Player/UI/intro/Image"),
    ("intro raw-image stretch", "Player/UI/intro/RawImage"),
)
_INTRO_VIDEO_PATH = "Player/UI/intro/Video Player"


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
    # Source-specific cleanup and verified intro behavior are informational.
    # Compatibility is gated only by the native resolutions, perspective
    # cameras, CanvasScalers, and resolution dropdowns.
    states = {
        str(target["state"])
        for target in targets
        if not bool(target.get("optional"))
    }
    if not states:
        return "unsupported"
    if "ambiguous" in states:
        return "ambiguous"
    if "unsupported" in states:
        return "unsupported"
    if states == {"patched"}:
        return "patched"
    return "original"


def _executable_ranges(data: bytes | bytearray, spec: _NativeSpec) -> list[tuple[int, int]]:
    if len(data) < 64 or bytes(data[:4]) != b"\x7fELF":
        raise PatchError(f"{spec.entry} is not an ELF binary")
    if data[4] != spec.elf_class or data[5] != 1:
        raise PatchError(f"{spec.entry} is not the expected little-endian ELF class")
    if struct.unpack_from("<H", data, 18)[0] != spec.machine:
        raise PatchError(f"{spec.entry} ELF machine does not match {spec.abi}")
    ranges: list[tuple[int, int]] = []
    if spec.elf_class == 2:
        program_offset = struct.unpack_from("<Q", data, 32)[0]
        entry_size = struct.unpack_from("<H", data, 54)[0]
        count = struct.unpack_from("<H", data, 56)[0]
        minimum = 56
        for index in range(count):
            offset = program_offset + index * entry_size
            if entry_size < minimum or offset + minimum > len(data):
                raise PatchError(f"{spec.entry} program-header table is truncated")
            kind, flags, file_offset, _va, _pa, file_size, _mem_size = struct.unpack_from(
                "<IIQQQQQ", data, offset
            )
            if kind == 1 and flags & 1:
                ranges.append((int(file_offset), int(file_offset + file_size)))
    else:
        program_offset = struct.unpack_from("<I", data, 28)[0]
        entry_size = struct.unpack_from("<H", data, 42)[0]
        count = struct.unpack_from("<H", data, 44)[0]
        minimum = 32
        for index in range(count):
            offset = program_offset + index * entry_size
            if entry_size < minimum or offset + minimum > len(data):
                raise PatchError(f"{spec.entry} program-header table is truncated")
            kind, file_offset, _va, _pa, file_size, _mem_size, flags, _align = (
                struct.unpack_from("<IIIIIIII", data, offset)
            )
            if kind == 1 and flags & 1:
                ranges.append((file_offset, file_offset + file_size))
    if not ranges:
        raise PatchError(f"{spec.entry} has no executable PT_LOAD segment")
    return ranges


def _discover_native(
    data: bytes | bytearray, spec: _NativeSpec
) -> tuple[list[dict[str, Any]], list[tuple[int, bytes, bytes]]]:
    executable = _executable_ranges(data, spec)
    matches = _locate_region(data, spec.region)
    if len(matches) != 1:
        return (
            [
                {
                    "name": spec.region.name,
                    "entry": spec.entry,
                    "abi": spec.abi,
                    "state": "ambiguous" if len(matches) > 1 else "unsupported",
                    "matches": len(matches),
                }
            ],
            [],
        )
    base = matches[0]
    if not any(start <= base and base + spec.region.span <= end for start, end in executable):
        return (
            [
                {
                    "name": spec.region.name,
                    "entry": spec.entry,
                    "abi": spec.abi,
                    "state": "unsupported",
                    "reason": "instruction region is not in one executable PT_LOAD segment",
                }
            ],
            [],
        )
    targets: list[dict[str, Any]] = []
    actions: list[tuple[int, bytes, bytes]] = []
    for change in spec.region.changes:
        offset = base + change.relative
        actual = bytes(data[offset : offset + len(change.original)])
        state = _value_state(actual, change.original, change.patched)
        targets.append(
            {
                "name": change.name,
                "method": spec.region.name,
                "entry": spec.entry,
                "abi": spec.abi,
                "state": state,
                "matches": 1,
            }
        )
        if state in ("original", "patched"):
            actions.append((offset, change.original, change.patched))
    return targets, actions


def _unitypy():
    try:
        import UnityPy
    except ImportError as exc:  # pragma: no cover - dependency preflight owns this
        raise PatchError("UnityPy is required for the STALKER patch") from exc
    return UnityPy


def _load_bundle(path: Path):
    environment = _unitypy().load(str(path))
    files = list(environment.files.values())
    if len(files) != 1 or getattr(files[0], "signature", None) != "UnityFS":
        del environment
        gc.collect()
        raise PatchError("data.unity3d is not one supported UnityFS bundle")
    bundle = files[0]
    for name in ("level0", "level1"):
        if name not in bundle.files:
            del bundle
            del environment
            gc.collect()
            raise PatchError(f"data.unity3d has no {name} serialized scene")
    return environment, bundle


def _near(value: Any, expected: float, tolerance: float = 1e-4) -> bool:
    try:
        return math.isclose(float(value), expected, rel_tol=0.0, abs_tol=tolerance)
    except (TypeError, ValueError):
        return False


def _pair(value: Any) -> tuple[float, float] | None:
    try:
        if isinstance(value, dict):
            return float(value["x"]), float(value["y"])
        return float(value.x), float(value.y)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _target_paths(serialized_name: str) -> set[str]:
    result = {
        item.path for item in _CANVAS_SPECS if item.serialized == serialized_name
    }
    result.update(
        item.path for item in _DROPDOWN_SPECS if item.serialized == serialized_name
    )
    result.update(
        item.path for item in _CAMERA_SPECS if item.serialized == serialized_name
    )
    result.update(item.path for item in _VK_SPECS if item.serialized == serialized_name)
    result.update(
        item.root for item in _SETTINGS_TEXT_SPECS if item.serialized == serialized_name
    )
    if serialized_name == "level1":
        result.update(path for _name, path in _INTRO_RECTS)
        result.add(_INTRO_VIDEO_PATH)
    return result


def _path_index(serialized: Any, wanted: set[str]) -> dict[str, list[int]]:
    transforms = {
        int(path_id): reader
        for path_id, reader in serialized.objects.items()
        if reader.type.name in ("Transform", "RectTransform")
    }
    cache: dict[int, str] = {}
    visiting: set[int] = set()

    def resolve(path_id: int) -> str:
        if path_id in cache:
            return cache[path_id]
        if path_id in visiting:
            raise PatchError("Unity Transform hierarchy contains a cycle")
        visiting.add(path_id)
        transform = transforms[path_id].read()
        name = str(transform.m_GameObject.read().m_Name)
        father = int(transform.m_Father.path_id) if transform.m_Father else 0
        value = f"{resolve(father)}/{name}" if father in transforms else name
        visiting.remove(path_id)
        cache[path_id] = value
        return value

    result = {path: [] for path in wanted}
    settings_roots = tuple(
        spec.root
        for spec in _SETTINGS_TEXT_SPECS
        if spec.serialized == getattr(serialized, "name", "")
    )
    # UnityPy's serialized file name is not consistent across versions, so
    # also derive the applicable roots from the wanted exact paths.
    if not settings_roots:
        settings_roots = tuple(
            spec.root
            for spec in _SETTINGS_TEXT_SPECS
            if spec.root in wanted
        )
    for path_id, reader in transforms.items():
        path = resolve(path_id)
        if path in result or any(
            path == root or path.startswith(root + "/") for root in settings_roots
        ):
            result.setdefault(path, [])
            game_object_id = int(reader.read().m_GameObject.path_id)
            if game_object_id not in result[path]:
                result[path].append(game_object_id)
    return result


def _one_game_object(
    serialized: Any,
    index: dict[str, list[int]],
    *,
    name: str,
    path: str,
    targets: list[dict[str, Any]],
) -> Any | None:
    matches = index.get(path, [])
    if len(matches) != 1:
        targets.append(
            {
                "name": name,
                "state": "ambiguous" if len(matches) > 1 else "unsupported",
                "entry": DATA_ENTRY,
                "path": path,
                "matches": len(matches),
            }
        )
        return None
    reader = serialized.objects.get(matches[0])
    if reader is None or reader.type.name != "GameObject":
        targets.append(
            {
                "name": name,
                "state": "unsupported",
                "entry": DATA_ENTRY,
                "path": path,
                "reason": "hierarchy target has no GameObject reader",
            }
        )
        return None
    return reader


def _components(serialized: Any, game_object_reader: Any) -> list[Any]:
    game_object = game_object_reader.read()
    result: list[Any] = []
    for item in game_object.m_Component:
        pointer = getattr(item, "component", item)
        reader = serialized.objects.get(int(pointer.path_id))
        if reader is not None:
            result.append(reader)
    return result


def _script_identity(reader: Any) -> tuple[str, str, str] | None:
    if reader.type.name != "MonoBehaviour":
        return None
    try:
        script = reader.read(check_read=False).m_Script.read()
        return (
            str(script.m_ClassName),
            str(script.m_Namespace),
            str(script.m_AssemblyName),
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _one_component(
    serialized: Any,
    game_object_reader: Any,
    *,
    type_name: str,
    script: tuple[str, str, str] | None = None,
) -> list[Any]:
    result: list[Any] = []
    for reader in _components(serialized, game_object_reader):
        if reader.type.name != type_name:
            continue
        if script is not None and _script_identity(reader) != script:
            continue
        result.append(reader)
    return result


def _canvas_state(raw: bytes, spec: _CanvasSpec) -> str:
    if len(raw) != 80:
        return "unsupported"
    try:
        ui_scale_mode = struct.unpack_from("<i", raw, 0x20)[0]
        reference_ppu = struct.unpack_from("<f", raw, 0x24)[0]
        scale_factor = struct.unpack_from("<f", raw, 0x28)[0]
        width, height = struct.unpack_from("<ff", raw, 0x2C)
        screen_match_mode = struct.unpack_from("<i", raw, 0x34)[0]
        match = struct.unpack_from("<f", raw, 0x38)[0]
    except struct.error:
        return "unsupported"
    if not (
        ui_scale_mode == 1
        and _near(reference_ppu, 100.0)
        and _near(scale_factor, 1.0)
        and _near(width, spec.width)
        and screen_match_mode == spec.screen_match_mode
        and _near(match, spec.match)
    ):
        return "unsupported"
    if _near(height, spec.original_height):
        return "original"
    if _near(height, spec.patched_height):
        return "patched"
    return "unsupported"


def _settings_font_state(raw: bytes) -> tuple[str, int | None]:
    if len(raw) < _TEXT_FONT_SIZE_OFFSET + 4:
        return "unsupported", None
    value = struct.unpack_from("<i", raw, _TEXT_FONT_SIZE_OFFSET)[0]
    if value in set(_SETTINGS_FONT_SIZES).intersection(_SETTINGS_FONT_SIZES.values()):
        return "ambiguous", value
    if value in _SETTINGS_FONT_SIZES:
        return "original", value
    if value in _SETTINGS_FONT_SIZES.values():
        return "patched", value
    return "unsupported", value


def _option_record(value: str) -> bytes:
    encoded = value.encode("utf-8")
    padding = (-len(encoded)) & 3
    return struct.pack("<I", len(encoded)) + encoded + b"\0" * padding


def _dropdown_states(
    raw: bytes, spec: _DropdownSpec
) -> tuple[list[dict[str, Any]], list[tuple[int, bytes, bytes]]]:
    targets: list[dict[str, Any]] = []
    actions: list[tuple[int, bytes, bytes]] = []
    if raw.count(b"DropVideoQuality") != 1:
        return (
            [
                {
                    "name": spec.name,
                    "state": "unsupported",
                    "reason": "Dropdown listener is not one DropVideoQuality callback",
                }
            ],
            [],
        )
    for original_text, patched_text in spec.options:
        original = _option_record(original_text)
        patched = _option_record(patched_text)
        if len(original) != len(patched):  # pragma: no cover - definition invariant
            raise PatchError("resolution label replacements are not length-preserving")
        original_matches = list(_find_all(raw, original))
        patched_matches = list(_find_all(raw, patched))
        total = len(original_matches) + len(patched_matches)
        if total == 1:
            state = "original" if original_matches else "patched"
            offset = (original_matches or patched_matches)[0]
            actions.append((offset, original, patched))
        elif total > 1:
            state = "ambiguous"
        else:
            state = "unsupported"
        targets.append(
            {
                "name": f"{spec.name}: {original_text} to {patched_text}",
                "state": state,
                "matches": total,
            }
        )
    return targets, actions


def _discover_unity(bundle: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    targets: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    indexes = {
        name: _path_index(bundle.files[name], _target_paths(name))
        for name in ("level0", "level1")
    }

    for spec in _CANVAS_SPECS:
        serialized = bundle.files[spec.serialized]
        game_object = _one_game_object(
            serialized,
            indexes[spec.serialized],
            name=spec.name,
            path=spec.path,
            targets=targets,
        )
        if game_object is None:
            continue
        readers = _one_component(
            serialized,
            game_object,
            type_name="MonoBehaviour",
            script=("CanvasScaler", "UnityEngine.UI", "UnityEngine.UI.dll"),
        )
        if len(readers) != 1:
            targets.append(
                {
                    "name": spec.name,
                    "state": "ambiguous" if len(readers) > 1 else "unsupported",
                    "entry": DATA_ENTRY,
                    "path": spec.path,
                    "matches": len(readers),
                }
            )
            continue
        raw = bytes(readers[0].get_raw_data())
        state = _canvas_state(raw, spec)
        targets.append(
            {
                "name": spec.name,
                "state": state,
                "entry": DATA_ENTRY,
                "path": spec.path,
            }
        )
        if state in ("original", "patched"):
            actions.append(
                {
                    "kind": "raw",
                    "reader": readers[0],
                    "offset": 0x30,
                    "original": struct.pack("<f", spec.original_height),
                    "patched": struct.pack("<f", spec.patched_height),
                    "state": state,
                    "name": spec.name,
                }
            )

    for spec in _DROPDOWN_SPECS:
        serialized = bundle.files[spec.serialized]
        game_object = _one_game_object(
            serialized,
            indexes[spec.serialized],
            name=spec.name,
            path=spec.path,
            targets=targets,
        )
        if game_object is None:
            continue
        readers = _one_component(
            serialized,
            game_object,
            type_name="MonoBehaviour",
            script=("Dropdown", "UnityEngine.UI", "UnityEngine.UI.dll"),
        )
        if len(readers) != 1:
            targets.append(
                {
                    "name": spec.name,
                    "state": "ambiguous" if len(readers) > 1 else "unsupported",
                    "entry": DATA_ENTRY,
                    "path": spec.path,
                    "matches": len(readers),
                }
            )
            continue
        raw = bytes(readers[0].get_raw_data())
        dropdown_targets, dropdown_actions = _dropdown_states(raw, spec)
        for target in dropdown_targets:
            target.update(entry=DATA_ENTRY, path=spec.path)
        targets.extend(dropdown_targets)
        for offset, original, patched in dropdown_actions:
            state = _value_state(raw[offset : offset + len(original)], original, patched)
            actions.append(
                {
                    "kind": "raw",
                    "reader": readers[0],
                    "offset": offset,
                    "original": original,
                    "patched": patched,
                    "state": state,
                    "name": spec.name,
                }
            )

    for spec in _SETTINGS_TEXT_SPECS:
        serialized = bundle.files[spec.serialized]
        before_count = len(targets)
        root = _one_game_object(
            serialized,
            indexes[spec.serialized],
            name=spec.name,
            path=spec.root,
            targets=targets,
        )
        if root is None:
            continue
        text_readers: list[tuple[str, Any, bytes, int]] = []
        ambiguous_components = False
        for path in sorted(indexes[spec.serialized]):
            if not (path == spec.root or path.startswith(spec.root + "/")):
                continue
            game_object_ids = indexes[spec.serialized][path]
            if len(game_object_ids) != 1:
                ambiguous_components = True
                continue
            game_object = serialized.objects.get(game_object_ids[0])
            if game_object is None or game_object.type.name != "GameObject":
                ambiguous_components = True
                continue
            readers = _one_component(
                serialized,
                game_object,
                type_name="MonoBehaviour",
                script=("Text", "UnityEngine.UI", "UnityEngine.UI.dll"),
            )
            if not readers:
                continue
            if len(readers) != 1:
                ambiguous_components = True
                continue
            raw = bytes(readers[0].get_raw_data())
            _item_state, value = _settings_font_state(raw)
            if value is None:
                value = -1
            text_readers.append((path, readers[0], raw, value))

        values = [item[3] for item in text_readers]
        recognized = set(_SETTINGS_FONT_SIZES) | set(_SETTINGS_FONT_SIZES.values())
        definite_original = set(_SETTINGS_FONT_SIZES) - set(_SETTINGS_FONT_SIZES.values())
        definite_patched = set(_SETTINGS_FONT_SIZES.values()) - set(_SETTINGS_FONT_SIZES)
        has_original = any(value in definite_original for value in values)
        has_patched = any(value in definite_patched for value in values)
        if ambiguous_components:
            state = "ambiguous"
        elif len(text_readers) < 40:
            state = "unsupported"
        elif any(value not in recognized for value in values):
            state = "unsupported"
        elif has_original and has_patched:
            state = "ambiguous"
        elif has_original:
            state = "original"
        elif has_patched:
            state = "patched"
        else:
            state = "ambiguous"
        targets.append(
            {
                "name": spec.name,
                "state": state,
                "entry": DATA_ENTRY,
                "path": spec.root,
                "text_components": len(text_readers),
                "tested_text_components": spec.tested_count,
            }
        )
        if state == "original":
            for path, reader, raw, value in text_readers:
                original = struct.pack("<i", value)
                patched = struct.pack("<i", _SETTINGS_FONT_SIZES[value])
                actions.append(
                    {
                        "kind": "raw",
                        "reader": reader,
                        "offset": _TEXT_FONT_SIZE_OFFSET,
                        "original": original,
                        "patched": patched,
                        "state": "original",
                        "name": f"{spec.name}: {path}",
                    }
                )
        if len(targets) == before_count:  # pragma: no cover - internal invariant
            raise PatchError(f"{spec.name} discovery produced no target")

    for spec in _CAMERA_SPECS:
        serialized = bundle.files[spec.serialized]
        game_object = _one_game_object(
            serialized,
            indexes[spec.serialized],
            name=spec.name,
            path=spec.path,
            targets=targets,
        )
        if game_object is None:
            continue
        readers = _one_component(serialized, game_object, type_name="Camera")
        if len(readers) != 1:
            targets.append(
                {
                    "name": spec.name,
                    "state": "ambiguous" if len(readers) > 1 else "unsupported",
                    "entry": DATA_ENTRY,
                    "path": spec.path,
                    "matches": len(readers),
                }
            )
            continue
        data = readers[0].read()
        value = float(data.field_of_view)
        if bool(data.orthographic) or int(data.m_Enabled) != 1:
            state = "unsupported"
        elif _near(value, 60.0):
            state = "original"
        elif _near(value, _FOV_4X3):
            state = "patched"
        else:
            state = "unsupported"
        targets.append(
            {
                "name": spec.name,
                "state": state,
                "entry": DATA_ENTRY,
                "path": spec.path,
                "field_of_view": value,
            }
        )
        if state in ("original", "patched"):
            actions.append(
                {
                    "kind": "camera",
                    "reader": readers[0],
                    "state": state,
                    "name": spec.name,
                }
            )

    vk_listener = _option_record("Vk")
    for spec in _VK_SPECS:
        serialized = bundle.files[spec.serialized]
        before_optional = len(targets)
        game_object = _one_game_object(
            serialized,
            indexes[spec.serialized],
            name=spec.name,
            path=spec.path,
            targets=targets,
        )
        if game_object is None:
            for target in targets[before_optional:]:
                target["optional"] = True
                target["state"] = "absent" if target.get("matches") == 0 else "unrecognized"
            continue
        buttons = _one_component(
            serialized,
            game_object,
            type_name="MonoBehaviour",
            script=("Button", "UnityEngine.UI", "UnityEngine.UI.dll"),
        )
        listener_matches = (
            bytes(buttons[0].get_raw_data()).count(vk_listener) if len(buttons) == 1 else 0
        )
        if len(buttons) != 1 or listener_matches != 1:
            targets.append(
                {
                    "name": spec.name,
                    "state": "unrecognized",
                    "optional": True,
                    "entry": DATA_ENTRY,
                    "path": spec.path,
                    "reason": "button does not have one target-verified Vk listener",
                }
            )
            continue
        tree = game_object.read_typetree()
        active = tree.get("m_IsActive")
        state = "original" if active is True else "patched" if active is False else "unsupported"
        targets.append(
            {
                "name": spec.name,
                "state": state,
                "optional": True,
                "entry": DATA_ENTRY,
                "path": spec.path,
            }
        )
        if state in ("original", "patched"):
            actions.append(
                {
                    "kind": "game-object",
                    "reader": game_object,
                    "state": state,
                    "name": spec.name,
                }
            )

    serialized = bundle.files["level1"]
    for name, path in _INTRO_RECTS:
        before_optional = len(targets)
        game_object = _one_game_object(
            serialized,
            indexes["level1"],
            name=name,
            path=path,
            targets=targets,
        )
        if game_object is None:
            for target in targets[before_optional:]:
                target["optional"] = True
                target["state"] = "absent" if target.get("matches") == 0 else "unrecognized"
            continue
        readers = _one_component(serialized, game_object, type_name="RectTransform")
        if len(readers) != 1:
            targets.append(
                {
                    "name": name,
                    "state": "unrecognized",
                    "optional": True,
                    "entry": DATA_ENTRY,
                    "path": path,
                    "matches": len(readers),
                }
            )
            continue
        tree = readers[0].read_typetree()
        state = (
            "patched"
            if _pair(tree.get("m_AnchorMin")) == (0.0, 0.0)
            and _pair(tree.get("m_AnchorMax")) == (1.0, 1.0)
            else "unsupported"
        )
        targets.append(
            {
                "name": name,
                "state": state,
                "optional": True,
                "entry": DATA_ENTRY,
                "path": path,
            }
        )

    before_optional = len(targets)
    game_object = _one_game_object(
        serialized,
        indexes["level1"],
        name="intro VideoPlayer proportional mode",
        path=_INTRO_VIDEO_PATH,
        targets=targets,
    )
    if game_object is None:
        for target in targets[before_optional:]:
            target["optional"] = True
            target["state"] = "absent" if target.get("matches") == 0 else "unrecognized"
    if game_object is not None:
        readers = _one_component(serialized, game_object, type_name="VideoPlayer")
        if len(readers) == 1:
            tree = readers[0].read_typetree()
            clip = tree.get("m_VideoClip", {})
            state = (
                "patched"
                if int(tree.get("m_AspectRatio", -1)) == 2
                and int(tree.get("m_RenderMode", -1)) == 2
                and int(clip.get("m_PathID", -1)) == 0
                else "unsupported"
            )
        else:
            state = "unrecognized"
        targets.append(
            {
                "name": "intro VideoPlayer proportional mode",
                "state": state,
                "optional": True,
                "entry": DATA_ENTRY,
                "path": _INTRO_VIDEO_PATH,
                "matches": len(readers),
            }
        )
    return targets, actions


def _unity_targets(path: Path) -> list[dict[str, Any]]:
    environment = bundle = None
    try:
        environment, bundle = _load_bundle(path)
        targets, _actions = _discover_unity(bundle)
        return targets
    finally:
        del bundle
        del environment
        gc.collect()


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Inspect required Unity and native targets without APK/version hash gates."""

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
    targets: list[dict[str, Any]] = []
    try:
        targets.extend(_unity_targets(Path(extracted[DATA_ENTRY])))
    except Exception as exc:
        targets.append(
            {"name": "Unity data bundle", "state": "unsupported", "reason": str(exc)}
        )
    for spec in _NATIVE_SPECS:
        if spec.entry not in extracted:
            continue
        try:
            native_targets, _actions = _discover_native(
                Path(extracted[spec.entry]).read_bytes(), spec
            )
            targets.extend(native_targets)
        except Exception as exc:
            targets.append(
                {
                    "name": f"{spec.abi} native library",
                    "state": "unsupported",
                    "entry": spec.entry,
                    "reason": str(exc),
                }
            )
    if not any(spec.entry in extracted for spec in _NATIVE_SPECS):
        targets.append(
            {
                "name": "audited native ABI",
                "state": "unsupported",
                "reason": "neither arm64-v8a nor armeabi-v7a libil2cpp.so is present",
            }
        )
    public_targets = [target for target in targets if not target.get("optional", False)]
    return {"state": _overall(targets), "targets": public_targets}


def _patch_native(source: Path, destination: Path, spec: _NativeSpec) -> bool:
    data = bytearray(source.read_bytes())
    targets, actions = _discover_native(data, spec)
    if _overall(targets) in ("unsupported", "ambiguous"):
        raise PatchError(f"{spec.abi} native targets changed during application")
    changed = False
    for offset, original, patched in actions:
        actual = bytes(data[offset : offset + len(original)])
        if actual == patched:
            continue
        if actual != original:
            raise PatchError(f"{spec.abi} native instruction changed during application")
        data[offset : offset + len(original)] = patched
        changed = True
    verify, _ = _discover_native(data, spec)
    if _overall(verify) != "patched":
        raise PatchError(f"{spec.abi} native postcondition failed")
    if changed:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return changed


def _patch_unity(source: Path, destination: Path) -> bool:
    environment = bundle = None
    changed = False
    try:
        environment, bundle = _load_bundle(source)
        targets, actions = _discover_unity(bundle)
        if _overall(targets) in ("unsupported", "ambiguous"):
            raise PatchError("Unity targets changed during patch application")
        # UnityPy stages raw payload replacements on ``reader.data`` while
        # ``get_raw_data()`` continues to expose the source stream.  Batch all
        # changes for one Dropdown before staging it so three option edits do
        # not overwrite one another.
        raw_batches: dict[int, tuple[Any, bytearray]] = {}
        for action in actions:
            if action["state"] != "original" or action["kind"] != "raw":
                continue
            reader = action["reader"]
            key = id(reader)
            if key not in raw_batches:
                raw_batches[key] = (reader, bytearray(reader.get_raw_data()))
            raw = raw_batches[key][1]
            offset = int(action["offset"])
            original = action["original"]
            patched = action["patched"]
            if bytes(raw[offset : offset + len(original)]) != original:
                raise PatchError(f"{action['name']} changed during application")
            raw[offset : offset + len(original)] = patched
            changed = True
        for reader, raw in raw_batches.values():
            reader.set_raw_data(bytes(raw))

        for action in actions:
            if action["state"] != "original" or action["kind"] == "raw":
                continue
            reader = action["reader"]
            if action["kind"] == "camera":
                tree = reader.read_typetree()
                if not _near(tree.get("field of view"), 60.0):
                    raise PatchError(f"{action['name']} changed during application")
                tree["field of view"] = _FOV_4X3
                reader.save_typetree(tree)
            elif action["kind"] == "game-object":
                tree = reader.read_typetree()
                if tree.get("m_IsActive") is not True:
                    raise PatchError(f"{action['name']} changed during application")
                tree["m_IsActive"] = False
                reader.save_typetree(tree)
            else:  # pragma: no cover - internal invariant
                raise PatchError(f"unknown Unity action kind: {action['kind']}")
            changed = True
        if changed:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(bundle.save(packer="original"))
    finally:
        del bundle
        del environment
        gc.collect()
    return changed


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Write only recognized replacement entries and verify every postcondition."""

    initial = probe(extracted)
    if initial["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"STALKER targets are {initial['state']}; refusing to guess")
    if initial["state"] == "patched":
        return {}

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    replacements: dict[str, Path] = {}

    data_output = output_dir / "data.unity3d"
    if _patch_unity(Path(extracted[DATA_ENTRY]), data_output):
        replacements[DATA_ENTRY] = data_output

    for spec in _NATIVE_SPECS:
        if spec.entry not in extracted:
            continue
        destination = output_dir / f"libil2cpp-{spec.abi}.so"
        if _patch_native(Path(extracted[spec.entry]), destination, spec):
            replacements[spec.entry] = destination

    verification_input = dict(extracted)
    verification_input.update(replacements)
    verification = probe(verification_input)
    if verification["state"] != "patched":
        raise PatchError(f"STALKER post-patch verification failed: {verification['state']}")
    return replacements
