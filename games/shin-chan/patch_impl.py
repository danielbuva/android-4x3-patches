"""Semantic Shin Chan: Shiro & Coal Town 4:3 patch."""

from __future__ import annotations

import gc
import io
import math
import struct
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_ENTRIES: tuple[str, ...] = ()

_BUNDLE_PREFIX = "assets/aa/android/"
_FALLBACK_UNITY_VERSION = "6000.0.58f2"
PREFERRED_ENTRIES = (
    "assets/aa/Android/70b5c8e3a6b61b4c36575520b6171bd2.bundle",
    "assets/aa/Android/776c9c4756d0465df21aaa0a4c1c42fa.bundle",
    "assets/aa/Android/a6d851deff04d7b26bf91f33c4602b52.bundle",
    "assets/aa/Android/38cc20153de5f2c061629579cb58f064.bundle",
)
_PREFERRED_BUNDLES = PREFERRED_ENTRIES

_F2 = lambda x, y: struct.pack("<ff", x, y)
_I4 = lambda value: struct.pack("<i", value)
_FOV_4X3 = struct.unpack(
    "<f",
    struct.pack(
        "<f",
        math.degrees(
            2.0
            * math.atan(
                math.tan(math.radians(60.0) / 2.0)
                * (16.0 / 9.0)
                / (4.0 / 3.0)
            )
        ),
    ),
)[0]


class PatchError(RuntimeError):
    """The input does not contain one safely identifiable patch target."""


@dataclass(frozen=True)
class _Change:
    offset: int
    original: bytes
    replacement: bytes


@dataclass(frozen=True)
class _Target:
    entry: str
    serialized_file: str
    path_id: int
    role: str
    status: str


_CHANGES: dict[str, tuple[_Change, ...]] = {
    "gameplay-aspect-controller": (_Change(0x0C, _I4(1), _I4(0)),),
    "gameplay-camera-fov": (_Change(0x7C, struct.pack("<f", 60.0), struct.pack("<f", _FOV_4X3)),),
    "title-root": (_Change(0xA4, _F2(1920.0, 1080.0), _F2(1920.0, 1440.0)),),
    "title-art": (
        _Change(0x44, _F2(0.0, 0.0), _F2(0.5, 0.5)),
        _Change(0x4C, _F2(1.0, 1.0), _F2(0.5, 0.5)),
        _Change(0x5C, _F2(0.0, 0.0), _F2(2560.0, 1440.0)),
    ),
    "title-canvas-scaler": (_Change(0x2C, _F2(1920.0, 1080.0), _F2(1920.0, 1440.0)),),
    "movie-canvas": (_Change(0x5C, _F2(1920.0, 1080.0), _F2(2560.0, 1440.0)),),
    "movie-crop-mode": (_Change(0x5C, _I4(2), _I4(4)),),
    "movie-canvas-scaler": (_Change(0x2C, _F2(1920.0, 1080.0), _F2(1920.0, 1440.0)),),
    "main-menu-canvas-scaler": (_Change(0x2C, _F2(1920.0, 1080.0), _F2(1920.0, 1440.0)),),
}

_EXPECTED_ROLES = tuple(_CHANGES)


def _normal_entries(extracted: dict[str, Path]) -> dict[str, tuple[str, Path]]:
    return {
        name.replace("\\", "/").lower(): (name.replace("\\", "/"), Path(path))
        for name, path in extracted.items()
    }


def _bundle_entries(extracted: dict[str, Path]) -> list[tuple[str, Path]]:
    entries = [
        value
        for key, value in _normal_entries(extracted).items()
        if key.startswith(_BUNDLE_PREFIX) and key.endswith(".bundle")
    ]
    preferred = {name.lower(): index for index, name in enumerate(_PREFERRED_BUNDLES)}
    return sorted(entries, key=lambda item: (preferred.get(item[0].lower(), 999), item[0]))


def _unity_module():
    try:
        import UnityPy
        from UnityPy import config
    except ImportError as exc:  # pragma: no cover - dependency preflight owns this
        raise PatchError("UnityPy is required for the Shin Chan patch") from exc
    config.FALLBACK_UNITY_VERSION = _FALLBACK_UNITY_VERSION
    return UnityPy


