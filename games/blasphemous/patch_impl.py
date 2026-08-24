"""Target-driven 4:3 patch for Blasphemous's Unity IL2CPP Android build."""

from __future__ import annotations

import gc
import math
from pathlib import Path
import struct
from typing import Any, NamedTuple


DATA_ENTRY = "assets/bin/Data/datapack.unity3d"
ARM64_ENTRY = "lib/arm64-v8a/libil2cpp.so"
REQUIRED_ENTRIES = (DATA_ENTRY, ARM64_ENTRY)

SOURCE_HEIGHT = 360.0
TARGET_HEIGHT = 480.0
SOURCE_CAMERA_SIZE = 5.625
TARGET_CAMERA_SIZE = 7.5
SOURCE_POPUP_Y = 185.0
TARGET_POPUP_Y = 245.0


class PatchError(RuntimeError):
    """The supplied entries do not contain a safely recognizable target."""


class NativePattern(NamedTuple):
    name: str
    before: bytes
    original: bytes
    patched: bytes
    after: bytes


# The surrounding instructions exclude relocation-sensitive BL encodings. Each
# complete signature was unique in the tested library. The mutable instruction
# itself is never found by a fixed file offset.
NATIVE_PATTERNS = (
    NativePattern(
        "ScreenManager.FitScreenCamera reference height",
        b"",
        bytes.fromhex("8876a852"),
        bytes.fromhex("087ea852"),
        bytes.fromhex("0000221e0101271e0018211e0021201e"),
    ),
    NativePattern(
        "ScreenManager game RenderTexture height",
        bytes.fromhex("01508052"),
        bytes.fromhex("022d8052"),
        bytes.fromhex("023c8052"),
        bytes.fromhex("e3031f2ae4031faaf40300aa"),
    ),
    NativePattern(
        "ScreenManager UI RenderTexture height",
        bytes.fromhex("01508052"),
        bytes.fromhex("022d8052"),
        bytes.fromhex("023c8052"),
        bytes.fromhex("e3031f2ae4031faaf60300aa"),
    ),
    NativePattern(
        "ScreenManager strategy reference height",
        bytes.fromhex("8002221e0101271e"),
        bytes.fromhex("8876a852"),
        bytes.fromhex("087ea852"),
        bytes.fromhex("0018211e09e040b96102221e0201271e"),
    ),
    NativePattern(
        "ProCamera2D game-camera aspect",
        bytes.fromhex("007840f9800400b4"),
        bytes.fromhex("284fff90000540bde1031faa"),
        bytes.fromhex("6855955248f5a7720001271e"),
        bytes.fromhex("9cf91f9460b240f9c00300b4747a40f9758640f9"),
    ),
    # A development intermediate changed a shared 16:9/tablet threshold to 4:3.
    # The final patch restores 16:9 here and applies 4:3 only in the method above.
    NativePattern(
        "shared tablet-mode aspect threshold",
        bytes.fromhex("9ece5dc00ad7a33ccdcc4c3d022b073d"),
        bytes.fromhex("abaaaa3f"),
        bytes.fromhex("398ee33f"),
        bytes.fromhex("00feffc604ad01419a9999beca6b2840"),
    ),
)


def _unitypy():
    try:
        import UnityPy  # type: ignore
    except ImportError as exc:  # pragma: no cover - user-facing dependency path
        raise PatchError("UnityPy is required for the Blasphemous patch") from exc
    return UnityPy


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
    # A combination of recognized original and patched targets is safe to finish.
    return "original"


def _near(value: Any, expected: float, tolerance: float = 1e-4) -> bool:
    try:
        return math.isclose(float(value), expected, rel_tol=0.0, abs_tol=tolerance)
    except (TypeError, ValueError):
        return False


def _value_state(value: Any, original: float, patched: float) -> str:
    if _near(value, original):
        return "original"
    if _near(value, patched):
        return "patched"
    return "unsupported"


def _bundle_level(environment: Any) -> tuple[Any, Any]:
    files = list(environment.files.values())
    if len(files) != 1 or not hasattr(files[0], "files"):
        raise PatchError("datapack.unity3d is not a single UnityFS bundle")
    bundle = files[0]
    level = bundle.files.get("level1")
    if level is None:
        raise PatchError("datapack.unity3d has no level1 serialized file")
    return bundle, level


