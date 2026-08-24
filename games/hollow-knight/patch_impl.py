"""Target-driven 4:3 patch for the verified Hollow Knight Android port."""

from __future__ import annotations

import gc
import math
import struct
from pathlib import Path
from typing import Any


DATA_ENTRY = "assets/bin/Data/data.unity3d"
ARM64_ENTRY = "lib/arm64-v8a/libil2cpp.so"
ARMV7_ENTRY = "lib/armeabi-v7a/libil2cpp.so"
REQUIRED_ENTRIES = (DATA_ENTRY,)
SUPPORTED_NATIVE_ENTRIES = (ARM64_ENTRY, ARMV7_ENTRY)

SOURCE_ASPECT = 16.0 / 9.0
TARGET_ASPECT = 4.0 / 3.0
HUD_ORTHO_SOURCE = 8.710663795471191
HUD_ORTHO_TARGET = HUD_ORTHO_SOURCE * SOURCE_ASPECT / TARGET_ASPECT
HUD_CANVAS_SOURCE_Y = 6.6
HUD_CANVAS_TARGET_Y = HUD_CANVAS_SOURCE_Y + HUD_ORTHO_TARGET - HUD_ORTHO_SOURCE
CAMERA_LIMIT_SOURCE = 8.300000190734863
CAMERA_LIMIT_TARGET = CAMERA_LIMIT_SOURCE * SOURCE_ASPECT / TARGET_ASPECT
REFERENCE_UI_HEIGHT = 1080.0

TOP_TOUCH_BUTTONS = frozenset(
    {
        "joystick 1 button 4",
        "joystick 1 button 5",
        "joystick 1 button 6",
        "joystick 1 button 7",
        "joystick 1 button 8",
        "joystick 1 button 9",
    }
)


class PatchError(RuntimeError):
    """The supplied entries do not contain a safely recognizable target."""


def _unitypy():
    try:
        import UnityPy  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency error is user-facing
        raise PatchError("UnityPy is required for the Hollow Knight patch") from exc
    return UnityPy


def _close_unity(*objects: Any) -> None:
    for obj in objects:
        del obj
    gc.collect()


def _bundle_file(environment: Any) -> Any:
    files = list(environment.files.values())
    if len(files) != 1 or not hasattr(files[0], "files"):
        raise PatchError("data.unity3d is not the expected single UnityFS bundle")
    return files[0]


def _transform_path(transform: Any) -> str:
    names = [transform.m_GameObject.read().m_Name]
    seen: set[int] = set()
    while transform.m_Father and transform.m_Father.path_id:
        if transform.m_Father.path_id in seen:
            raise PatchError("Unity Transform hierarchy contains a cycle")
        seen.add(transform.m_Father.path_id)
        transform = transform.m_Father.read()
        names.append(transform.m_GameObject.read().m_Name)
    return "/".join(reversed(names))


def _game_object_path(game_object: Any) -> str:
    assets_file = game_object.object_reader.assets_file
    for component in game_object.m_Component:
        reader = assets_file.objects.get(component.component.path_id)
        if reader and reader.type.name in ("Transform", "RectTransform"):
            return _transform_path(reader.read())
    raise PatchError(f"GameObject {game_object.m_Name!r} has no Transform")


def _near(value: float, expected: float, tolerance: float = 1e-4) -> bool:
    return math.isclose(float(value), expected, rel_tol=0.0, abs_tol=tolerance)


def _value_state(value: float, source: float, target: float) -> str:
    if _near(value, source):
        return "original"
    if _near(value, target):
        return "patched"
    return "unsupported"


def _target(name: str, state: str, **details: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "state": state}
    result.update(details)
    return result


def _overall(targets: list[dict[str, Any]]) -> str:
    states = {target["state"] for target in targets}
    if "ambiguous" in states:
        return "ambiguous"
    if "unsupported" in states:
        return "unsupported"
    if states == {"patched"}:
        return "patched"
    # A recognized, partially patched input is safely finishable.
    return "original"


def _path_readers(assets_file: Any, type_name: str, path: str) -> list[Any]:
    matches: list[Any] = []
    for reader in assets_file.objects.values():
        if reader.type.name != type_name:
            continue
        try:
            if type_name in ("Transform", "RectTransform"):
                candidate = _transform_path(reader.read())
            else:
                candidate = _game_object_path(reader.read().m_GameObject.read())
        except Exception:
            continue
        if candidate == path:
            matches.append(reader)
    return matches


