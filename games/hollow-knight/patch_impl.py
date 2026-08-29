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
HUD_CANVAS_SOURCE_Y = 6.6
HUD_CANVAS_TARGET_Y = HUD_CANVAS_SOURCE_Y + HUD_ORTHO_TARGET - HUD_ORTHO_SOURCE
CAMERA_LIMIT_SOURCE = 8.300000190734863
CAMERA_LIMIT_TARGET = CAMERA_LIMIT_SOURCE * SOURCE_ASPECT / TARGET_ASPECT
REFERENCE_UI_HEIGHT = 1080.0
REFERENCE_UI_HALF_HEIGHT = REFERENCE_UI_HEIGHT / 2.0

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


def _mono_unity_targets(path: Path) -> list[dict[str, Any]]:
    UnityPy = _unitypy()
    environment = UnityPy.load(str(path))
    bundle = _bundle_file(environment)
    targets: list[dict[str, Any]] = []
    try:
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
            cameras = _path_readers(resources, "Camera", "_GameCameras/HudCamera")
            if len(cameras) != 1:
                state = "ambiguous" if len(cameras) > 1 else "unsupported"
                targets.append(_target("Mono HUD camera", state, matches=len(cameras)))
            else:
                value = cameras[0].read_typetree()["orthographic size"]
                targets.append(
                    _target(
                        "Mono HUD camera",
                        _value_state(value, HUD_ORTHO_SOURCE, HUD_ORTHO_TARGET),
                        value=float(value),
                    )
                )

            canvases = _path_readers(
                resources, "Transform", "_GameCameras/HudCamera/Hud Canvas"
            )
            if len(canvases) != 1:
                state = "ambiguous" if len(canvases) > 1 else "unsupported"
                targets.append(_target("Mono HUD top edge", state, matches=len(canvases)))
            else:
                value = canvases[0].read_typetree()["m_LocalPosition"]["y"]
                targets.append(
                    _target(
                        "Mono HUD top edge",
                        _value_state(value, HUD_CANVAS_SOURCE_Y, HUD_CANVAS_TARGET_Y),
                        value=float(value),
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
                if (
                    _near(min_y, 0.5)
                    and _near(max_y, 0.5)
                    and _near(position_y, 125.0)
                ):
                    state = "original"
                elif (
                    _near(min_y, 1.0)
                    and _near(max_y, 1.0)
                    and _near(position_y, 125.0 - REFERENCE_UI_HALF_HEIGHT)
                ):
                    state = "patched"
                else:
                    state = "unsupported"
                targets.append(
                    _target(
                        target_name,
                        state,
                        anchor_min_y=min_y,
                        anchor_max_y=max_y,
                        anchored_position_y=position_y,
                    )
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


def _patch_unity_mono(source: Path, destination: Path) -> bool:
    UnityPy = _unitypy()
    environment = UnityPy.load(str(source))
    bundle = _bundle_file(environment)
    changed = False
    try:
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
        camera = _path_readers(resources, "Camera", "_GameCameras/HudCamera")[0]
        tree = camera.read_typetree()
        if _near(tree["orthographic size"], HUD_ORTHO_SOURCE):
            tree["orthographic size"] = HUD_ORTHO_TARGET
            camera.save_typetree(tree)
            changed = True

        canvas = _path_readers(
            resources, "Transform", "_GameCameras/HudCamera/Hud Canvas"
        )[0]
        tree = canvas.read_typetree()
        if _near(tree["m_LocalPosition"]["y"], HUD_CANVAS_SOURCE_Y):
            tree["m_LocalPosition"]["y"] = HUD_CANVAS_TARGET_Y
            canvas.save_typetree(tree)
            changed = True

        for name in MONO_TOUCH_BUTTONS:
            reader = _path_readers(
                resources,
                "RectTransform",
                f"_InControlManager/TouchControls/{name}",
            )[0]
            tree = reader.read_typetree()
            if (
                _near(tree["m_AnchorMin"]["y"], 0.5)
                and _near(tree["m_AnchorMax"]["y"], 0.5)
                and _near(tree["m_AnchoredPosition"]["y"], 125.0)
            ):
                tree["m_AnchorMin"]["y"] = 1.0
                tree["m_AnchorMax"]["y"] = 1.0
                tree["m_AnchoredPosition"]["y"] = 125.0 - REFERENCE_UI_HALF_HEIGHT
                reader.save_typetree(tree)
                changed = True

        if changed:
            destination.write_bytes(bundle.save(packer="original"))
    finally:
        _close_unity(bundle, environment)
    return changed


def _patch_managed(source: Path, destination: Path) -> bool:
    targets, edits = _managed_targets(source)
    if any(target["state"] in ("unsupported", "ambiguous") for target in targets):
        raise PatchError("Hollow Knight Mono managed targets changed during patching")
    if not edits:
        return False
    data = bytearray(source.read_bytes())
    for offset, original, replacement in edits:
        if data[offset : offset + len(original)] != original:
            raise PatchError("Hollow Knight Mono managed target changed during patching")
        if len(original) != len(replacement):
            raise PatchError("Hollow Knight Mono managed edit is not length preserving")
        data[offset : offset + len(original)] = replacement
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
