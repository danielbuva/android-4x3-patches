"""Target-driven 4:3 patches for the IL2CPP and Mono Hollow Knight ports."""

from __future__ import annotations

import gc
import math
import struct
from pathlib import Path
from typing import Any


DATA_ENTRY = "assets/bin/Data/data.unity3d"
MONO_ENTRY = "assets/bin/Data/Managed/Assembly-CSharp.dll"
ARM64_ENTRY = "lib/arm64-v8a/libil2cpp.so"
ARMV7_ENTRY = "lib/armeabi-v7a/libil2cpp.so"
REQUIRED_ENTRIES = (DATA_ENTRY,)
SUPPORTED_NATIVE_ENTRIES = (ARM64_ENTRY, ARMV7_ENTRY)

SOURCE_ASPECT = 16.0 / 9.0
TARGET_ASPECT = 4.0 / 3.0
HUD_ORTHO_SOURCE = 8.710663795471191
HUD_ORTHO_TARGET = HUD_ORTHO_SOURCE * SOURCE_ASPECT / TARGET_ASPECT
# The Mono port's inventory prefab restores its own 16:9 transform hierarchy at
# runtime. Give the dedicated HUD camera enough horizontal room for that prefab,
# then compensate the gameplay HUD scale below. This does not affect the world
# camera or gameplay framing.
MONO_HUD_ORTHO_V4 = HUD_ORTHO_TARGET * SOURCE_ASPECT / TARGET_ASPECT
# The central frame fit at V4, but peripheral pane artwork still crossed the
# physical sides. An additional HUD-camera-only margin contains those pieces.
MONO_INVENTORY_EXTRA_FIT = 1.25
MONO_HUD_ORTHO_V5 = MONO_HUD_ORTHO_V4 * MONO_INVENTORY_EXTRA_FIT
# The active Mono gameplay scene has its own HUD-camera copy. Expanding that
# camera once to 4:3 preserves the original horizontal span; the older V4/V5
# values zoomed the HUD out a second time to compensate for the inventory.
MONO_HUD_ORTHO_TARGET = HUD_ORTHO_TARGET
HUD_CANVAS_SOURCE_X = -8.710000038146973
HUD_CANVAS_SOURCE_Y = 6.6
IL2CPP_HUD_CANVAS_TARGET_Y = HUD_CANVAS_SOURCE_Y + HUD_ORTHO_TARGET - HUD_ORTHO_SOURCE
# Earlier Mono implementations expanded the HUD camera, then briefly enlarged
# the world-space HUD without fitting the inventory. The final layout expands
# the dedicated camera again and compensates the gameplay HUD scale and
# placement. Keeping every released value here lets prior APKs migrate safely.
MONO_HUD_V1_CANVAS_Y = IL2CPP_HUD_CANVAS_TARGET_Y
MONO_HUD_V2_CANVAS_X = HUD_CANVAS_SOURCE_X + 1.2
MONO_HUD_V2_CANVAS_Y = MONO_HUD_V1_CANVAS_Y + 1.1
# Keep the health frame's decorative left edge on-screen. The canvas contains
# the left-side gameplay HUD; right-side mobile controls live on another canvas.
MONO_HUD_V3_CANVAS_X = HUD_CANVAS_SOURCE_X + 0.8
MONO_HUD_V3_CANVAS_Y = 10.8
MONO_HUD_V4_CANVAS_X = MONO_HUD_V3_CANVAS_X * SOURCE_ASPECT / TARGET_ASPECT
MONO_HUD_V4_CANVAS_Y = MONO_HUD_V3_CANVAS_Y * SOURCE_ASPECT / TARGET_ASPECT
MONO_HUD_V5_CANVAS_X = MONO_HUD_V4_CANVAS_X * MONO_INVENTORY_EXTRA_FIT
MONO_HUD_V5_CANVAS_Y = MONO_HUD_V4_CANVAS_Y * MONO_INVENTORY_EXTRA_FIT
# After the world camera is fitted independently, return the health HUD to the
# inset position used by the last visually verified layout. This keeps the soul
# vessel, masks, and geo counter clear of every physical display edge.
MONO_HUD_CANVAS_TARGET_X = -9.25
MONO_HUD_CANVAS_TARGET_Y = 9.7
MONO_HUD_SCALE_SOURCE = 1.0
MONO_HUD_SCALE_V2 = SOURCE_ASPECT / TARGET_ASPECT
MONO_HUD_SCALE_V4 = SOURCE_ASPECT / TARGET_ASPECT
MONO_HUD_SCALE_V5 = MONO_HUD_SCALE_V4 * MONO_INVENTORY_EXTRA_FIT
MONO_HUD_SCALE_TARGET = MONO_HUD_SCALE_SOURCE
UI_REFERENCE_HEIGHT_SOURCE = 1080.0
UI_REFERENCE_HEIGHT_TARGET = 1440.0
HUD_FSM_SCALE_TIME = 0.15000000596046448
INVENTORY_SCALE_V1 = TARGET_ASPECT / SOURCE_ASPECT
INVENTORY_SCALE_V2 = INVENTORY_SCALE_V1 * TARGET_ASPECT / SOURCE_ASPECT
# The inventory is reparented beneath the animated HUD canvas at runtime, so
# enlarging that canvas to preserve the gameplay HUD also enlarges the menu and
# cancels the wider HUD-camera fit. Counter-scale the inventory root by the
# 16:9-to-4:3 ratio. Unlike scaling individual panes, this keeps every page,
# border, cursor, and transition in one uniform coordinate system.
INVENTORY_SCALE_TARGET = 1.0
INVENTORY_SOURCE_POSITION = (-4.050000190734863, 7.550000190734863)
INVENTORY_V1_POSITION = tuple(
    value * INVENTORY_SCALE_V1 for value in INVENTORY_SOURCE_POSITION
)
INVENTORY_V2_POSITION = tuple(
    value * INVENTORY_SCALE_V2 for value in INVENTORY_SOURCE_POSITION
)
INVENTORY_TARGET_POSITION = tuple(
    value * INVENTORY_SCALE_TARGET for value in INVENTORY_SOURCE_POSITION
)
INVENTORY_CHILD_SCALE_V1 = TARGET_ASPECT / SOURCE_ASPECT
INVENTORY_CHILD_SCALE_TARGET = 1.0
INVENTORY_CHILDREN = (
    "Border",
    "Charms",
    "Inv",
    "Journal",
    "Map",
    "Map Key",
)
INVENTORY_RUNTIME_SCALE_V1 = TARGET_ASPECT / SOURCE_ASPECT
INVENTORY_RUNTIME_SCALE = 1.0
# The previous runtime correction was compensating for the old, cropped camera
# projection. With the world and HUD cameras now fitted independently, the
# prefab's original X/Y values center it exactly on the 4:3 display.
INVENTORY_RUNTIME_POSITION_V1 = (-2.90, 5.44, 40.4)
INVENTORY_RUNTIME_POSITION = (
    INVENTORY_SOURCE_POSITION[0],
    INVENTORY_SOURCE_POSITION[1],
    40.4,
)
INVENTORY_RUNTIME_TARGET_NAME = "Mono runtime inventory fit"
INVENTORY_BACKDROPS = {
    "backboard": (321.67681884765625, 196.77186584472656),
}
INVENTORY_BACKDROP_SCALE_MULTIPLIER_V1 = 3.25
# The first full-frame backdrop left a narrow uncovered strip at the physical
# top edge. A small uniform enlargement closes it without changing opacity or
# the inventory artwork's independent centered transform.
INVENTORY_BACKDROP_SCALE_MULTIPLIER = 3.4
INVENTORY_BACKDROP_SOURCE_Y = {
    "backboard": -7.519999980926514,
}
INVENTORY_BACKDROP_Y_OFFSET = 1.0
WORLD_CAMERA_ASSETS = ("resources.assets", "level2")
WORLD_NATIVE_RESOLUTION_SOURCE = (1920, 1080)
WORLD_NATIVE_RESOLUTION_TARGET = (1920, 1440)
WORLD_FORCE_RESOLUTION_SOURCE = (1280.0, 720.0)
WORLD_FORCE_RESOLUTION_TARGET = (1280.0, 960.0)
WORLD_ZOOM_SOURCE = 1.0
# The Mono port otherwise preserves its 16:9 height and discards one quarter
# of the horizontal world on a 4:3 display. A 0.75 zoom factor preserves the
# original 29.2-unit width and exposes the corresponding extra vertical area.
WORLD_ZOOM_TARGET = TARGET_ASPECT / SOURCE_ASPECT
CAMERA_LIMIT_SOURCE = 8.300000190734863
CAMERA_LIMIT_TARGET = CAMERA_LIMIT_SOURCE * SOURCE_ASPECT / TARGET_ASPECT
REFERENCE_UI_HEIGHT = 1080.0
REFERENCE_UI_HALF_HEIGHT = REFERENCE_UI_HEIGHT / 2.0
MONO_TOUCH_SOURCE_POSITION_Y = 125.0
MONO_TOUCH_V1_POSITION_Y = MONO_TOUCH_SOURCE_POSITION_Y - REFERENCE_UI_HALF_HEIGHT
MONO_TOUCH_TARGET_POSITION_Y = -125.0