def _load_bundle(path: Path):
    UnityPy = _unity_module()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        environment = UnityPy.load(io.BytesIO(path.read_bytes()))
    top = list(environment.files.values())
    if len(top) != 1 or getattr(top[0], "signature", None) != "UnityFS":
        del environment
        gc.collect()
        raise PatchError(f"{path.name}: not a supported UnityFS bundle")
    return environment, top[0]


def _pair(value: Any) -> tuple[float, float] | None:
    try:
        return (float(value.x), float(value.y))
    except (AttributeError, TypeError, ValueError):
        return None


def _same_pair(actual: tuple[float, float] | None, expected: tuple[float, float]) -> bool:
    return actual is not None and all(abs(a - b) < 0.0001 for a, b in zip(actual, expected))


def _game_object(data: Any) -> tuple[int, str] | None:
    try:
        pointer = data.m_GameObject
        if not pointer.path_id:
            return None
        return int(pointer.path_id), pointer.read().m_Name
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _component_order(data: Any) -> tuple[int, ...]:
    try:
        game_object = data.m_GameObject.read()
        return tuple(
            int(getattr(item, "component", item).path_id)
            for item in game_object.m_Component
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return ()


def _parent_name(data: Any) -> str | None:
    try:
        parent = data.m_Father
        if not parent.path_id:
            return None
        return parent.read().m_GameObject.read().m_Name
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _raw_state(role: str, raw: bytes) -> str:
    changes = _CHANGES[role]
    old = all(
        len(raw) >= item.offset + len(item.original)
        and raw[item.offset : item.offset + len(item.original)] == item.original
        for item in changes
    )
    new = all(
        len(raw) >= item.offset + len(item.replacement)
        and raw[item.offset : item.offset + len(item.replacement)] == item.replacement
        for item in changes
    )
    if old and not new:
        return "original"
    if new and not old:
        return "patched"
    return "unsupported"


def _decoded_state(role: str, data: Any) -> str:
    if role == "gameplay-aspect-controller":
        value = int(getattr(data, "m_Enabled", -1))
        return "original" if value == 1 else "patched" if value == 0 else "unsupported"
    if role == "gameplay-camera-fov":
        if bool(getattr(data, "orthographic", True)):
            return "unsupported"
        value = float(getattr(data, "field_of_view", -1.0))
        return "original" if abs(value - 60.0) < 0.0001 else "patched" if abs(value - _FOV_4X3) < 0.0001 else "unsupported"
    if role == "title-root":
        value = _pair(getattr(data, "m_SizeDelta", None))
        return "original" if _same_pair(value, (1920.0, 1080.0)) else "patched" if _same_pair(value, (1920.0, 1440.0)) else "unsupported"
    if role == "title-art":
        old = (
            _same_pair(_pair(getattr(data, "m_AnchorMin", None)), (0.0, 0.0))
            and _same_pair(_pair(getattr(data, "m_AnchorMax", None)), (1.0, 1.0))
            and _same_pair(_pair(getattr(data, "m_SizeDelta", None)), (0.0, 0.0))
        )
        new = (
            _same_pair(_pair(getattr(data, "m_AnchorMin", None)), (0.5, 0.5))
            and _same_pair(_pair(getattr(data, "m_AnchorMax", None)), (0.5, 0.5))
            and _same_pair(_pair(getattr(data, "m_SizeDelta", None)), (2560.0, 1440.0))
        )
        return "original" if old else "patched" if new else "unsupported"
    if role in ("title-canvas-scaler", "movie-canvas-scaler", "main-menu-canvas-scaler"):
        value = _pair(getattr(data, "m_ReferenceResolution", None))
        return "original" if _same_pair(value, (1920.0, 1080.0)) else "patched" if _same_pair(value, (1920.0, 1440.0)) else "unsupported"
    if role == "movie-canvas":
        value = _pair(getattr(data, "m_SizeDelta", None))
        return "original" if _same_pair(value, (1920.0, 1080.0)) else "patched" if _same_pair(value, (2560.0, 1440.0)) else "unsupported"
    if role == "movie-crop-mode":
        value = int(getattr(data, "m_AspectRatio", -1))
        return "original" if value == 2 else "patched" if value == 4 else "unsupported"
    return "unsupported"


def _target(entry: str, serialized: str, path_id: int, role: str, data: Any, raw: bytes) -> _Target:
    decoded = _decoded_state(role, data)
    encoded = _raw_state(role, raw)
    status = decoded if decoded == encoded else "unsupported"
    return _Target(entry, serialized, path_id, role, status)


def _inspect_bundle(entry: str, path: Path) -> list[_Target]:
    environment = bundle = None
    direct: list[_Target] = []
    gameplay_behaviours: dict[tuple[str, int], list[tuple[int, Any, bytes]]] = {}
    gameplay_cameras: dict[tuple[str, int], list[tuple[int, Any, bytes]]] = {}
    gameplay_orders: dict[tuple[str, int], tuple[int, ...]] = {}
    try:
        environment, bundle = _load_bundle(path)
        for serialized_name, serialized in bundle.files.items():
            if not hasattr(serialized, "objects"):
                continue
            for path_id, obj in serialized.objects.items():
                type_name = obj.type.name
                if type_name not in ("MonoBehaviour", "Camera", "RectTransform", "VideoPlayer"):
                    continue
                raw = obj.get_raw_data()
                try:
                    data = obj.read(check_read=False)
                except (KeyError, TypeError, ValueError):
                    continue
                game_object = _game_object(data)
                if game_object is None:
                    continue
                game_object_id, name = game_object
                key = (serialized_name, game_object_id)

                if name == "MainCamera" and type_name == "MonoBehaviour" and len(raw) == 32:
                    gameplay_behaviours.setdefault(key, []).append((path_id, data, raw))
                    gameplay_orders.setdefault(key, _component_order(data))
                    continue
                if name == "MainCamera" and type_name == "Camera":
                    gameplay_cameras.setdefault(key, []).append((path_id, data, raw))
                    gameplay_orders.setdefault(key, _component_order(data))
                    continue

                role: str | None = None
                if (
                    name == "All_Nut"
                    and type_name == "RectTransform"
                    and _parent_name(data) == "TitleView"
                ):
                    role = "title-root"
                elif name == "Img_BG_Title" and type_name == "RectTransform":
                    role = "title-art"
                elif name == "TitleView" and type_name == "MonoBehaviour" and hasattr(data, "m_ReferenceResolution"):
                    role = "title-canvas-scaler"
                elif name == "MovieCanvas" and type_name == "RectTransform":
                    role = "movie-canvas"
                elif name == "MovieCanvas" and type_name == "VideoPlayer":
                    role = "movie-crop-mode"
                elif name == "EventMovieView" and type_name == "MonoBehaviour" and hasattr(data, "m_ReferenceResolution"):
                    role = "movie-canvas-scaler"
                elif name == "MainMenuView" and type_name == "MonoBehaviour" and hasattr(data, "m_ReferenceResolution"):
                    role = "main-menu-canvas-scaler"
                if role is not None:
                    direct.append(_target(entry, serialized_name, path_id, role, data, raw))

        for key in sorted(gameplay_behaviours.keys() & gameplay_cameras.keys()):
            serialized_name, _game_object_id = key
            serialized = bundle.files[serialized_name]
            order = gameplay_orders.get(key, ())
            behaviours = {
                behaviour_id: (behaviour_data, behaviour_raw)
                for behaviour_id, behaviour_data, behaviour_raw in gameplay_behaviours[key]
            }
            # CameraAspectResize is the first of the final two compact script
            # components on MainCamera, immediately following AudioListener.
            # This component relationship distinguishes it from the adjacent
            # unrelated 32-byte MonoBehaviour without using either script's
            # revision-specific PathID.
            selected_behaviours: list[tuple[int, Any, bytes]] = []
            for index, component_id in enumerate(order):
                if component_id not in behaviours or not (0 < index < len(order) - 1):
                    continue
                previous = serialized.objects.get(order[index - 1])
                next_id = order[index + 1]
                if (
                    previous is not None
                    and previous.type.name == "AudioListener"
                    and next_id in behaviours
                ):
                    data, raw = behaviours[component_id]
                    selected_behaviours.append((component_id, data, raw))
            for behaviour_id, behaviour_data, behaviour_raw in selected_behaviours:
                direct.append(
                    _target(
                        entry,
                        serialized_name,
                        behaviour_id,
                        "gameplay-aspect-controller",
                        behaviour_data,
                        behaviour_raw,
                    )
                )
            for camera_id, camera_data, camera_raw in (
                gameplay_cameras[key] if selected_behaviours else []
            ):
                direct.append(
                    _target(
                        entry,
                        serialized_name,
                        camera_id,
                        "gameplay-camera-fov",
                        camera_data,
                        camera_raw,
                    )
                )
    except Exception:
        # Exhaustive fallback globs may contain bundles with unrelated layouts
        # that UnityPy cannot decode under this title's engine version.
        return []
    finally:
        del bundle
        del environment
        gc.collect()
    return direct


def _discover(extracted: dict[str, Path]) -> list[_Target]:
    found: list[_Target] = []
    for entry, path in _bundle_entries(extracted):
        # Inspect every candidate so a later duplicate cannot evade the
        # framework's fail-closed ambiguity check.
        found.extend(_inspect_bundle(entry, path))
    return found


def _analyse(extracted: dict[str, Path]) -> tuple[dict[str, Any], list[_Target]]:
    targets = _discover(extracted)
    by_role: dict[str, list[_Target]] = {}
    for target in targets:
        by_role.setdefault(target.role, []).append(target)
    states: list[str] = []
    rows: list[dict[str, Any]] = []
    for role in _EXPECTED_ROLES:
        matches = by_role.get(role, [])
        if not matches:
            state = "unsupported"
        elif len(matches) != 1:
            state = "ambiguous"
        elif matches[0].status not in ("original", "patched"):
            state = "unsupported"
        else:
            state = matches[0].status
        states.append(state)
        rows.append({"name": role, "state": state, "matches": len(matches)})
    if "ambiguous" in states:
        state = "ambiguous"
    elif "unsupported" in states:
        state = "unsupported"
    elif all(value == "patched" for value in states):
        state = "patched"
    else:
        state = "original"
    return {"state": state, "targets": rows}, targets


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Return compatibility and original/already-patched target states."""

    report, _targets = _analyse(extracted)
    return report


def _replacement_path(output_dir: Path, entry: str) -> Path:
    path = output_dir.joinpath(*entry.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _patch_bundle(source: Path, targets: list[_Target], output: Path) -> None:
    environment = bundle = None
    try:
        environment, bundle = _load_bundle(source)
        for target in targets:
            if target.status != "original":
                continue
            obj = bundle.files[target.serialized_file].objects[target.path_id]
            raw = bytearray(obj.get_raw_data())
            for change in _CHANGES[target.role]:
                end = change.offset + len(change.original)
                if raw[change.offset:end] != change.original:
                    raise PatchError(f"{target.role}: source bytes changed after probing")
                raw[change.offset:end] = change.replacement
            obj.set_raw_data(bytes(raw))
        output.write_bytes(bundle.save(packer="original"))
    finally:
        del bundle
        del environment
        gc.collect()

    verified = {
        (item.serialized_file, item.path_id): item.status
        for item in _inspect_bundle(targets[0].entry, output)
    }
    for target in targets:
        if verified.get((target.serialized_file, target.path_id)) != "patched":
            raise PatchError(f"{target.role}: replacement bundle verification failed")


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Emit replacements for every safely recognized original-state target."""

    report, targets = _analyse(extracted)
    if report["state"] not in ("original", "patched"):
        raise PatchError(f"Shin Chan core patch targets are {report['state']}")

    grouped: dict[str, list[_Target]] = {}
    for target in targets:
        if target.status == "original":
            grouped.setdefault(target.entry, []).append(target)

    replacements: dict[str, Path] = {}
    entry_map = _normal_entries(extracted)
    for entry, bundle_targets in grouped.items():
        source = entry_map[entry.lower()][1]
        output = _replacement_path(Path(output_dir), entry)
        _patch_bundle(source, bundle_targets, output)
        replacements[entry] = output
    return replacements