def _transform_path(transform: Any) -> str:
    names = [transform.m_GameObject.read().m_Name]
    seen: set[int] = set()
    while transform.m_Father and transform.m_Father.path_id:
        path_id = int(transform.m_Father.path_id)
        if path_id in seen:
            raise PatchError("Unity Transform hierarchy contains a cycle")
        seen.add(path_id)
        transform = transform.m_Father.read()
        names.append(transform.m_GameObject.read().m_Name)
    return "/".join(reversed(names))


def _game_object_path(game_object: Any) -> str:
    assets_file = game_object.object_reader.assets_file
    for pair in game_object.m_Component:
        reader = assets_file.objects.get(pair.component.path_id)
        if reader is not None and reader.type.name in ("Transform", "RectTransform"):
            return _transform_path(reader.read())
    raise PatchError(f"GameObject {game_object.m_Name!r} has no Transform")


def _path_readers(level: Any, type_name: str, path: str) -> list[Any]:
    matches: list[Any] = []
    for reader in level.objects.values():
        if reader.type.name != type_name:
            continue
        try:
            if type_name in ("Transform", "RectTransform"):
                candidate = _transform_path(reader.read())
            else:
                component = reader.read(check_read=False)
                candidate = _game_object_path(component.m_GameObject.read())
        except Exception:
            continue
        if candidate == path:
            matches.append(reader)
    return matches


def _typed_target(
    targets: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    *,
    name: str,
    readers: list[Any],
    value: Any,
    original: float,
    patched: float,
    mutation: str,
) -> None:
    if len(readers) != 1:
        state = "ambiguous" if len(readers) > 1 else "unsupported"
        targets.append(_target(name, state, entry=DATA_ENTRY, matches=len(readers)))
        return
    reader = readers[0]
    try:
        tree = reader.read_typetree()
        current = value(tree)
        state = _value_state(current, original, patched)
        targets.append(
            _target(name, state, entry=DATA_ENTRY, value=float(current), matches=1)
        )
        actions.append(
            {"kind": "typed", "reader": reader, "mutation": mutation, "state": state}
        )
    except Exception as exc:
        targets.append(_target(name, "unsupported", entry=DATA_ENTRY, reason=str(exc)))


def _layout_offsets(raw: bytes) -> list[tuple[int, str]]:
    """Locate {pixels-per-unit, *, width, height} in one component payload."""

    marker = struct.pack("<f", 32.0)
    width = struct.pack("<f", 640.0)
    original = struct.pack("<f", SOURCE_HEIGHT)
    patched = struct.pack("<f", TARGET_HEIGHT)
    matches: list[tuple[int, str]] = []
    cursor = 0
    while True:
        offset = raw.find(marker, cursor)
        if offset < 0:
            return matches
        height_offset = offset + 12
        if raw[offset + 8 : offset + 12] == width:
            value = raw[height_offset : height_offset + 4]
            if value == original:
                matches.append((height_offset, "original"))
            elif value == patched:
                matches.append((height_offset, "patched"))
        cursor = offset + 1


def _layout_target(
    level: Any,
    targets: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    *,
    name: str,
    game_object_path: str,
) -> None:
    candidates: list[tuple[Any, int, str]] = []
    for reader in _path_readers(level, "MonoBehaviour", game_object_path):
        raw = bytes(reader.get_raw_data())
        for offset, state in _layout_offsets(raw):
            candidates.append((reader, offset, state))
    if len(candidates) != 1:
        state = "ambiguous" if len(candidates) > 1 else "unsupported"
        targets.append(_target(name, state, entry=DATA_ENTRY, matches=len(candidates)))
        return
    reader, offset, state = candidates[0]
    targets.append(_target(name, state, entry=DATA_ENTRY, matches=1))
    actions.append(
        {"kind": "raw", "reader": reader, "offset": offset, "state": state}
    )


def _popup_candidates(level: Any) -> list[Any]:
    candidates: list[Any] = []
    for reader in level.objects.values():
        if reader.type.name != "RectTransform":
            continue
        try:
            tree = reader.read_typetree()
            game_object = reader.read().m_GameObject.read()
            if game_object.m_Name != "UI_POPUPACHIEVEMENT":
                continue
            anchor_min = tree["m_AnchorMin"]
            anchor_max = tree["m_AnchorMax"]
            size = tree["m_SizeDelta"]
            if not (
                _near(anchor_min["x"], 0.5)
                and _near(anchor_min["y"], 0.5)
                and _near(anchor_max["x"], 0.5)
                and _near(anchor_max["y"], 0.5)
                and _near(size["x"], 369.0)
                and _near(size["y"], 200.0)
            ):
                continue
        except Exception:
            continue
        candidates.append(reader)
    return candidates