DISCLAIMER_SCALE_SOURCE = 0.5492802262306213
# The source text is wider than its nominal 1920-pixel canvas. Leave a small
# 5% margin when Expand mode fits that canvas to the 4:3 display width.
DISCLAIMER_SCALE_TARGET = (1920.0 * 0.95) / 3758.111083984375

MONO_TOUCH_BUTTONS = frozenset(
    {
        "TouchChat",
        "TouchMenu",
        "TouchMod",
        "TouchQuickMap",
        "TouchSelect",
        "TouchSuperDash",
    }
)

MANAGED_ASPECT_METHODS = (
    ("ForceCameraAspect", "Awake", 1, 1),
    ("ForceCameraAspect", "AutoScaleViewport", 1, 2),
    ("ForceCameraAspectLite", "AutoScaleViewport", 1, 1),
)

MANAGED_BOUND_METHODS = (
    ("CameraController", "LateUpdate", 1, 2),
    ("CameraController", "LockToArea", 1, 1),
    ("CameraController", "KeepWithinSceneBounds", 2, 4),
    ("CameraController", "IsAtSceneBounds", 1, 1),
    ("CameraController", "GetTilemapInfo", 1, 1),
    ("CameraLockArea", "ValidateBounds", 1, 1),
    ("CameraTarget", "Update", 1, 4),
    ("CameraTarget", "EnterLockZone", 1, 1),
    ("CameraTarget", "ExitLockZone", 1, 1),
)

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
                    state = _value_state(
                        value, HUD_CANVAS_SOURCE_Y, IL2CPP_HUD_CANVAS_TARGET_Y
                    )
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


def _script_component_reader(
    bundle: Any, assets_file: Any, game_object_path: str, class_name: str
) -> list[Any]:
    """Find a component by hierarchy and MonoScript identity.

    This Unity build stores MonoScripts in globalgamemanagers.assets and omits
    embedded type trees for those components. Resolving the script pointer is
    still semantic and avoids depending on a component path ID or file offset.
    """

    global_assets = bundle.files.get("globalgamemanagers.assets")
    if global_assets is None:
        return []
    transforms = _path_readers(assets_file, "RectTransform", game_object_path)
    transforms.extend(_path_readers(assets_file, "Transform", game_object_path))
    if len(transforms) != 1:
        return []
    game_object = transforms[0].read().m_GameObject.read()
    matches: list[Any] = []
    for component in game_object.m_Component:
        reader = assets_file.objects.get(component.component.path_id)
        if reader is None or reader.type.name != "MonoBehaviour":
            continue
        raw = reader.get_raw_data()
        if len(raw) < 28:
            continue
        script_file_id, script_path_id = struct.unpack_from("<iq", raw, 16)
        if script_file_id != 1:
            continue
        script_reader = global_assets.objects.get(script_path_id)
        if script_reader is None or script_reader.type.name != "MonoScript":
            continue
        try:
            if script_reader.read().m_ClassName == class_name:
                matches.append(reader)
        except Exception:
            continue
    return matches


def _disclaimer_scaler_state(raw: bytes | bytearray) -> tuple[str, int | None]:
    # Expand mode already preserves the full 1920-pixel horizontal reference
    # on a 4:3 display; the child description is the part that needs fitting.
    expected = struct.pack(
        "<iffffif", 1, 100.0, 1.0, 1920.0, 1080.0, 1, 0.0
    )
    offsets = _byte_offsets(raw, expected)
    if len(offsets) == 1:
        return "patched", offsets[0]
    if len(offsets) > 1:
        return "ambiguous", None
    return "unsupported", None


def _ui_scaler_state(raw: bytes | bytearray) -> tuple[str, int | None]:
    """Recognize the gameplay/menu CanvasScaler reference-resolution field."""

    candidates: list[tuple[str, int]] = []
    for width_offset in _float_offsets(raw, 1920.0):
        height_offset = width_offset + 4
        if width_offset < 12 or height_offset + 12 > len(raw):
            continue
        scale_mode = struct.unpack_from("<i", raw, width_offset - 12)[0]
        scale_factor, reference_ppu = struct.unpack_from(
            "<ff", raw, width_offset - 8
        )
        height = struct.unpack_from("<f", raw, height_offset)[0]
        mode, match = struct.unpack_from("<if", raw, height_offset + 4)
        if (
            scale_mode != 1
            or not math.isfinite(scale_factor)
            or scale_factor <= 0.0
            or not _near(reference_ppu, 1.0)
            or mode != 1
            or not _near(match, 0.0)
        ):
            continue
        state = _value_state(
            height, UI_REFERENCE_HEIGHT_SOURCE, UI_REFERENCE_HEIGHT_TARGET
        )
        if state != "unsupported":
            candidates.append((state, height_offset))
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return "ambiguous", None
    return "unsupported", None


def _mono_hud_layout_state(camera_tree: dict[str, Any], canvas_tree: dict[str, Any]) -> str:
    camera_size = float(camera_tree["orthographic size"])
    position = canvas_tree["m_LocalPosition"]
    scale = canvas_tree["m_LocalScale"]
    recognized = (
        any(
            _near(camera_size, value)
            for value in (
                HUD_ORTHO_SOURCE,
                HUD_ORTHO_TARGET,
                MONO_HUD_ORTHO_V4,
                MONO_HUD_ORTHO_V5,
                MONO_HUD_ORTHO_TARGET,
            )
        )
        and any(
            _near(position["x"], value)
            for value in (
                HUD_CANVAS_SOURCE_X,
                MONO_HUD_V2_CANVAS_X,
                MONO_HUD_V3_CANVAS_X,
                MONO_HUD_V4_CANVAS_X,
                MONO_HUD_V5_CANVAS_X,
                MONO_HUD_CANVAS_TARGET_X,
            )
        )
        and any(
            _near(position["y"], value)
            for value in (
                HUD_CANVAS_SOURCE_Y,
                MONO_HUD_V1_CANVAS_Y,
                MONO_HUD_V2_CANVAS_Y,
                MONO_HUD_V3_CANVAS_Y,
                MONO_HUD_V4_CANVAS_Y,
                MONO_HUD_V5_CANVAS_Y,
                MONO_HUD_CANVAS_TARGET_Y,
            )
        )
        and all(
            any(
                _near(scale[axis], value)
                for value in (
                    MONO_HUD_SCALE_SOURCE,
                    MONO_HUD_SCALE_V2,
                    MONO_HUD_SCALE_V4,
                    MONO_HUD_SCALE_V5,
                    MONO_HUD_SCALE_TARGET,
                )
            )
            for axis in ("x", "y")
        )
        and _near(scale["z"], 1.0)
    )
    if not recognized:
        return "unsupported"
    final = (
        _near(camera_size, MONO_HUD_ORTHO_TARGET)
        and _near(position["x"], MONO_HUD_CANVAS_TARGET_X)
        and _near(position["y"], MONO_HUD_CANVAS_TARGET_Y)
        and _near(scale["x"], MONO_HUD_SCALE_TARGET)
        and _near(scale["y"], MONO_HUD_SCALE_TARGET)
    )
    return "patched" if final else "original"


def _hud_fsm_scale_pattern(value: float) -> bytes:
    return (
        b"\x00"
        + struct.pack("<fff", value, value, value)
        + b"\x00"
        + struct.pack("<f", HUD_FSM_SCALE_TIME)
        + b"\x01Scale Time"
    )


def _mono_hud_fsm_state(raw: bytes | bytearray) -> tuple[str, int | None]:
    """Locate the Slide Out FSM's Come In scale without decoding game data."""

    if raw.count(b"Slide Out") != 1 or raw.count(b"iTweenScaleTo") < 1:
        return "unsupported", None
    prior = [
        offset
        for value in (MONO_HUD_SCALE_V4, MONO_HUD_SCALE_V5)
        for offset in _byte_offsets(raw, _hud_fsm_scale_pattern(value))
    ]
    target = _byte_offsets(raw, _hud_fsm_scale_pattern(MONO_HUD_SCALE_TARGET))
    if len(prior) == 1 and not target:
        return "original", prior[0]
    if len(target) == 1 and not prior:
        return "patched", target[0]
    if prior or target:
        return "ambiguous", None
    return "unsupported", None