def _unity_targets(path: Path) -> list[dict[str, Any]]:
    UnityPy = _unitypy()
    environment = UnityPy.load(str(path))
    bundle = _bundle_file(environment)
    targets: list[dict[str, Any]] = []
    try:
        for asset_name in ("level1", "resources.assets"):
            assets_file = bundle.files.get(asset_name)
            if assets_file is None:
                targets.append(_target(f"{asset_name}: assets file", "unsupported"))
                continue

            cameras = _path_readers(assets_file, "Camera", "_GameCameras/HudCamera")
            if len(cameras) != 1:
                state = "ambiguous" if len(cameras) > 1 else "unsupported"
                targets.append(
                    _target(f"{asset_name}: HUD camera", state, matches=len(cameras))
                )
            else:
                try:
                    value = cameras[0].read_typetree()["orthographic size"]
                    state = _value_state(value, HUD_ORTHO_SOURCE, HUD_ORTHO_TARGET)
                    targets.append(
                        _target(f"{asset_name}: HUD camera", state, value=float(value))
                    )
                except Exception as exc:
                    targets.append(
                        _target(f"{asset_name}: HUD camera", "unsupported", reason=str(exc))
                    )

            canvases = _path_readers(
                assets_file, "Transform", "_GameCameras/HudCamera/Hud Canvas"
            )
            if len(canvases) != 1:
                state = "ambiguous" if len(canvases) > 1 else "unsupported"
                targets.append(
                    _target(f"{asset_name}: HUD canvas", state, matches=len(canvases))
                )
            else:
                try:
                    value = canvases[0].read_typetree()["m_LocalPosition"]["y"]
                    state = _value_state(value, HUD_CANVAS_SOURCE_Y, HUD_CANVAS_TARGET_Y)
                    targets.append(
                        _target(f"{asset_name}: HUD canvas", state, value=float(value))
                    )
                except Exception as exc:
                    targets.append(
                        _target(f"{asset_name}: HUD canvas", "unsupported", reason=str(exc))
                    )

        level1 = bundle.files.get("level1")
        if level1 is None:
            targets.append(_target("touch controls", "unsupported"))
        else:
            found: dict[str, list[Any]] = {name: [] for name in TOP_TOUCH_BUTTONS}
            for reader in level1.objects.values():
                if reader.type.name != "RectTransform":
                    continue
                try:
                    transform = reader.read()
                    name = transform.m_GameObject.read().m_Name
                    path_name = _transform_path(transform)
                except Exception:
                    continue
                if name in found and path_name.startswith("_GameManager/_TCKCanvas/"):
                    found[name].append(reader)

            for name in sorted(TOP_TOUCH_BUTTONS):
                readers = found[name]
                target_name = f"level1: touch control {name}"
                if len(readers) != 1:
                    state = "ambiguous" if len(readers) > 1 else "unsupported"
                    targets.append(_target(target_name, state, matches=len(readers)))
                    continue
                try:
                    tree = readers[0].read_typetree()
                    min_y = float(tree["m_AnchorMin"]["y"])
                    max_y = float(tree["m_AnchorMax"]["y"])
                    if _near(min_y, 0.0) and _near(max_y, 0.0):
                        state = "original"
                    elif _near(min_y, 1.0) and _near(max_y, 1.0):
                        state = "patched"
                    else:
                        state = "unsupported"
                    targets.append(
                        _target(target_name, state, anchor_min_y=min_y, anchor_max_y=max_y)
                    )
                except Exception as exc:
                    targets.append(_target(target_name, "unsupported", reason=str(exc)))
    finally:
        _close_unity(bundle, environment)
    return targets


def _float_offsets(data: bytes | bytearray, value: float) -> list[int]:
    needle = struct.pack("<f", value)
    offsets: list[int] = []
    cursor = 0
    while True:
        offset = data.find(needle, cursor)
        if offset < 0:
            return offsets
        offsets.append(offset)
        cursor = offset + len(needle)


def _literal_group(
    data: bytes | bytearray,
    name: str,
    source: float,
    target: float,
    expected: int,
) -> tuple[dict[str, Any], list[int]]:
    source_offsets = _float_offsets(data, source)
    target_offsets = _float_offsets(data, target)
    if len(source_offsets) == expected and not target_offsets:
        return _target(name, "original", matches=expected), source_offsets
    if len(target_offsets) == expected and not source_offsets:
        return _target(name, "patched", matches=expected), target_offsets
    if source_offsets and target_offsets:
        return _target(
            name,
            "ambiguous",
            original_matches=len(source_offsets),
            patched_matches=len(target_offsets),
        ), []
    return _target(
        name,
        "unsupported",
        original_matches=len(source_offsets),
        patched_matches=len(target_offsets),
    ), []