def _discover_unity(level: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    targets: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    camera_readers = _path_readers(level, "Camera", "ProCamera2D/Camera")
    _typed_target(
        targets,
        actions,
        name="gameplay camera orthographic size",
        readers=camera_readers,
        value=lambda tree: tree["orthographic size"],
        original=SOURCE_CAMERA_SIZE,
        patched=TARGET_CAMERA_SIZE,
        mutation="camera",
    )
    _layout_target(
        level,
        targets,
        actions,
        name="pixel-perfect gameplay reference height",
        game_object_path="ProCamera2D/Camera",
    )
    _layout_target(
        level,
        targets,
        actions,
        name="Game UI virtual-canvas reference height",
        game_object_path="Game UI",
    )

    for path, label, mutation in (
        ("Virtual Camera/Pixel Resize/UIQuad", "UI output quad height", "ui_quad"),
        ("Virtual Camera/Pixel Resize/GameQuad", "game output quad height", "game_quad"),
    ):
        readers = _path_readers(level, "Transform", path)
        _typed_target(
            targets,
            actions,
            name=label,
            readers=readers,
            value=lambda tree: tree["m_LocalScale"]["y"],
            original=SOURCE_HEIGHT,
            patched=TARGET_HEIGHT,
            mutation=mutation,
        )

    popup = _popup_candidates(level)
    _typed_target(
        targets,
        actions,
        name="achievement popup resting position",
        readers=popup,
        value=lambda tree: tree["m_AnchoredPosition"]["y"],
        original=SOURCE_POPUP_Y,
        patched=TARGET_POPUP_Y,
        mutation="popup",
    )
    return targets, actions


def _unity_targets(path: Path) -> list[dict[str, Any]]:
    UnityPy = _unitypy()
    environment = UnityPy.load(str(path))
    bundle: Any | None = None
    try:
        bundle, level = _bundle_level(environment)
        targets, _ = _discover_unity(level)
        return targets
    finally:
        del bundle
        del environment
        gc.collect()


def _find_all(data: bytes | bytearray, needle: bytes) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while True:
        offset = data.find(needle, cursor)
        if offset < 0:
            return offsets
        offsets.append(offset)
        cursor = offset + 1


def _native_pattern_state(
    data: bytes | bytearray, pattern: NativePattern
) -> tuple[dict[str, Any], int | None]:
    original_signature = pattern.before + pattern.original + pattern.after
    patched_signature = pattern.before + pattern.patched + pattern.after
    original = _find_all(data, original_signature)
    patched = _find_all(data, patched_signature)
    total = len(original) + len(patched)
    if total == 1:
        if original:
            target = _target(pattern.name, "original", entry=ARM64_ENTRY, matches=1)
            return target, original[0] + len(pattern.before)
        target = _target(pattern.name, "patched", entry=ARM64_ENTRY, matches=1)
        return target, patched[0] + len(pattern.before)
    if total > 1:
        return (
            _target(
                pattern.name,
                "ambiguous",
                entry=ARM64_ENTRY,
                original_matches=len(original),
                patched_matches=len(patched),
            ),
            None,
        )
    return (
        _target(
            pattern.name,
            "unsupported",
            entry=ARM64_ENTRY,
            original_matches=0,
            patched_matches=0,
        ),
        None,
    )


def _discover_native(
    data: bytes | bytearray,
) -> tuple[list[dict[str, Any]], list[tuple[NativePattern, int, str]]]:
    if len(data) < 20 or bytes(data[:4]) != b"\x7fELF":
        raise PatchError("libil2cpp.so is not an ELF binary")
    byte_order = "<" if data[5] == 1 else ">" if data[5] == 2 else ""
    if not byte_order or struct.unpack_from(f"{byte_order}H", data, 18)[0] != 183:
        raise PatchError("libil2cpp.so is not an ARM64 ELF binary")

    targets: list[dict[str, Any]] = []
    actions: list[tuple[NativePattern, int, str]] = []
    for pattern in NATIVE_PATTERNS:
        target, offset = _native_pattern_state(data, pattern)
        targets.append(target)
        if offset is not None:
            actions.append((pattern, offset, target["state"]))
    return targets, actions


def _native_targets(path: Path) -> list[dict[str, Any]]:
    targets, _ = _discover_native(path.read_bytes())
    return targets


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Inspect the required entries without APK, signature, or version gates."""

    missing = [
        entry
        for entry in REQUIRED_ENTRIES
        if entry not in extracted or not Path(extracted[entry]).is_file()
    ]
    if missing:
        return {
            "state": "unsupported",
            "targets": [
                _target(entry, "unsupported", reason="required entry missing")
                for entry in missing
            ],
        }

    targets: list[dict[str, Any]] = []
    try:
        targets.extend(_unity_targets(Path(extracted[DATA_ENTRY])))
    except Exception as exc:
        targets.append(_target("Unity data bundle", "unsupported", reason=str(exc)))
    try:
        targets.extend(_native_targets(Path(extracted[ARM64_ENTRY])))
    except Exception as exc:
        targets.append(_target("ARM64 IL2CPP library", "unsupported", reason=str(exc)))
    return {"state": _overall(targets), "targets": targets}


def _patch_unity(source: Path, destination: Path) -> bool:
    UnityPy = _unitypy()
    environment = UnityPy.load(str(source))
    bundle: Any | None = None
    changed = False
    try:
        bundle, level = _bundle_level(environment)
        targets, actions = _discover_unity(level)
        if _overall(targets) in ("unsupported", "ambiguous"):
            raise PatchError("Unity targets changed during patch application")

        for action in actions:
            if action["state"] != "original":
                continue
            reader = action["reader"]
            if action["kind"] == "raw":
                raw = bytearray(reader.get_raw_data())
                offset = int(action["offset"])
                if raw[offset : offset + 4] != struct.pack("<f", SOURCE_HEIGHT):
                    raise PatchError("Unity layout target changed during application")
                raw[offset : offset + 4] = struct.pack("<f", TARGET_HEIGHT)
                reader.set_raw_data(bytes(raw))
            else:
                tree = reader.read_typetree()
                mutation = action["mutation"]
                if mutation == "camera":
                    tree["orthographic size"] = TARGET_CAMERA_SIZE
                elif mutation in ("ui_quad", "game_quad"):
                    tree["m_LocalScale"]["y"] = TARGET_HEIGHT
                elif mutation == "popup":
                    tree["m_AnchoredPosition"]["y"] = TARGET_POPUP_Y
                else:  # pragma: no cover - internal invariant
                    raise PatchError(f"unknown Unity mutation: {mutation}")
                reader.save_typetree(tree)
            changed = True

        if changed:
            destination.write_bytes(bundle.save(packer="original"))
    finally:
        del bundle
        del environment
        gc.collect()
    return changed


def _patch_native(source: Path, destination: Path) -> bool:
    data = bytearray(source.read_bytes())
    targets, actions = _discover_native(data)
    if _overall(targets) in ("unsupported", "ambiguous"):
        raise PatchError("native targets changed during patch application")
    changed = False
    for pattern, offset, state in actions:
        if state != "original":
            continue
        end = offset + len(pattern.original)
        if bytes(data[offset:end]) != pattern.original:
            raise PatchError(f"{pattern.name} changed during patch application")
        data[offset:end] = pattern.patched
        changed = True
    if changed:
        destination.write_bytes(data)
    return changed


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Write only the recognized replacement APK entries and verify them."""

    result = probe(extracted)
    if result["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"Blasphemous patch targets are {result['state']}")
    if result["state"] == "patched":
        return {}

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    replacements: dict[str, Path] = {}

    data_output = output_dir / "datapack.unity3d"
    if _patch_unity(Path(extracted[DATA_ENTRY]), data_output):
        replacements[DATA_ENTRY] = data_output

    library_output = output_dir / "libil2cpp-arm64-v8a.so"
    if _patch_native(Path(extracted[ARM64_ENTRY]), library_output):
        replacements[ARM64_ENTRY] = library_output

    verification_input = dict(extracted)
    verification_input.update(replacements)
    verification = probe(verification_input)
    if verification["state"] != "patched":
        raise PatchError(f"post-patch verification failed: {verification['state']}")
    return replacements