def _mono_inventory_layout_state(tree: dict[str, Any]) -> str:
    position = tree["m_LocalPosition"]
    scale = tree["m_LocalScale"]
    recognized = (
        all(
            any(
                _near(position[axis], value)
                for value in (
                    INVENTORY_SOURCE_POSITION[index],
                    INVENTORY_V1_POSITION[index],
                    INVENTORY_V2_POSITION[index],
                    INVENTORY_TARGET_POSITION[index],
                )
            )
            for index, axis in enumerate(("x", "y"))
        )
        and all(
            any(
                _near(scale[axis], value)
                for value in (
                    1.0,
                    INVENTORY_SCALE_V1,
                    INVENTORY_SCALE_V2,
                    INVENTORY_SCALE_TARGET,
                )
            )
            for axis in ("x", "y")
        )
        and _near(scale["z"], 1.0)
    )
    if not recognized:
        return "unsupported"
    final = (
        _near(position["x"], INVENTORY_TARGET_POSITION[0])
        and _near(position["y"], INVENTORY_TARGET_POSITION[1])
        and _near(scale["x"], INVENTORY_SCALE_TARGET)
        and _near(scale["y"], INVENTORY_SCALE_TARGET)
    )
    return "patched" if final else "original"


def _mono_inventory_child_state(tree: dict[str, Any]) -> str:
    scale = tree["m_LocalScale"]
    if (
        _near(scale["x"], INVENTORY_CHILD_SCALE_TARGET)
        and _near(scale["y"], INVENTORY_CHILD_SCALE_TARGET)
    ):
        return "patched"
    if (
        _near(scale["x"], INVENTORY_CHILD_SCALE_V1)
        and _near(scale["y"], INVENTORY_CHILD_SCALE_V1)
    ):
        return "original"
    return "unsupported"


def _mono_inventory_backdrop_state(tree: dict[str, Any], name: str) -> str:
    source_x, source_y = INVENTORY_BACKDROPS[name]
    scale = tree["m_LocalScale"]
    target_x = source_x * INVENTORY_BACKDROP_SCALE_MULTIPLIER
    target_y = source_y * INVENTORY_BACKDROP_SCALE_MULTIPLIER
    position_y = float(tree["m_LocalPosition"]["y"])
    source_position_y = INVENTORY_BACKDROP_SOURCE_Y[name]
    target_scale = _near(scale["x"], target_x) and _near(scale["y"], target_y)
    source_scale = _near(scale["x"], source_x) and _near(scale["y"], source_y)
    prior_scale = _near(
        scale["x"], source_x / INVENTORY_RUNTIME_SCALE
    ) and _near(scale["y"], source_y / INVENTORY_RUNTIME_SCALE)
    prior_full_frame_scale = _near(
        scale["x"], source_x * INVENTORY_BACKDROP_SCALE_MULTIPLIER_V1
    ) and _near(
        scale["y"], source_y * INVENTORY_BACKDROP_SCALE_MULTIPLIER_V1
    )
    target_position_y = source_position_y + INVENTORY_BACKDROP_Y_OFFSET
    if target_scale and _near(position_y, target_position_y):
        return "patched"
    if (source_scale or prior_scale) and _near(position_y, source_position_y):
        return "original"
    if prior_full_frame_scale and _near(position_y, target_position_y):
        return "original"
    return "unsupported"


def _mono_touch_layout_state(tree: dict[str, Any]) -> str:
    min_y = float(tree["m_AnchorMin"]["y"])
    max_y = float(tree["m_AnchorMax"]["y"])
    position_y = float(tree["m_AnchoredPosition"]["y"])
    if (
        _near(min_y, 1.0)
        and _near(max_y, 1.0)
        and _near(position_y, MONO_TOUCH_TARGET_POSITION_Y)
    ):
        return "patched"
    if (
        _near(min_y, 0.5)
        and _near(max_y, 0.5)
        and _near(position_y, MONO_TOUCH_SOURCE_POSITION_Y)
    ) or (
        _near(min_y, 1.0)
        and _near(max_y, 1.0)
        and _near(position_y, MONO_TOUCH_V1_POSITION_Y)
    ):
        return "original"
    return "unsupported"


def _mono_world_resolution_state(
    raw: bytes | bytearray,
) -> tuple[str, list[tuple[int, bytes, bytes]]]:
    pairs = (
        (
            struct.pack("<ii", *WORLD_NATIVE_RESOLUTION_SOURCE),
            struct.pack("<ii", *WORLD_NATIVE_RESOLUTION_TARGET),
        ),
        (
            struct.pack("<ff", *WORLD_FORCE_RESOLUTION_SOURCE),
            struct.pack("<ff", *WORLD_FORCE_RESOLUTION_TARGET),
        ),
    )
    edits: list[tuple[int, bytes, bytes]] = []
    states: set[str] = set()
    force_offset: int | None = None
    for source, target in pairs:
        source_offsets = _byte_offsets(raw, source)
        target_offsets = _byte_offsets(raw, target)
        if len(source_offsets) == 1 and not target_offsets:
            states.add("original")
            edits.append((source_offsets[0], source, target))
            if source == pairs[1][0]:
                force_offset = source_offsets[0]
        elif len(target_offsets) == 1 and not source_offsets:
            states.add("patched")
            if target == pairs[1][1]:
                force_offset = target_offsets[0]
        else:
            return "unsupported", []

    # `zoomFactor` is serialized immediately before the enabled forced-output
    # flag and its Vector2 resolution. Anchor the field to that verified
    # structure instead of searching for the common 1.0 float globally.
    if force_offset is None or force_offset < 8:
        return "unsupported", []
    zoom_offset = force_offset - 8
    if raw[zoom_offset + 4 : force_offset] != b"\x01\x00\x00\x00":
        return "unsupported", []
    source_zoom = struct.pack("<f", WORLD_ZOOM_SOURCE)
    target_zoom = struct.pack("<f", WORLD_ZOOM_TARGET)
    current_zoom = bytes(raw[zoom_offset : zoom_offset + 4])
    if current_zoom == source_zoom:
        states.add("original")
        edits.append((zoom_offset, source_zoom, target_zoom))
    elif current_zoom == target_zoom:
        states.add("patched")
    else:
        return "unsupported", []
    return ("patched" if states == {"patched"} else "original"), edits


