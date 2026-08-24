"""Semantic 4:3 patch for Skul's GameBase Unity scene."""

from __future__ import annotations

import gc
import math
import struct
from pathlib import Path
from typing import Any


ENTRY = "assets/bin/Data/datapack.unity3d"
REQUIRED_ENTRIES = (ENTRY,)
SERIALIZED_FILE = "level3"

GAMEPLAY_SOURCE = 360
GAMEPLAY_TARGET = 480
UI_WIDTH = 1920.0
UI_SOURCE = 1080.0
UI_TARGET = 1440.0


class PatchError(RuntimeError):
    pass


def _unitypy():
    try:
        import UnityPy  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise PatchError("UnityPy is required for the Skul patch") from exc
    return UnityPy


def _load(path: Path) -> tuple[Any, Any, Any]:
    UnityPy = _unitypy()
    environment = UnityPy.load(str(path))
    files = list(environment.files.values())
    if len(files) != 1 or not hasattr(files[0], "files"):
        raise PatchError("datapack.unity3d is not a single UnityFS bundle")
    bundle = files[0]
    serialized = bundle.files.get(SERIALIZED_FILE)
    if serialized is None or not hasattr(serialized, "objects"):
        raise PatchError("Unity bundle is missing the GameBase level3 scene")
    return environment, bundle, serialized


def _close(*objects: Any) -> None:
    for obj in objects:
        del obj
    gc.collect()


def _near(value: float, expected: float) -> bool:
    return math.isclose(float(value), expected, rel_tol=0.0, abs_tol=1e-4)


def _state(value: float, source: float, patched: float) -> str:
    if _near(value, source):
        return "original"
    if _near(value, patched):
        return "patched"
    return "unsupported"


def _target(name: str, state: str, **details: Any) -> dict[str, Any]:
    target: dict[str, Any] = {"name": name, "state": state}
    target.update(details)
    return target


def _overall(targets: list[dict[str, Any]]) -> str:
    states = {target["state"] for target in targets}
    if "ambiguous" in states:
        return "ambiguous"
    if "unsupported" in states:
        return "unsupported"
    if states == {"patched"}:
        return "patched"
    return "original"


def _game_object_name(serialized: Any, raw: bytes) -> str | None:
    if len(raw) < 12:
        return None
    file_id, path_id = struct.unpack_from("<iq", raw, 0)
    if file_id != 0:
        return None
    reader = serialized.objects.get(path_id)
    if reader is None or reader.type.name != "GameObject":
        return None
    try:
        return reader.read().m_Name
    except Exception:
        return None


def _camera_pattern(raw: bytes) -> tuple[str, int] | None:
    if len(raw) < 24:
        return None
    matches: list[tuple[str, int]] = []
    for offset in range(0, max(0, len(raw) - 24) + 1, 4):
        sample_size, width, height = struct.unpack_from("<iii", raw, offset)
        if sample_size != 32 or width != 640:
            continue
        if struct.unpack_from("<iii", raw, offset + 12) != (0, 0, 0):
            continue
        state = (
            "original"
            if height == GAMEPLAY_SOURCE
            else "patched"
            if height == GAMEPLAY_TARGET
            else "unsupported"
        )
        if state != "unsupported":
            matches.append((state, offset + 8))
    if len(matches) > 1:
        return "ambiguous", -1
    return matches[0] if matches else None


def _canvas_pattern(raw: bytes) -> tuple[str, int] | None:
    if len(raw) < 24:
        return None
    matches: list[tuple[str, int]] = []
    for offset in range(0, max(0, len(raw) - 24) + 1, 4):
        if struct.unpack_from("<i", raw, offset)[0] != 1:
            continue
        width, height = struct.unpack_from("<ff", raw, offset + 12)
        if not _near(width, UI_WIDTH):
            continue
        if struct.unpack_from("<i", raw, offset + 20)[0] != 1:
            continue
        state = _state(height, UI_SOURCE, UI_TARGET)
        if state != "unsupported":
            matches.append((state, offset + 16))
    if len(matches) > 1:
        return "ambiguous", -1
    return matches[0] if matches else None