def _armv7_bound_cluster(
    data: bytes | bytearray,
) -> tuple[dict[str, Any], list[tuple[int, float, float]]]:
    """Find the CameraController literal pool by its 1-negative/7-positive cluster."""

    radius = 0x4000
    candidates: list[tuple[str, list[tuple[int, float, float]]]] = []
    for state, negative, positive, replacement_negative, replacement_positive in (
        (
            "original",
            -CAMERA_LIMIT_SOURCE,
            CAMERA_LIMIT_SOURCE,
            -CAMERA_LIMIT_TARGET,
            CAMERA_LIMIT_TARGET,
        ),
        (
            "patched",
            -CAMERA_LIMIT_TARGET,
            CAMERA_LIMIT_TARGET,
            -CAMERA_LIMIT_SOURCE,
            CAMERA_LIMIT_SOURCE,
        ),
    ):
        positive_offsets = _float_offsets(data, positive)
        opposite_positive_offsets = _float_offsets(data, replacement_positive)
        for negative_offset in _float_offsets(data, negative):
            start = max(0, negative_offset - radius)
            end = min(len(data), negative_offset + radius)
            nearby = [offset for offset in positive_offsets if start <= offset < end]
            opposite = [
                offset for offset in opposite_positive_offsets if start <= offset < end
            ]
            if len(nearby) == 7 and not opposite:
                edits = [(negative_offset, negative, replacement_negative)]
                edits.extend((offset, positive, replacement_positive) for offset in nearby)
                candidates.append((state, edits))

    # Overlapping windows around the same literal pool describe one candidate.
    unique: dict[tuple[int, ...], tuple[str, list[tuple[int, float, float]]]] = {}
    for state, edits in candidates:
        unique[tuple(sorted(offset for offset, _, _ in edits))] = (state, edits)
    candidates = list(unique.values())
    if len(candidates) == 1:
        state, edits = candidates[0]
        return _target("armeabi-v7a: camera bounds", state, matches=8), edits
    if len(candidates) > 1:
        return _target(
            "armeabi-v7a: camera bounds", "ambiguous", matches=len(candidates)
        ), []
    return _target("armeabi-v7a: camera bounds", "unsupported", matches=0), []