def _mono_unity_targets(path: Path) -> list[dict[str, Any]]:
    UnityPy = _unitypy()
    environment = UnityPy.load(str(path))
    bundle = _bundle_file(environment)
    targets: list[dict[str, Any]] = []
    try:
        for asset_name in WORLD_CAMERA_ASSETS:
            assets_file = bundle.files.get(asset_name)
            target_name = f"Mono 4:3 world render resolution: {asset_name}"
            if assets_file is None:
                targets.append(_target(target_name, "unsupported"))
                continue
            cameras = _script_component_reader(
                bundle,
                assets_file,
                "_GameCameras/CameraParent/tk2dCamera",
                "tk2dCamera",
            )
            if len(cameras) != 1:
                state = "ambiguous" if len(cameras) > 1 else "unsupported"
                targets.append(_target(target_name, state, matches=len(cameras)))
                continue
            state, _ = _mono_world_resolution_state(cameras[0].get_raw_data())
            targets.append(_target(target_name, state))

        level0 = bundle.files.get("level0")
        if level0 is None:
            targets.append(_target("Mono intro: disclaimer scene", "unsupported"))
        else:
            scalers = _script_component_reader(bundle, level0, "Canvas", "CanvasScaler")
            if len(scalers) != 1:
                state = "ambiguous" if len(scalers) > 1 else "unsupported"
                targets.append(
                    _target("Mono intro: expanding canvas", state, matches=len(scalers))
                )
            else:
                state, _ = _disclaimer_scaler_state(scalers[0].get_raw_data())
                targets.append(_target("Mono intro: expanding canvas", state))

            descriptions = _path_readers(
                level0, "RectTransform", "Canvas/Disclaimer/Description"
            )
            if len(descriptions) != 1:
                state = "ambiguous" if len(descriptions) > 1 else "unsupported"
                targets.append(
                    _target("Mono intro: disclaimer text fit", state, matches=len(descriptions))
                )
            else:
                tree = descriptions[0].read_typetree()
                scale = tree["m_LocalScale"]
                states = {
                    _value_state(scale[axis], DISCLAIMER_SCALE_SOURCE, DISCLAIMER_SCALE_TARGET)
                    for axis in ("x", "y")
                }
                if states == {"original"}:
                    state = "original"
                elif states == {"patched"}:
                    state = "patched"
                elif states <= {"original", "patched"}:
                    state = "original"
                else:
                    state = "unsupported"
                targets.append(
                    _target(
                        "Mono intro: disclaimer text fit",
                        state,
                        scale_x=float(scale["x"]),
                        scale_y=float(scale["y"]),
                    )
                )

        resources = bundle.files.get("resources.assets")
        if resources is None:
            targets.append(_target("Mono resources.assets", "unsupported"))
        else:
            ui_scalers = _script_component_reader(
                bundle, resources, "_UIManager/UICanvas", "CanvasScaler"
            )
            if len(ui_scalers) != 1:
                state = "ambiguous" if len(ui_scalers) > 1 else "unsupported"
                targets.append(
                    _target("Mono 4:3 UI reference", state, matches=len(ui_scalers))
                )
            else:
                state, _ = _ui_scaler_state(ui_scalers[0].get_raw_data())
                targets.append(_target("Mono 4:3 UI reference", state))

            cameras = _path_readers(resources, "Camera", "_GameCameras/HudCamera")
            canvases = _path_readers(
                resources, "Transform", "_GameCameras/HudCamera/Hud Canvas"
            )
            if len(cameras) != 1 or len(canvases) != 1:
                state = (
                    "ambiguous"
                    if len(cameras) > 1 or len(canvases) > 1
                    else "unsupported"
                )
                targets.append(
                    _target(
                        "Mono 4:3 gameplay HUD",
                        state,
                        cameras=len(cameras),
                        canvases=len(canvases),
                    )
                )

            else:
                camera_tree = cameras[0].read_typetree()
                canvas_tree = canvases[0].read_typetree()
                targets.append(
                    _target(
                        "Mono 4:3 gameplay HUD",
                        _mono_hud_layout_state(camera_tree, canvas_tree),
                        camera_size=float(camera_tree["orthographic size"]),
                        position_x=float(canvas_tree["m_LocalPosition"]["x"]),
                        position_y=float(canvas_tree["m_LocalPosition"]["y"]),
                        scale_x=float(canvas_tree["m_LocalScale"]["x"]),
                        scale_y=float(canvas_tree["m_LocalScale"]["y"]),
                    )
                )

            hud_fsms = _script_component_reader(
                bundle, resources, "_GameCameras/HudCamera/Hud Canvas", "PlayMakerFSM"
            )
            recognized_fsms = []
            for reader in hud_fsms:
                fsm_state, _ = _mono_hud_fsm_state(reader.get_raw_data())
                if fsm_state != "unsupported":
                    recognized_fsms.append((fsm_state, reader))
            if len(recognized_fsms) != 1:
                state = "ambiguous" if len(recognized_fsms) > 1 else "unsupported"
                targets.append(
                    _target(
                        "Mono runtime gameplay HUD scale",
                        state,
                        matches=len(recognized_fsms),
                    )
                )
            else:
                targets.append(
                    _target("Mono runtime gameplay HUD scale", recognized_fsms[0][0])
                )

            inventories = _path_readers(
                resources, "Transform", "_GameCameras/HudCamera/Inventory"
            )
            if len(inventories) != 1:
                state = "ambiguous" if len(inventories) > 1 else "unsupported"
                targets.append(
                    _target("Mono 4:3 inventory fit", state, matches=len(inventories))
                )
            else:
                inventory_tree = inventories[0].read_typetree()
                targets.append(
                    _target(
                        "Mono 4:3 inventory fit",
                        _mono_inventory_layout_state(inventory_tree),
                        position_x=float(inventory_tree["m_LocalPosition"]["x"]),
                        position_y=float(inventory_tree["m_LocalPosition"]["y"]),
                        scale_x=float(inventory_tree["m_LocalScale"]["x"]),
                        scale_y=float(inventory_tree["m_LocalScale"]["y"]),
                    )
                )

            for name in INVENTORY_CHILDREN:
                path_name = f"_GameCameras/HudCamera/Inventory/{name}"
                readers = _path_readers(resources, "Transform", path_name)
                target_name = f"Mono 4:3 inventory pane: {name}"
                if len(readers) != 1:
                    state = "ambiguous" if len(readers) > 1 else "unsupported"
                    targets.append(_target(target_name, state, matches=len(readers)))
                    continue
                tree = readers[0].read_typetree()
                targets.append(_target(target_name, _mono_inventory_child_state(tree)))

            for name in sorted(INVENTORY_BACKDROPS):
                path_name = f"_GameCameras/HudCamera/Inventory/Border/{name}"
                readers = _path_readers(resources, "Transform", path_name)
                target_name = f"Mono full-screen inventory backdrop: {name}"
                if len(readers) != 1:
                    state = "ambiguous" if len(readers) > 1 else "unsupported"
                    targets.append(_target(target_name, state, matches=len(readers)))
                    continue
                tree = readers[0].read_typetree()
                targets.append(
                    _target(
                        target_name,
                        _mono_inventory_backdrop_state(tree, name),
                    )
                )

            for name in sorted(MONO_TOUCH_BUTTONS):
                path_name = f"_InControlManager/TouchControls/{name}"
                readers = _path_readers(resources, "RectTransform", path_name)
                target_name = f"Mono touch top edge: {name}"
                if len(readers) != 1:
                    state = "ambiguous" if len(readers) > 1 else "unsupported"
                    targets.append(_target(target_name, state, matches=len(readers)))
                    continue
                tree = readers[0].read_typetree()
                min_y = float(tree["m_AnchorMin"]["y"])
                max_y = float(tree["m_AnchorMax"]["y"])
                position_y = float(tree["m_AnchoredPosition"]["y"])
                state = _mono_touch_layout_state(tree)
                targets.append(
                    _target(
                        target_name,
                        state,
                        anchor_min_y=min_y,
                        anchor_max_y=max_y,
                        anchored_position_y=position_y,
                    )
                )

        level2 = bundle.files.get("level2")
        if level2 is None:
            targets.append(_target("Mono active-scene HUD", "unsupported"))
        else:
            cameras = _path_readers(level2, "Camera", "_GameCameras/HudCamera")
            canvases = _path_readers(
                level2, "Transform", "_GameCameras/HudCamera/Hud Canvas"
            )
            if len(cameras) != 1 or len(canvases) != 1:
                state = (
                    "ambiguous"
                    if len(cameras) > 1 or len(canvases) > 1
                    else "unsupported"
                )
                targets.append(_target("Mono active-scene HUD", state))
            else:
                targets.append(
                    _target(
                        "Mono active-scene HUD",
                        _mono_hud_layout_state(
                            cameras[0].read_typetree(), canvases[0].read_typetree()
                        ),
                    )
                )

            hud_fsms = _script_component_reader(
                bundle, level2, "_GameCameras/HudCamera/Hud Canvas", "PlayMakerFSM"
            )
            recognized_fsms = [
                (state, reader)
                for reader in hud_fsms
                for state, _offset in [_mono_hud_fsm_state(reader.get_raw_data())]
                if state != "unsupported"
            ]
            state = (
                recognized_fsms[0][0]
                if len(recognized_fsms) == 1
                else ("ambiguous" if len(recognized_fsms) > 1 else "unsupported")
            )
            targets.append(_target("Mono active-scene HUD animation", state))

            inventories = _path_readers(
                level2, "Transform", "_GameCameras/HudCamera/Inventory"
            )
            state = (
                _mono_inventory_layout_state(inventories[0].read_typetree())
                if len(inventories) == 1
                else ("ambiguous" if len(inventories) > 1 else "unsupported")
            )
            targets.append(_target("Mono active-scene inventory fit", state))

            for name in sorted(INVENTORY_BACKDROPS):
                readers = _path_readers(
                    level2,
                    "Transform",
                    f"_GameCameras/HudCamera/Inventory/Border/{name}",
                )
                state = (
                    _mono_inventory_backdrop_state(readers[0].read_typetree(), name)
                    if len(readers) == 1
                    else ("ambiguous" if len(readers) > 1 else "unsupported")
                )
                targets.append(
                    _target(f"Mono active-scene inventory backdrop: {name}", state)
                )
    finally:
        _close_unity(bundle, environment)
    return targets


