"""Semantic and contextual 4:3 patch for Hollow Knight: Silksong.

The native camera patch is required. The launcher UI adjustments are
best-effort because they belong to one known Android launcher rather than the
gameplay runtime itself. No APK, version, or signature hash is used as a
compatibility gate.
"""

from __future__ import annotations

import gc
import io
import math
from pathlib import Path
import struct
from typing import Any


LIBRARY_ENTRY = "lib/arm64-v8a/libil2cpp.so"
DATA_ENTRY = "assets/bin/Data/data.unity3d"
REQUIRED_ENTRIES = (LIBRARY_ENTRY,)

# Instructions following ForceCameraAspect.AutoScaleViewport's MinMaxFloat
# setup locate the method without assuming a branch displacement, constant-page
# address, library offset, version, or whole-file hash.
_NATIVE_CONTEXT = bytes.fromhex(
    "e80740f9"  # ldr x8, [sp, #8]
    "e0630091"  # add x0, sp, #0x18
    "e1031faa"  # mov x1, xzr
    "e80f00f9"  # str x8, [sp, #0x18]
)
_CONTEXT_FROM_PATCH_BASE = 40

_ORIGINAL_WORDS = {
    16: 0xF90007FF,  # str xzr, [sp, #8]
    20: 0x1E211809,  # fdiv s9, s0, s1
}
_PATCHED_WORDS = {
    0: 0x1E211809,   # fdiv s9, s0, s1
    16: 0x1E221000,  # fmov s0, #4.0
    20: 0x1E211001,  # fmov s1, #3.0
    24: 0x1E211800,  # fdiv s0, s0, s1
}

_SOURCE_LOADING_Y = -251.0
_PATCHED_LOADING_Y = -465.0


def _u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _put_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def _is_adrp(word: int, register: int) -> bool:
    return word & 0x9F00001F == 0x90000000 | register


def _is_bl(word: int) -> bool:
    return word & 0xFC000000 == 0x94000000


def _is_ldr_s_unsigned(word: int, base_register: int, target_register: int) -> bool:
    expected = 0xBD400000 | (base_register << 5) | target_register
    return word & 0xFFC003FF == expected