def _mono_candidates(serialized: Any, game_object: str, kind: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    matcher = _camera_pattern if kind == "camera" else _canvas_pattern
    for reader in serialized.objects.values():
        if reader.type.name != "MonoBehaviour":
            continue
        try:
            raw = reader.get_raw_data()
        except Exception:
            continue
        if _game_object_name(serialized, raw) != game_object:
            continue
        matched = matcher(raw)
        if matched is not None:
            state, value_offset = matched
            candidates.append(
                {
                    "reader": reader,
                    "state": state,
                    "value_offset": value_offset,
                    "path_id": reader.path_id,
                }
            )
    return candidates


def _rect_candidates(serialized: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for reader in serialized.objects.values():
        if reader.type.name != "RectTransform":
            continue
        try:
            transform = reader.read()
            if transform.m_GameObject.read().m_Name != "Inside Of Letterbox":
                continue
            tree = reader.read_typetree()
            size = tree["m_SizeDelta"]
            anchor_min = tree["m_AnchorMin"]
            anchor_max = tree["m_AnchorMax"]
            pivot = tree["m_Pivot"]
            if not _near(size["x"], UI_WIDTH):
                continue
            if not all(
                _near(vector[key], 0.5)
                for vector in (anchor_min, anchor_max, pivot)
                for key in ("x", "y")
            ):
                continue
            state = _state(size["y"], UI_SOURCE, UI_TARGET)
            if state != "unsupported":
                candidates.append(
                    {
                        "reader": reader,
                        "state": state,
                        "path_id": reader.path_id,
                        "value": float(size["y"]),
                    }
                )
        except Exception:
            continue
    return candidates


def _inspect(path: Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    environment, bundle, serialized = _load(path)
    targets: list[dict[str, Any]] = []
    located: dict[str, list[dict[str, Any]]] = {}
    try:
        located["camera"] = _mono_candidates(serialized, "Main Camera", "camera")
        located["canvas"] = _mono_candidates(serialized, "UI Canvas", "canvas")
        located["safe_rect"] = _rect_candidates(serialized)
        labels = {
            "camera": "GameBase/Main Camera pixel-perfect reference",
            "canvas": "GameBase/UI Canvas reference",
            "safe_rect": "GameBase/Inside Of Letterbox safe area",
        }
        for key in ("camera", "canvas", "safe_rect"):
            matches = located[key]
            if len(matches) == 1:
                targets.append(
                    _target(
                        labels[key],
                        matches[0]["state"],
                        object_path_id=matches[0]["path_id"],
                    )
                )
            else:
                targets.append(
                    _target(
                        labels[key],
                        "ambiguous" if len(matches) > 1 else "unsupported",
                        matches=len(matches),
                    )
                )
    finally:
        _close(serialized, bundle, environment)
    return targets, located


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    source = extracted.get(ENTRY)
    if source is None or not source.is_file():
        target = _target(ENTRY, "unsupported", reason="required entry missing")
        return {"state": "unsupported", "targets": [target]}
    try:
        targets, _ = _inspect(source)
    except Exception as exc:
        targets = [_target("GameBase Unity scene", "unsupported", reason=str(exc))]
    return {"state": _overall(targets), "targets": targets}


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    result = probe(extracted)
    if result["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"Skul patch targets are {result['state']}")
    if result["state"] == "patched":
        return {}

    source = extracted[ENTRY]
    environment, bundle, serialized = _load(source)
    try:
        camera = _mono_candidates(serialized, "Main Camera", "camera")[0]
        if camera["state"] == "original":
            reader = camera["reader"]
            raw = bytearray(reader.get_raw_data())
            struct.pack_into("<i", raw, camera["value_offset"], GAMEPLAY_TARGET)
            reader.set_raw_data(bytes(raw))

        canvas = _mono_candidates(serialized, "UI Canvas", "canvas")[0]
        if canvas["state"] == "original":
            reader = canvas["reader"]
            raw = bytearray(reader.get_raw_data())
            struct.pack_into("<f", raw, canvas["value_offset"], UI_TARGET)
            reader.set_raw_data(bytes(raw))

        safe_rect = _rect_candidates(serialized)[0]
        if safe_rect["state"] == "original":
            reader = safe_rect["reader"]
            tree = reader.read_typetree()
            tree["m_SizeDelta"]["y"] = UI_TARGET
            reader.save_typetree(tree)

        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / "datapack.unity3d"
        destination.write_bytes(bundle.save(packer="original"))
    finally:
        _close(serialized, bundle, environment)

    verification = probe({ENTRY: destination})
    if verification["state"] != "patched":
        raise PatchError(f"post-patch verification failed: {verification['state']}")
    return {ENTRY: destination}