def _byte_offsets(data: bytes | bytearray, needle: bytes) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while True:
        offset = data.find(needle, cursor)
        if offset < 0:
            return offsets
        offsets.append(offset)
        cursor = offset + len(needle)


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


def _managed_dependencies():
    try:
        import dnfile  # type: ignore
        from dncil.cil.body.reader import read_method_body_from_bytes  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency error is user-facing
        raise PatchError("dnfile and dncil are required for the Hollow Knight Mono patch") from exc
    return dnfile, read_method_body_from_bytes


def _metadata_type_name(row: Any) -> str:
    return f"{row.TypeNamespace}.{row.TypeName}".strip(".")


class _ManagedAssembly:
    def __init__(self, path: Path):
        dnfile, self._read_body = _managed_dependencies()
        self.path = path
        self.pe = dnfile.dnPE(str(path))
        if self.pe.net is None:
            raise PatchError("Assembly-CSharp.dll is not a managed .NET assembly")
        self.method_owners = {
            id(index.row): _metadata_type_name(type_def)
            for type_def in self.pe.net.mdtables.TypeDef
            for index in type_def.MethodList
        }
        self.field_owners = {
            id(index.row): _metadata_type_name(type_def)
            for type_def in self.pe.net.mdtables.TypeDef
            for index in type_def.FieldList
        }

    def methods(self, type_name: str, method_name: str) -> list[tuple[int, Any]]:
        matches: list[tuple[int, Any]] = []
        for type_def in self.pe.net.mdtables.TypeDef:
            if _metadata_type_name(type_def) != type_name:
                continue
            for index in type_def.MethodList:
                method = index.row
                if str(method.Name) != method_name or not method.Rva:
                    continue
                body = self._read_body(self.pe.get_data(method.Rva, 1 << 20))
                matches.append((self.pe.get_offset_from_rva(method.Rva), body))
        return matches

    def field_name(self, operand: Any) -> str | None:
        value = getattr(operand, "value", None)
        if not isinstance(value, int) or value >> 24 != 0x04:
            return None
        row_id = value & 0xFFFFFF
        table = self.pe.net.mdtables.Field
        if not 1 <= row_id <= len(table.rows):
            return None
        row = table.rows[row_id - 1]
        return f"{self.field_owners.get(id(row), '?')}::{row.Name}"

    def method_row(self, type_name: str, method_name: str) -> Any:
        matches = []
        for type_def in self.pe.net.mdtables.TypeDef:
            if _metadata_type_name(type_def) != type_name:
                continue
            matches.extend(
                index.row
                for index in type_def.MethodList
                if str(index.row.Name) == method_name and index.row.Rva
            )
        if len(matches) != 1:
            raise PatchError(
                f"managed method {type_name}.{method_name} is not unique"
            )
        return matches[0]

    def field_token(self, type_name: str, field_name: str) -> int:
        matches = [
            index
            for index, row in enumerate(self.pe.net.mdtables.Field, 1)
            if self.field_owners.get(id(row)) == type_name
            and str(row.Name) == field_name
        ]
        if len(matches) != 1:
            raise PatchError(f"managed field {type_name}.{field_name} is not unique")
        return 0x04000000 | matches[0]

    def method_token(self, type_name: str, method_name: str) -> int:
        table = self.pe.net.mdtables.MethodDef
        matches = [
            index
            for index, row in enumerate(table, 1)
            if self.method_owners.get(id(row)) == type_name
            and str(row.Name) == method_name
        ]
        if len(matches) != 1:
            raise PatchError(f"managed method {type_name}.{method_name} is not unique")
        return 0x06000000 | matches[0]

    def member_token(self, type_name: str, method_name: str, signature: bytes) -> int:
        matches = []
        for index, row in enumerate(self.pe.net.mdtables.MemberRef, 1):
            owner = getattr(getattr(row.Class, "row", None), "TypeName", None)
            namespace = getattr(getattr(row.Class, "row", None), "TypeNamespace", "")
            full_name = f"{namespace}.{owner}".strip(".") if owner else ""
            if (
                full_name == type_name
                and str(row.Name) == method_name
                and bytes(row.Signature.value) == signature
            ):
                matches.append(index)
        if len(matches) != 1:
            raise PatchError(f"managed member {type_name}.{method_name} is not unique")
        return 0x0A000000 | matches[0]

    def user_string_token(self, value: str) -> int:
        encoded = value.encode("utf-16le") + b"\0"
        if len(encoded) >= 0x80:
            raise PatchError("managed inventory string encoding changed")
        needle = bytes((len(encoded),)) + encoded
        heap = self.pe.net.user_strings.__dict__["__data__"]
        offsets = _byte_offsets(heap, needle)
        if len(offsets) != 1:
            raise PatchError("managed Inventory user string is not unique")
        return 0x70000000 | offsets[0]


def _managed_inventory_runtime_state(assembly: _ManagedAssembly) -> str:
    """Recognize the original or injected HUDCamera menu-open method."""

    methods = assembly.methods("HUDCamera", "MoveMenuToHUDCamera")
    if len(methods) != 1:
        return "ambiguous" if len(methods) > 1 else "unsupported"
    _offset, body = methods[0]
    instructions = body.instructions
    target_literals = [
        instruction
        for instruction in instructions
        if instruction.opcode.name == "ldc.r4"
        and _near(instruction.operand, INVENTORY_RUNTIME_SCALE)
    ]
    prior_literals = [
        instruction
        for instruction in instructions
        if instruction.opcode.name == "ldc.r4"
        and _near(instruction.operand, INVENTORY_RUNTIME_SCALE_V1)
    ]
    has_find = any(
        instruction.opcode.name == "call"
        and getattr(instruction.operand, "value", None)
        == assembly.member_token(
            "UnityEngine.GameObject", "Find", bytes.fromhex("000112590e")
        )
        for instruction in instructions
    )
    float_literals = [
        float(instruction.operand)
        for instruction in instructions
        if instruction.opcode.name == "ldc.r4"
    ]

    def has_position(position: tuple[float, float, float]) -> bool:
        return all(
            any(_near(value, expected) for value in float_literals)
            for expected in position
        )

    # X, Y, and Z are all one in the final uniform-scale vector.
    if (
        len(target_literals) == 3
        and not prior_literals
        and has_find
        and has_position(INVENTORY_RUNTIME_POSITION)
    ):
        return "patched"
    if (len(prior_literals) == 2 and has_find) or (
        len(target_literals) == 3
        and not prior_literals
        and has_find
        and has_position(INVENTORY_RUNTIME_POSITION_V1)
    ):
        return "original"
    if not target_literals and not prior_literals and not has_find and len(instructions) == 13:
        return "original"
    return "unsupported"


def _managed_inventory_runtime_body(assembly: _ManagedAssembly) -> bytes:
    """Build a replacement method that fits Inventory after its runtime reset."""

    def token(opcode: int, value: int) -> bytes:
        return bytes((opcode,)) + struct.pack("<I", value)

    gc_field = assembly.field_token("HUDCamera", "gc")
    pause_field = assembly.field_token("HUDCamera", "shouldEnablePause")
    input_field = assembly.field_token("HUDCamera", "ih")
    move_menu = assembly.method_token("GameCameras", "MoveMenuToHUDCamera")
    allow_pause = assembly.method_token("InputHandler", "AllowPause")
    find = assembly.member_token(
        "UnityEngine.GameObject", "Find", bytes.fromhex("000112590e")
    )
    get_transform = assembly.member_token(
        "UnityEngine.GameObject", "get_transform", bytes.fromhex("20001280d5")
    )
    vector_ctor = assembly.member_token(
        "UnityEngine.Vector3", ".ctor", bytes.fromhex("2003010c0c0c")
    )
    set_scale = assembly.member_token(
        "UnityEngine.Transform", "set_localScale", bytes.fromhex("2001011175")
    )
    set_position = assembly.member_token(
        "UnityEngine.Transform", "set_localPosition", bytes.fromhex("2001011175")
    )
    inventory_string = assembly.user_string_token("Inventory")

    code = bytearray()
    code += b"\x02" + token(0x7B, gc_field) + token(0x6F, move_menu)
    code += token(0x72, inventory_string) + token(0x28, find)
    code += token(0x6F, get_transform)
    code += b"\x22" + struct.pack("<f", INVENTORY_RUNTIME_SCALE)
    code += b"\x22" + struct.pack("<f", INVENTORY_RUNTIME_SCALE)
    code += b"\x22" + struct.pack("<f", 1.0)
    code += token(0x73, vector_ctor) + token(0x6F, set_scale)
    code += token(0x72, inventory_string) + token(0x28, find)
    code += token(0x6F, get_transform)
    for value in INVENTORY_RUNTIME_POSITION:
        code += b"\x22" + struct.pack("<f", value)
    code += token(0x73, vector_ctor) + token(0x6F, set_position)

    code += b"\x02" + token(0x7B, pause_field)
    branch_offset = len(code)
    code += b"\x2c\x00"
    code += b"\x02" + token(0x7B, input_field) + token(0x6F, allow_pause)
    code += b"\x02\x16" + token(0x7D, pause_field)
    return_offset = len(code)
    code += b"\x2a"
    distance = return_offset - (branch_offset + 2)
    if not -128 <= distance <= 127:
        raise PatchError("managed inventory branch is out of range")
    code[branch_offset + 1] = distance & 0xFF
    return struct.pack("<HHII", 0x3003, 4, len(code), 0) + bytes(code)