def _all_offsets(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while True:
        cursor = data.find(needle, cursor)
        if cursor < 0:
            return offsets
        offsets.append(cursor)
        cursor += 1


def _native_candidates(data: bytes | bytearray) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    raw = bytes(data)
    for context_offset in _all_offsets(raw, _NATIVE_CONTEXT):
        base = context_offset - _CONTEXT_FROM_PATCH_BASE
        if base < 0 or base + 60 > len(raw) or base % 4:
            continue
        if not _is_adrp(_u32(raw, base + 4), 9):
            continue
        if _u32(raw, base + 8) != 0x910023E0:  # add x0, sp, #8
            continue
        if _u32(raw, base + 12) != 0xAA1F03E1:  # mov x1, xzr
            continue
        if not _is_ldr_s_unsigned(_u32(raw, base + 28), 9, 1):
            continue
        if not _is_bl(_u32(raw, base + 32)):
            continue
        if _u32(raw, base + 36) != 0x1E204120:  # fcmp s9, s0
            continue

        patched = all(_u32(raw, base + rel) == word for rel, word in _PATCHED_WORDS.items())
        original = (
            _is_adrp(_u32(raw, base), 8)
            and all(_u32(raw, base + rel) == word for rel, word in _ORIGINAL_WORDS.items())
            and _is_ldr_s_unsigned(_u32(raw, base + 24), 8, 0)
        )
        if original or patched:
            candidates.append(
                {
                    "offset": base,
                    "state": "patched" if patched else "original",
                }
            )
    return candidates


def _probe_native(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4:6] != b"\x02\x01":
        return {"state": "unsupported", "reason": "not a 64-bit little-endian ELF"}
    if len(data) < 20 or struct.unpack_from("<H", data, 18)[0] != 183:
        return {"state": "unsupported", "reason": "not an AArch64 ELF"}
    candidates = _native_candidates(data)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return {"state": "ambiguous", "matches": len(candidates)}
    return {"state": "unsupported", "reason": "camera instruction context not found"}


def _load_bundle(path: Path):
    import UnityPy  # Imported lazily so listing games needs no optional dependency.

    environment = UnityPy.load(io.BytesIO(path.read_bytes()))
    if len(environment.files) != 1:
        raise ValueError("expected one top-level Unity bundle")
    bundle = next(iter(environment.files.values()))
    if getattr(bundle, "signature", None) != "UnityFS":
        raise ValueError("not a UnityFS bundle")
    return environment, bundle


def _objects_named(level, type_name: str, name: str) -> list[Any]:
    found: list[Any] = []
    for obj in level.objects.values():
        if obj.type.name != type_name:
            continue
        try:
            if obj.read(check_read=False).m_Name == name:
                found.append(obj)
        except Exception:
            continue
    return found


def _component_objects(level, game_object, type_name: str) -> list[Any]:
    result: list[Any] = []
    try:
        components = game_object.read(check_read=False).m_Component
    except Exception:
        return result
    for component in components:
        path_id = component.component.m_PathID
        obj = level.objects.get(path_id)
        if obj is not None and obj.type.name == type_name:
            result.append(obj)
    return result


def _child_names(level, game_object) -> set[str]:
    names: set[str] = set()
    transforms = _component_objects(level, game_object, "RectTransform")
    if len(transforms) != 1:
        return names
    try:
        children = transforms[0].read(check_read=False).m_Children
    except Exception:
        return names
    for pointer in children:
        child = level.objects.get(pointer.m_PathID)
        if child is None:
            continue
        try:
            child_game_object = level.objects[child.read(check_read=False).m_GameObject.m_PathID]
            names.add(child_game_object.read(check_read=False).m_Name)
        except Exception:
            continue
    return names


def _find_loading(level) -> dict[str, Any]:
    game_objects = _objects_named(level, "GameObject", "UpdateTip")
    if not game_objects:
        return {"state": "absent"}
    if len(game_objects) != 1:
        return {"state": "ambiguous", "matches": len(game_objects)}
    rects = _component_objects(level, game_objects[0], "RectTransform")
    if len(rects) != 1:
        return {"state": "ambiguous", "matches": len(rects)}
    try:
        rect = rects[0].read(check_read=False)
        semantic_layout = (
            math.isclose(rect.m_AnchorMin.x, 0.0)
            and math.isclose(rect.m_AnchorMin.y, 0.0)
            and math.isclose(rect.m_AnchorMax.x, 1.0)
            and math.isclose(rect.m_AnchorMax.y, 1.0)
            and math.isclose(rect.m_AnchoredPosition.x, -19.0)
            and math.isclose(rect.m_SizeDelta.x, 0.0)
            and math.isclose(rect.m_SizeDelta.y, -990.0)
        )
        if not semantic_layout:
            return {"state": "unsupported"}
        y = float(rect.m_AnchoredPosition.y)
    except Exception:
        return {"state": "unsupported"}
    if math.isclose(y, _SOURCE_LOADING_Y, abs_tol=0.01):
        state = "original"
    elif math.isclose(y, _PATCHED_LOADING_Y, abs_tol=0.01):
        state = "patched"
    else:
        state = "unsupported"
    return {"state": state, "path_id": rects[0].path_id, "y": y}


def _find_watermark(level) -> dict[str, Any]:
    game_objects = _objects_named(level, "GameObject", "WaterMark")
    if len(game_objects) != 1:
        return {"state": "absent" if not game_objects else "ambiguous"}
    game_object = game_objects[0]
    # The child hierarchy identifies the known port overlay. A coincidental
    # object with the same generic name is deliberately left untouched.
    if not {"Dev", "Version", "Tip"}.issubset(_child_names(level, game_object)):
        return {"state": "absent"}
    try:
        active = bool(game_object.read(check_read=False).m_IsActive)
    except Exception:
        return {"state": "absent"}
    return {
        "state": "original" if active else "patched",
        "path_id": game_object.path_id,
    }


def _probe_ui(path: Path) -> dict[str, Any]:
    environment = bundle = level = None
    try:
        environment, bundle = _load_bundle(path)
        level = bundle.files.get("level0")
        if level is None:
            return {"state": "absent", "targets": {}}
        loading = _find_loading(level)
        # Branding is deliberately not inspected here. Its state must never
        # appear in reports or influence compatibility/output creation.
        targets = (
            {"loading_label": loading}
            if loading["state"] in {"original", "patched"}
            else {}
        )
        return {
            "state": "original" if loading["state"] == "original" else "patched",
            "targets": targets,
        }
    except Exception:
        # Launcher/UI cleanup is optional and never gates the camera patch.
        return {"state": "skipped", "targets": {}}
    finally:
        del level, bundle, environment
        gc.collect()


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    missing = [entry for entry in REQUIRED_ENTRIES if entry not in extracted]
    if missing:
        return {"state": "unsupported", "targets": {}, "missing": missing}
    native = _probe_native(extracted[LIBRARY_ENTRY])
    ui = (
        _probe_ui(extracted[DATA_ENTRY])
        if DATA_ENTRY in extracted
        else {"state": "skipped", "targets": {}}
    )
    if native["state"] in {"unsupported", "ambiguous"}:
        state = native["state"]
    elif native["state"] == "original" or ui["state"] == "original":
        state = "original"
    else:
        state = "patched"
    return {"state": state, "targets": {"camera": native, "launcher_ui": ui}}


def _patch_native(source: Path, destination: Path, offset: int) -> None:
    data = bytearray(source.read_bytes())
    candidates = _native_candidates(data)
    if len(candidates) != 1 or candidates[0]["offset"] != offset:
        raise ValueError("Silksong camera target changed during patching")
    if candidates[0]["state"] == "original":
        for relative, word in _PATCHED_WORDS.items():
            _put_u32(data, offset + relative, word)
    destination.write_bytes(data)
    result = _probe_native(destination)
    if result["state"] != "patched":
        destination.unlink(missing_ok=True)
        raise ValueError("Silksong camera post-verification failed")


def _patch_ui(source: Path, destination: Path, target: dict[str, Any]) -> bool:
    environment = bundle = level = None
    try:
        environment, bundle = _load_bundle(source)
        level = bundle.files.get("level0")
        if level is None:
            return False
        loading = target.get("targets", {}).get("loading_label", {})
        if loading.get("state") != "original":
            return False
        obj = level.objects.get(loading.get("path_id"))
        if obj is None or obj.type.name != "RectTransform":
            raise ValueError("Silksong loading-label target changed during patching")
        rect = obj.read(check_read=False)
        rect.m_AnchoredPosition.y = _PATCHED_LOADING_Y
        rect.save()
        changed = True
        # This is the only branding lookup. It happens opportunistically after
        # the core loading-layout target has already required a bundle rewrite.
        # Missing, changed, or ambiguous branding is silently ignored.
        try:
            watermark = _find_watermark(level)
            if watermark.get("state") == "original":
                obj = level.objects.get(watermark.get("path_id"))
                if obj is not None and obj.type.name == "GameObject":
                    game_object = obj.read(check_read=False)
                    game_object.m_IsActive = False
                    game_object.save()
        except Exception:
            pass
        if not changed:
            return False
        destination.write_bytes(bundle.save(packer="original"))
        verified = _probe_ui(destination)
        loading_verified = verified.get("targets", {}).get("loading_label", {})
        if (
            verified.get("state") != "patched"
            or loading_verified.get("state") != "patched"
        ):
            destination.unlink(missing_ok=True)
            raise ValueError("Silksong launcher UI post-verification failed")
        return True
    finally:
        del level, bundle, environment
        gc.collect()


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    status = probe(extracted)
    if status["state"] in {"unsupported", "ambiguous"}:
        raise ValueError(f"Silksong patch target is {status['state']}")
    output_dir.mkdir(parents=True, exist_ok=True)
    replacements: dict[str, Path] = {}

    native = status["targets"]["camera"]
    if native["state"] == "original":
        destination = output_dir / "libil2cpp.so"
        _patch_native(extracted[LIBRARY_ENTRY], destination, native["offset"])
        replacements[LIBRARY_ENTRY] = destination

    ui = status["targets"]["launcher_ui"]
    if ui["state"] == "original" and DATA_ENTRY in extracted:
        destination = output_dir / "data.unity3d"
        if _patch_ui(extracted[DATA_ENTRY], destination, ui):
            replacements[DATA_ENTRY] = destination
    return replacements