def _native_targets(entry: str, path: Path) -> list[dict[str, Any]]:
    data = path.read_bytes()
    architecture = "arm64-v8a" if entry == ARM64_ENTRY else "armeabi-v7a"
    aspect_expected = 1 if entry == ARM64_ENTRY else 2
    aspect, _ = _literal_group(
        data,
        f"{architecture}: viewport aspect",
        SOURCE_ASPECT,
        TARGET_ASPECT,
        aspect_expected,
    )
    if entry == ARM64_ENTRY:
        lower, _ = _literal_group(
            data,
            "arm64-v8a: lower camera bound",
            -CAMERA_LIMIT_SOURCE,
            -CAMERA_LIMIT_TARGET,
            1,
        )
        upper, _ = _literal_group(
            data,
            "arm64-v8a: upper camera bound",
            CAMERA_LIMIT_SOURCE,
            CAMERA_LIMIT_TARGET,
            1,
        )
        return [aspect, lower, upper]
    bounds, _ = _armv7_bound_cluster(data)
    return [aspect, bounds]


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Inspect extracted APK entries without relying on APK/version hashes."""

    missing = [
        entry
        for entry in REQUIRED_ENTRIES
        if extracted.get(entry) is None or not Path(extracted[entry]).is_file()
    ]
    if missing:
        targets = [_target(entry, "unsupported", reason="required entry missing") for entry in missing]
        return {"state": "unsupported", "targets": targets}

    targets: list[dict[str, Any]] = []
    try:
        targets.extend(_unity_targets(extracted[DATA_ENTRY]))
    except Exception as exc:
        targets.append(_target("Unity data bundle", "unsupported", reason=str(exc)))
    native_entries = [
        entry
        for entry in SUPPORTED_NATIVE_ENTRIES
        if extracted.get(entry) is not None and Path(extracted[entry]).is_file()
    ]
    if not native_entries:
        targets.append(
            _target(
                "supported IL2CPP library",
                "unsupported",
                reason="APK contains neither ARM64 nor ARMv7 libil2cpp.so",
            )
        )
    for entry in native_entries:
        try:
            targets.extend(_native_targets(entry, extracted[entry]))
        except Exception as exc:
            targets.append(_target(entry, "unsupported", reason=str(exc)))
    return {"state": _overall(targets), "targets": targets}


def _patch_unity(source: Path, destination: Path) -> bool:
    UnityPy = _unitypy()
    environment = UnityPy.load(str(source))
    bundle = _bundle_file(environment)
    changed = False
    try:
        for asset_name in ("level1", "resources.assets"):
            assets_file = bundle.files[asset_name]
            camera = _path_readers(assets_file, "Camera", "_GameCameras/HudCamera")[0]
            tree = camera.read_typetree()
            if _near(tree["orthographic size"], HUD_ORTHO_SOURCE):
                tree["orthographic size"] = HUD_ORTHO_TARGET
                camera.save_typetree(tree)
                changed = True

            canvas = _path_readers(
                assets_file, "Transform", "_GameCameras/HudCamera/Hud Canvas"
            )[0]
            tree = canvas.read_typetree()
            if _near(tree["m_LocalPosition"]["y"], HUD_CANVAS_SOURCE_Y):
                tree["m_LocalPosition"]["y"] = HUD_CANVAS_TARGET_Y
                canvas.save_typetree(tree)
                changed = True

        level1 = bundle.files["level1"]
        for reader in level1.objects.values():
            if reader.type.name != "RectTransform":
                continue
            transform = reader.read()
            name = transform.m_GameObject.read().m_Name
            if name not in TOP_TOUCH_BUTTONS:
                continue
            if not _transform_path(transform).startswith("_GameManager/_TCKCanvas/"):
                continue
            tree = reader.read_typetree()
            if _near(tree["m_AnchorMin"]["y"], 0.0) and _near(
                tree["m_AnchorMax"]["y"], 0.0
            ):
                tree["m_AnchorMin"]["y"] = 1.0
                tree["m_AnchorMax"]["y"] = 1.0
                tree["m_AnchoredPosition"]["y"] -= REFERENCE_UI_HEIGHT
                reader.save_typetree(tree)
                changed = True
        if changed:
            destination.write_bytes(bundle.save(packer="original"))
    finally:
        _close_unity(bundle, environment)
    return changed


def _replace_offsets(data: bytearray, offsets: list[int], target: float) -> None:
    replacement = struct.pack("<f", target)
    for offset in offsets:
        data[offset : offset + 4] = replacement


def _patch_native(source: Path, destination: Path, entry: str) -> bool:
    data = bytearray(source.read_bytes())
    changed = False
    aspect_expected = 1 if entry == ARM64_ENTRY else 2
    aspect, offsets = _literal_group(
        data,
        "viewport aspect",
        SOURCE_ASPECT,
        TARGET_ASPECT,
        aspect_expected,
    )
    if aspect["state"] == "original":
        _replace_offsets(data, offsets, TARGET_ASPECT)
        changed = True

    if entry == ARM64_ENTRY:
        for source_value, target_value, label in (
            (-CAMERA_LIMIT_SOURCE, -CAMERA_LIMIT_TARGET, "lower bound"),
            (CAMERA_LIMIT_SOURCE, CAMERA_LIMIT_TARGET, "upper bound"),
        ):
            target, offsets = _literal_group(data, label, source_value, target_value, 1)
            if target["state"] == "original":
                _replace_offsets(data, offsets, target_value)
                changed = True
    else:
        bounds, edits = _armv7_bound_cluster(data)
        if bounds["state"] == "original":
            for offset, _old, new in edits:
                data[offset : offset + 4] = struct.pack("<f", new)
            changed = True

    if changed:
        destination.write_bytes(data)
    return changed


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Write replacement entries for every recognized original target."""

    result = probe(extracted)
    if result["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"Hollow Knight patch targets are {result['state']}")
    if result["state"] == "patched":
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    replacements: dict[str, Path] = {}
    data_output = output_dir / "data.unity3d"
    if _patch_unity(extracted[DATA_ENTRY], data_output):
        replacements[DATA_ENTRY] = data_output

    for entry, filename in (
        (ARM64_ENTRY, "libil2cpp-arm64-v8a.so"),
        (ARMV7_ENTRY, "libil2cpp-armeabi-v7a.so"),
    ):
        if extracted.get(entry) is None or not Path(extracted[entry]).is_file():
            continue
        destination = output_dir / filename
        if _patch_native(extracted[entry], destination, entry):
            replacements[entry] = destination

    verification_input = dict(extracted)
    verification_input.update(replacements)
    verification = probe(verification_input)
    if verification["state"] != "patched":
        raise PatchError(f"post-patch verification failed: {verification['state']}")
    return replacements