def _inject_managed_inventory_runtime(
    assembly: _ManagedAssembly, data: bytearray
) -> None:
    body = _managed_inventory_runtime_body(assembly)
    text_sections = [
        section
        for section in assembly.pe.sections
        if section.Name.rstrip(b"\0") == b".text"
    ]
    if len(text_sections) != 1:
        raise PatchError("managed .text section is not unique")
    section = text_sections[0]
    section_end = section.PointerToRawData + section.SizeOfRawData
    padding_start = section_end
    while padding_start > section.PointerToRawData and data[padding_start - 1] == 0:
        padding_start -= 1
    destination = (padding_start + 3) & ~3
    if destination + len(body) > section_end:
        raise PatchError("managed assembly has no safe trailing code space")
    if any(data[destination : destination + len(body)]):
        raise PatchError("managed trailing code space is not empty")
    data[destination : destination + len(body)] = body

    method = assembly.method_row("HUDCamera", "MoveMenuToHUDCamera")
    rva_offset = method.struct.get_field_absolute_offset("Rva")
    new_rva = section.VirtualAddress + destination - section.PointerToRawData
    struct.pack_into("<I", data, rva_offset, new_rva)


def _managed_float_target(
    assembly: _ManagedAssembly,
    type_name: str,
    method_name: str,
    expected_methods: int,
    expected_literals: int,
    source: float,
    target: float,
    label: str,
) -> tuple[dict[str, Any], list[tuple[int, bytes, bytes]]]:
    methods = assembly.methods(type_name, method_name)
    if len(methods) != expected_methods:
        state = "ambiguous" if len(methods) > expected_methods else "unsupported"
        return _target(label, state, methods=len(methods)), []

    source_hits: list[tuple[int, bytes, bytes]] = []
    target_hits = 0
    for method_offset, body in methods:
        for instruction in body.instructions:
            if instruction.opcode.name != "ldc.r4":
                continue
            value = instruction.operand
            operand_offset = method_offset + instruction.offset + len(instruction.opcode_bytes)
            if _near(value, source):
                source_hits.append(
                    (
                        operand_offset,
                        bytes(instruction.operand_bytes),
                        struct.pack("<f", target),
                    )
                )
            elif _near(value, target):
                target_hits += 1

    recognized = len(source_hits) + target_hits
    if recognized != expected_literals:
        state = "ambiguous" if recognized > expected_literals else "unsupported"
        return _target(
            label,
            state,
            original_matches=len(source_hits),
            patched_matches=target_hits,
        ), []
    state = "patched" if target_hits == expected_literals else "original"
    return _target(
        label,
        state,
        original_matches=len(source_hits),
        patched_matches=target_hits,
    ), source_hits


def _managed_black_bars_target(
    assembly: _ManagedAssembly,
) -> tuple[dict[str, Any], list[tuple[int, bytes, bytes]]]:
    methods = assembly.methods("ForceCameraAspect", "AutoScaleViewport")
    if len(methods) != 1:
        state = "ambiguous" if len(methods) > 1 else "unsupported"
        return _target("Mono full viewport branch", state, methods=len(methods)), []
    method_offset, body = methods[0]
    instructions = body.instructions
    field_indices = [
        index
        for index, instruction in enumerate(instructions)
        if instruction.opcode.name == "ldsfld"
        and assembly.field_name(instruction.operand) == "ModManagerSettings::BlackBars"
    ]
    if len(field_indices) != 1:
        state = "ambiguous" if len(field_indices) > 1 else "unsupported"
        return _target("Mono full viewport branch", state, matches=len(field_indices)), []
    index = field_indices[0]
    following = instructions[index + 1 : index + 3]
    if following and following[0].opcode.name in ("brtrue", "brtrue.s"):
        branch = following[0]
        offset = method_offset + branch.offset
        original = bytes(branch.opcode_bytes) + bytes(branch.operand_bytes)
        replacement = b"\x26" + b"\x00" * (len(original) - 1)
        return _target("Mono full viewport branch", "original"), [
            (offset, original, replacement)
        ]
    if len(following) == 2 and following[0].opcode.name == "pop" and following[1].opcode.name == "nop":
        return _target("Mono full viewport branch", "patched"), []
    return _target("Mono full viewport branch", "unsupported"), []


def _managed_overscan_target(
    assembly: _ManagedAssembly,
) -> tuple[dict[str, Any], list[tuple[int, bytes, bytes]]]:
    """Neutralize the port's hidden edge crop while preserving UI overscan math."""

    methods = assembly.methods("ForceCameraAspect", "AutoScaleViewport")
    if len(methods) != 1:
        state = "ambiguous" if len(methods) > 1 else "unsupported"
        return _target("Mono full-frame overscan", state, methods=len(methods)), []
    method_offset, body = methods[0]
    instructions = body.instructions

    field_indices = [
        index
        for index, instruction in enumerate(instructions)
        if instruction.opcode.name == "ldfld"
        and assembly.field_name(instruction.operand) == "ForceCameraAspect::scaleAdjust"
    ]
    if len(field_indices) == 1:
        index = field_indices[0]
        if index < 2 or index + 1 >= len(instructions):
            return _target("Mono full-frame overscan", "unsupported"), []
        load_this = instructions[index - 1]
        one = instructions[index - 2]
        add = instructions[index + 1]
        if (
            load_this.opcode.name != "ldarg.0"
            or one.opcode.name != "ldc.r4"
            or not _near(one.operand, 1.0)
            or add.opcode.name != "add"
        ):
            return _target("Mono full-frame overscan", "unsupported"), []
        start = method_offset + load_this.offset
        original = b"".join(
            bytes(item.opcode_bytes) + bytes(item.operand_bytes)
            for item in (load_this, instructions[index], add)
        )
        if len(original) != 7:
            return _target("Mono full-frame overscan", "unsupported"), []
        return _target("Mono full-frame overscan", "original"), [
            (start, original, b"\x00" * len(original))
        ]

    # In the patched method the 7-byte `this.scaleAdjust +` expression is a
    # run of nops between `ldc.r4 1` and the local store. Require that exact
    # structure so an unrelated run of padding can never pass verification.
    for index, instruction in enumerate(instructions):
        if (
            instruction.opcode.name != "ldc.r4"
            or not _near(instruction.operand, 1.0)
            or index + 8 >= len(instructions)
        ):
            continue
        padding = instructions[index + 1 : index + 8]
        store = instructions[index + 8]
        if all(item.opcode.name == "nop" for item in padding) and store.opcode.name.startswith(
            "stloc"
        ):
            return _target("Mono full-frame overscan", "patched"), []
    return _target("Mono full-frame overscan", "unsupported"), []


def _managed_targets(
    path: Path,
) -> tuple[list[dict[str, Any]], list[tuple[int, bytes, bytes]]]:
    assembly = _ManagedAssembly(path)
    targets: list[dict[str, Any]] = []
    edits: list[tuple[int, bytes, bytes]] = []
    for type_name, method_name, method_count, literal_count in MANAGED_ASPECT_METHODS:
        target, method_edits = _managed_float_target(
            assembly,
            type_name,
            method_name,
            method_count,
            literal_count,
            SOURCE_ASPECT,
            TARGET_ASPECT,
            f"Mono aspect: {type_name}.{method_name}",
        )
        targets.append(target)
        edits.extend(method_edits)
    branch, branch_edits = _managed_black_bars_target(assembly)
    targets.append(branch)
    edits.extend(branch_edits)
    overscan, overscan_edits = _managed_overscan_target(assembly)
    targets.append(overscan)
    edits.extend(overscan_edits)
    ui_reference, ui_reference_edits = _managed_float_target(
        assembly,
        "GameCameras",
        "SetOverscan",
        1,
        1,
        UI_REFERENCE_HEIGHT_SOURCE,
        UI_REFERENCE_HEIGHT_TARGET,
        "Mono 4:3 runtime UI reference",
    )
    targets.append(ui_reference)
    edits.extend(ui_reference_edits)
    for type_name, method_name, method_count, literal_count in MANAGED_BOUND_METHODS:
        target, method_edits = _managed_float_target(
            assembly,
            type_name,
            method_name,
            method_count,
            literal_count,
            CAMERA_LIMIT_SOURCE,
            CAMERA_LIMIT_TARGET,
            f"Mono camera bounds: {type_name}.{method_name}",
        )
        targets.append(target)
        edits.extend(method_edits)
    targets.append(
        _target(
            INVENTORY_RUNTIME_TARGET_NAME,
            _managed_inventory_runtime_state(assembly),
        )
    )
    return targets, edits


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
    mono_present = extracted.get(MONO_ENTRY) is not None and Path(
        extracted[MONO_ENTRY]
    ).is_file()
    native_entries = [
        entry
        for entry in SUPPORTED_NATIVE_ENTRIES
        if extracted.get(entry) is not None and Path(extracted[entry]).is_file()
    ]
    if mono_present and native_entries:
        targets.append(
            _target(
                "Unity scripting runtime",
                "ambiguous",
                reason="APK contains both Mono Assembly-CSharp.dll and IL2CPP libraries",
            )
        )
        return {"state": _overall(targets), "targets": targets}
    if mono_present:
        try:
            targets.extend(_mono_unity_targets(extracted[DATA_ENTRY]))
        except Exception as exc:
            targets.append(_target("Mono Unity data bundle", "unsupported", reason=str(exc)))
        try:
            managed_targets, _ = _managed_targets(extracted[MONO_ENTRY])
            targets.extend(managed_targets)
        except Exception as exc:
            targets.append(_target(MONO_ENTRY, "unsupported", reason=str(exc)))
    elif native_entries:
        try:
            targets.extend(_unity_targets(extracted[DATA_ENTRY]))
        except Exception as exc:
            targets.append(_target("Unity data bundle", "unsupported", reason=str(exc)))
        for entry in native_entries:
            try:
                targets.extend(_native_targets(entry, extracted[entry]))
            except Exception as exc:
                targets.append(_target(entry, "unsupported", reason=str(exc)))
    else:
        targets.append(
            _target(
                "supported Unity scripting runtime",
                "unsupported",
                reason="APK contains neither Mono Assembly-CSharp.dll nor a supported IL2CPP library",
            )
        )
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
                tree["m_LocalPosition"]["y"] = IL2CPP_HUD_CANVAS_TARGET_Y
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


def _patch_unity_mono(source: Path, destination: Path) -> bool:
    UnityPy = _unitypy()
    environment = UnityPy.load(str(source))
    bundle = _bundle_file(environment)
    changed = False
    try:
        for asset_name in WORLD_CAMERA_ASSETS:
            assets_file = bundle.files[asset_name]
            camera = _script_component_reader(
                bundle,
                assets_file,
                "_GameCameras/CameraParent/tk2dCamera",
                "tk2dCamera",
            )[0]
            raw = bytearray(camera.get_raw_data())
            state, edits = _mono_world_resolution_state(raw)
            if state == "original":
                for offset, source_value, target_value in edits:
                    if raw[offset : offset + len(source_value)] != source_value:
                        raise PatchError(
                            f"Hollow Knight Mono world resolution changed in {asset_name}"
                        )
                    raw[offset : offset + len(source_value)] = target_value
                camera.set_raw_data(bytes(raw))
                changed = True
            elif state != "patched":
                raise PatchError(
                    f"Hollow Knight Mono world resolution changed in {asset_name}"
                )

        level0 = bundle.files["level0"]
        scaler = _script_component_reader(bundle, level0, "Canvas", "CanvasScaler")[0]
        raw = bytearray(scaler.get_raw_data())
        state, _ = _disclaimer_scaler_state(raw)
        if state != "patched":
            raise PatchError("Hollow Knight Mono disclaimer CanvasScaler changed")

        description = _path_readers(
            level0, "RectTransform", "Canvas/Disclaimer/Description"
        )[0]
        tree = description.read_typetree()
        scale = tree["m_LocalScale"]
        scale_changed = False
        for axis in ("x", "y"):
            if _near(scale[axis], DISCLAIMER_SCALE_SOURCE):
                scale[axis] = DISCLAIMER_SCALE_TARGET
                scale_changed = True
        if scale_changed:
            description.save_typetree(tree)
            changed = True

        resources = bundle.files["resources.assets"]
        ui_scaler = _script_component_reader(
            bundle, resources, "_UIManager/UICanvas", "CanvasScaler"
        )[0]
        raw = bytearray(ui_scaler.get_raw_data())
        scaler_state, height_offset = _ui_scaler_state(raw)
        if scaler_state == "original" and height_offset is not None:
            struct.pack_into("<f", raw, height_offset, UI_REFERENCE_HEIGHT_TARGET)
            ui_scaler.set_raw_data(bytes(raw))
            changed = True
        elif scaler_state != "patched":
            raise PatchError("Hollow Knight Mono UI CanvasScaler changed")

        camera = _path_readers(resources, "Camera", "_GameCameras/HudCamera")[0]
        tree = camera.read_typetree()
        if any(
            _near(tree["orthographic size"], value)
            for value in (
                HUD_ORTHO_SOURCE,
                HUD_ORTHO_TARGET,
                MONO_HUD_ORTHO_V4,
                MONO_HUD_ORTHO_V5,
            )
        ):
            tree["orthographic size"] = MONO_HUD_ORTHO_TARGET
            camera.save_typetree(tree)
            changed = True

        canvas = _path_readers(
            resources, "Transform", "_GameCameras/HudCamera/Hud Canvas"
        )[0]
        tree = canvas.read_typetree()
        if _mono_hud_layout_state(camera.read_typetree(), tree) == "original":
            tree["m_LocalPosition"]["x"] = MONO_HUD_CANVAS_TARGET_X
            tree["m_LocalPosition"]["y"] = MONO_HUD_CANVAS_TARGET_Y
            tree["m_LocalScale"]["x"] = MONO_HUD_SCALE_TARGET
            tree["m_LocalScale"]["y"] = MONO_HUD_SCALE_TARGET
            canvas.save_typetree(tree)
            changed = True

        hud_fsms = _script_component_reader(
            bundle, resources, "_GameCameras/HudCamera/Hud Canvas", "PlayMakerFSM"
        )
        recognized_fsms = []
        for reader in hud_fsms:
            fsm_state, offset = _mono_hud_fsm_state(reader.get_raw_data())
            if fsm_state != "unsupported":
                recognized_fsms.append((fsm_state, offset, reader))
        if len(recognized_fsms) != 1:
            raise PatchError("Hollow Knight Mono HUD scale FSM changed")
        fsm_state, offset, hud_fsm = recognized_fsms[0]
        if fsm_state == "original" and offset is not None:
            raw = bytearray(hud_fsm.get_raw_data())
            source_patterns = (
                _hud_fsm_scale_pattern(MONO_HUD_SCALE_V4),
                _hud_fsm_scale_pattern(MONO_HUD_SCALE_V5),
            )
            target_pattern = _hud_fsm_scale_pattern(MONO_HUD_SCALE_TARGET)
            source_pattern = next(
                (
                    pattern
                    for pattern in source_patterns
                    if raw[offset : offset + len(pattern)] == pattern
                ),
                None,
            )
            if source_pattern is None:
                raise PatchError("Hollow Knight Mono HUD scale FSM changed")
            raw[offset : offset + len(source_pattern)] = target_pattern
            hud_fsm.set_raw_data(bytes(raw))
            changed = True
        elif fsm_state != "patched":
            raise PatchError("Hollow Knight Mono HUD scale FSM is ambiguous")

        inventory = _path_readers(
            resources, "Transform", "_GameCameras/HudCamera/Inventory"
        )[0]
        tree = inventory.read_typetree()
        inventory_state = _mono_inventory_layout_state(tree)
        if inventory_state == "original":
            tree["m_LocalPosition"]["x"] = INVENTORY_TARGET_POSITION[0]
            tree["m_LocalPosition"]["y"] = INVENTORY_TARGET_POSITION[1]
            tree["m_LocalScale"]["x"] = INVENTORY_SCALE_TARGET
            tree["m_LocalScale"]["y"] = INVENTORY_SCALE_TARGET
            inventory.save_typetree(tree)
            changed = True
        elif inventory_state != "patched":
            raise PatchError("Hollow Knight Mono inventory layout changed")

        for name in INVENTORY_CHILDREN:
            reader = _path_readers(
                resources,
                "Transform",
                f"_GameCameras/HudCamera/Inventory/{name}",
            )[0]
            tree = reader.read_typetree()
            child_state = _mono_inventory_child_state(tree)
            if child_state == "original":
                tree["m_LocalScale"]["x"] = INVENTORY_CHILD_SCALE_TARGET
                tree["m_LocalScale"]["y"] = INVENTORY_CHILD_SCALE_TARGET
                reader.save_typetree(tree)
                changed = True
            elif child_state != "patched":
                raise PatchError(f"Hollow Knight Mono inventory pane {name} changed")

        for name, (source_x, source_y) in INVENTORY_BACKDROPS.items():
            reader = _path_readers(
                resources,
                "Transform",
                f"_GameCameras/HudCamera/Inventory/Border/{name}",
            )[0]
            tree = reader.read_typetree()
            backdrop_state = _mono_inventory_backdrop_state(tree, name)
            if backdrop_state == "original":
                tree["m_LocalScale"]["x"] = (
                    source_x * INVENTORY_BACKDROP_SCALE_MULTIPLIER
                )
                tree["m_LocalScale"]["y"] = (
                    source_y * INVENTORY_BACKDROP_SCALE_MULTIPLIER
                )
                tree["m_LocalPosition"]["y"] = (
                    INVENTORY_BACKDROP_SOURCE_Y[name]
                    + INVENTORY_BACKDROP_Y_OFFSET
                )
                reader.save_typetree(tree)
                changed = True
            elif backdrop_state != "patched":
                raise PatchError(f"Hollow Knight Mono inventory backdrop {name} changed")

        for name in MONO_TOUCH_BUTTONS:
            reader = _path_readers(
                resources,
                "RectTransform",
                f"_InControlManager/TouchControls/{name}",
            )[0]
            tree = reader.read_typetree()
            if _mono_touch_layout_state(tree) == "original":
                tree["m_AnchorMin"]["y"] = 1.0
                tree["m_AnchorMax"]["y"] = 1.0
                tree["m_AnchoredPosition"]["y"] = MONO_TOUCH_TARGET_POSITION_Y
                reader.save_typetree(tree)
                changed = True

        level2 = bundle.files["level2"]
        camera = _path_readers(level2, "Camera", "_GameCameras/HudCamera")[0]
        canvas = _path_readers(
            level2, "Transform", "_GameCameras/HudCamera/Hud Canvas"
        )[0]
        camera_tree = camera.read_typetree()
        canvas_tree = canvas.read_typetree()
        scene_hud_state = _mono_hud_layout_state(camera_tree, canvas_tree)
        if scene_hud_state == "original":
            camera_tree["orthographic size"] = MONO_HUD_ORTHO_TARGET
            canvas_tree["m_LocalPosition"]["x"] = MONO_HUD_CANVAS_TARGET_X
            canvas_tree["m_LocalPosition"]["y"] = MONO_HUD_CANVAS_TARGET_Y
            canvas_tree["m_LocalScale"]["x"] = MONO_HUD_SCALE_TARGET
            canvas_tree["m_LocalScale"]["y"] = MONO_HUD_SCALE_TARGET
            camera.save_typetree(camera_tree)
            canvas.save_typetree(canvas_tree)
            changed = True
        elif scene_hud_state != "patched":
            raise PatchError("Hollow Knight Mono active-scene HUD changed")

        hud_fsms = _script_component_reader(
            bundle, level2, "_GameCameras/HudCamera/Hud Canvas", "PlayMakerFSM"
        )
        recognized_fsms = []
        for reader in hud_fsms:
            fsm_state, offset = _mono_hud_fsm_state(reader.get_raw_data())
            if fsm_state != "unsupported":
                recognized_fsms.append((fsm_state, offset, reader))
        if len(recognized_fsms) != 1:
            raise PatchError("Hollow Knight Mono active-scene HUD animation changed")
        fsm_state, offset, hud_fsm = recognized_fsms[0]
        if fsm_state == "original" and offset is not None:
            raw = bytearray(hud_fsm.get_raw_data())
            source_pattern = next(
                (
                    pattern
                    for pattern in (
                        _hud_fsm_scale_pattern(MONO_HUD_SCALE_V4),
                        _hud_fsm_scale_pattern(MONO_HUD_SCALE_V5),
                    )
                    if raw[offset : offset + len(pattern)] == pattern
                ),
                None,
            )
            if source_pattern is None:
                raise PatchError("Hollow Knight Mono active-scene HUD scale changed")
            raw[offset : offset + len(source_pattern)] = _hud_fsm_scale_pattern(
                MONO_HUD_SCALE_TARGET
            )
            hud_fsm.set_raw_data(bytes(raw))
            changed = True

        inventory = _path_readers(
            level2, "Transform", "_GameCameras/HudCamera/Inventory"
        )[0]
        tree = inventory.read_typetree()
        inventory_state = _mono_inventory_layout_state(tree)
        if inventory_state == "original":
            tree["m_LocalPosition"]["x"] = INVENTORY_TARGET_POSITION[0]
            tree["m_LocalPosition"]["y"] = INVENTORY_TARGET_POSITION[1]
            tree["m_LocalScale"]["x"] = INVENTORY_SCALE_TARGET
            tree["m_LocalScale"]["y"] = INVENTORY_SCALE_TARGET
            inventory.save_typetree(tree)
            changed = True
        elif inventory_state != "patched":
            raise PatchError("Hollow Knight Mono active-scene inventory changed")

        for name, (source_x, source_y) in INVENTORY_BACKDROPS.items():
            reader = _path_readers(
                level2,
                "Transform",
                f"_GameCameras/HudCamera/Inventory/Border/{name}",
            )[0]
            tree = reader.read_typetree()
            backdrop_state = _mono_inventory_backdrop_state(tree, name)
            if backdrop_state == "original":
                tree["m_LocalScale"]["x"] = (
                    source_x * INVENTORY_BACKDROP_SCALE_MULTIPLIER
                )
                tree["m_LocalScale"]["y"] = (
                    source_y * INVENTORY_BACKDROP_SCALE_MULTIPLIER
                )
                tree["m_LocalPosition"]["y"] = (
                    INVENTORY_BACKDROP_SOURCE_Y[name]
                    + INVENTORY_BACKDROP_Y_OFFSET
                )
                reader.save_typetree(tree)
                changed = True
            elif backdrop_state != "patched":
                raise PatchError(
                    f"Hollow Knight Mono active-scene inventory backdrop {name} changed"
                )

        if changed:
            destination.write_bytes(bundle.save(packer="original"))
    finally:
        _close_unity(bundle, environment)
    return changed


def _patch_managed(source: Path, destination: Path) -> bool:
    targets, edits = _managed_targets(source)
    if any(target["state"] in ("unsupported", "ambiguous") for target in targets):
        raise PatchError("Hollow Knight Mono managed targets changed during patching")
    runtime_state = next(
        target["state"]
        for target in targets
        if target["name"] == INVENTORY_RUNTIME_TARGET_NAME
    )
    if not edits and runtime_state == "patched":
        return False
    data = bytearray(source.read_bytes())
    for offset, original, replacement in edits:
        if data[offset : offset + len(original)] != original:
            raise PatchError("Hollow Knight Mono managed target changed during patching")
        if len(original) != len(replacement):
            raise PatchError("Hollow Knight Mono managed edit is not length preserving")
        data[offset : offset + len(original)] = replacement
    if runtime_state == "original":
        _inject_managed_inventory_runtime(_ManagedAssembly(source), data)
    destination.write_bytes(data)
    return True


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
    mono_present = extracted.get(MONO_ENTRY) is not None and Path(
        extracted[MONO_ENTRY]
    ).is_file()
    unity_changed = (
        _patch_unity_mono(extracted[DATA_ENTRY], data_output)
        if mono_present
        else _patch_unity(extracted[DATA_ENTRY], data_output)
    )
    if unity_changed:
        replacements[DATA_ENTRY] = data_output

    if mono_present:
        managed_output = output_dir / "Assembly-CSharp.dll"
        if _patch_managed(extracted[MONO_ENTRY], managed_output):
            replacements[MONO_ENTRY] = managed_output

    if not mono_present:
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
