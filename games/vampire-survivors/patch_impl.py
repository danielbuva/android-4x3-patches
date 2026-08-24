"""Semantic 4:3 UI and aspect-mask patch for Vampire Survivors."""

from __future__ import annotations

import gc
import io
from pathlib import Path
import struct
from typing import Any


DATAPACK_ENTRY = "assets/bin/Data/datapack.unity3d"
LIBRARY_ENTRY = "lib/arm64-v8a/libil2cpp.so"
REQUIRED_ENTRIES = (DATAPACK_ENTRY, LIBRARY_ENTRY)

_EXPECTED_SCENES = {
    "level1": "Canvas",
    "level2": "Canvas - App",
    "level3": "GameplayPreloader",
    "level4": "Canvas - Game UI",
}
_FORCE_ASPECT_OFFSET = 32
_SAFE_AREA_POINTER_OFFSET = 36

# The first instruction of AspectMask.Enable is replaced with ret. The shared
# body context identifies the method while allowing branch displacements and
# the method's file offset to move between compatible builds.
_ENABLE_CONTEXT = bytes.fromhex(
    "011040f9"  # ldr x1, [x0, #0x20]
    "22008052"  # mov w2, #1
    "f30300aa"  # mov x19, x0
)
_ORIGINAL_PROLOGUE = 0xA9BF4FFE  # stp x30, x19, [sp, #-16]!
_PATCHED_RETURN = 0xD65F03C0    # ret


def _u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _put_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def _is_bl(word: int) -> bool:
    return word & 0xFC000000 == 0x94000000


def _is_b(word: int) -> bool:
    return word & 0xFC000000 == 0x14000000


def _all_offsets(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while True:
        cursor = data.find(needle, cursor)
        if cursor < 0:
            return offsets
        offsets.append(cursor)
        cursor += 1


def _enable_candidates(data: bytes | bytearray) -> list[dict[str, Any]]:
    raw = bytes(data)
    candidates: list[dict[str, Any]] = []
    for context in _all_offsets(raw, _ENABLE_CONTEXT):
        base = context - 4
        if base < 0 or base + 60 > len(raw) or base % 4:
            continue
        # Validate the four repeated image toggles around the wildcard BL
        # displacements. This makes the otherwise generic opening unique.
        expected_words = {
            20: 0xF9401661,
            24: 0x52800022,
            32: 0xF9401A61,
            36: 0x52800022,
            44: 0xF9401E61,
            48: 0x52800022,
            52: 0xA8C14FFE,
        }
        if not all(_u32(raw, base + rel) == word for rel, word in expected_words.items()):
            continue
        if not all(_is_bl(_u32(raw, base + rel)) for rel in (16, 28, 40)):
            continue
        if not _is_b(_u32(raw, base + 56)):
            continue
        first = _u32(raw, base)
        if first == _ORIGINAL_PROLOGUE:
            state = "original"
        elif first == _PATCHED_RETURN:
            state = "patched"
        else:
            continue
        candidates.append({"state": state, "offset": base})
    return candidates


def _probe_library(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4:6] != b"\x02\x01":
        return {"state": "unsupported", "reason": "not a 64-bit little-endian ELF"}
    if len(data) < 20 or struct.unpack_from("<H", data, 18)[0] != 183:
        return {"state": "unsupported", "reason": "not an AArch64 ELF"}
    candidates = _enable_candidates(data)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return {"state": "ambiguous", "matches": len(candidates)}
    return {"state": "unsupported", "reason": "AspectMask.Enable context not found"}


def _load_bundle(path: Path):
    import UnityPy  # Lazy so discovery/listing works before dependencies are installed.

    environment = UnityPy.load(io.BytesIO(path.read_bytes()))
    if len(environment.files) != 1:
        raise ValueError("expected one top-level Unity bundle")
    bundle = next(iter(environment.files.values()))
    if getattr(bundle, "signature", None) != "UnityFS":
        raise ValueError("not a UnityFS bundle")
    return environment, bundle


def _read_pointer(raw: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<iq", raw, offset)


def _game_object_name(level, file_id: int, path_id: int) -> str | None:
    if file_id != 0:
        return None
    obj = level.objects.get(path_id)
    if obj is None or obj.type.name != "GameObject":
        return None
    try:
        return str(obj.read(check_read=False).m_Name)
    except Exception:
        return None


def _uihelper_candidates(level, expected_game_object_name: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for obj in level.objects.values():
        if obj.type.name != "MonoBehaviour":
            continue
        raw = bytes(obj.get_raw_data())
        if len(raw) < _SAFE_AREA_POINTER_OFFSET + 12:
            continue
        try:
            game_file, game_path = _read_pointer(raw, 0)
            script_file, script_path = _read_pointer(raw, 16)
            safe_file, safe_path = _read_pointer(raw, _SAFE_AREA_POINTER_OFFSET)
        except struct.error:
            continue
        if _game_object_name(level, game_file, game_path) != expected_game_object_name:
            continue
        if raw[12] != 1 or script_path == 0:
            continue
        safe_transform = level.objects.get(safe_path) if safe_file == 0 else None
        if safe_transform is None or safe_transform.type.name != "RectTransform":
            continue
        safe_raw = bytes(safe_transform.get_raw_data())
        if len(safe_raw) < 12:
            continue
        safe_game_file, safe_game_path = _read_pointer(safe_raw, 0)
        if _game_object_name(level, safe_game_file, safe_game_path) != "Safe Area":
            continue
        flag = raw[_FORCE_ASPECT_OFFSET]
        if flag not in (0, 1):
            continue
        candidates.append(
            {
                "state": "original" if flag == 1 else "patched",
                "path_id": obj.path_id,
                "script": [script_file, script_path],
                "safe_area_path_id": safe_path,
            }
        )
    return candidates


def _probe_datapack(path: Path) -> dict[str, Any]:
    environment = bundle = None
    try:
        environment, bundle = _load_bundle(path)
        targets: dict[str, Any] = {}
        script_pointers: set[tuple[int, int]] = set()
        for level_name, game_object_name in _EXPECTED_SCENES.items():
            level = bundle.files.get(level_name)
            if level is None:
                return {"state": "unsupported", "reason": f"missing {level_name}"}
            candidates = _uihelper_candidates(level, game_object_name)
            if len(candidates) != 1:
                state = "ambiguous" if len(candidates) > 1 else "unsupported"
                targets[level_name] = {"state": state, "matches": len(candidates)}
                return {"state": state, "targets": targets}
            targets[level_name] = candidates[0]
            script_pointers.add(tuple(candidates[0]["script"]))
        # All four instances must reference the same UIHelper script. This
        # guards against matching unrelated MonoBehaviours with similar fields.
        if len(script_pointers) != 1:
            return {"state": "ambiguous", "targets": targets, "reason": "script mismatch"}
        states = {target["state"] for target in targets.values()}
        state = "patched" if states == {"patched"} else "original"
        return {"state": state, "targets": targets}
    except Exception as error:
        return {"state": "unsupported", "reason": str(error)}
    finally:
        del bundle, environment
        gc.collect()


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    missing = [entry for entry in REQUIRED_ENTRIES if entry not in extracted]
    if missing:
        return {"state": "unsupported", "targets": {}, "missing": missing}
    ui = _probe_datapack(extracted[DATAPACK_ENTRY])
    mask = _probe_library(extracted[LIBRARY_ENTRY])
    states = {ui["state"], mask["state"]}
    if "ambiguous" in states:
        state = "ambiguous"
    elif "unsupported" in states:
        state = "unsupported"
    elif states == {"patched"}:
        state = "patched"
    else:
        # A recognized partial patch is safe to complete.
        state = "original"
    return {"state": state, "targets": {"ui_safe_areas": ui, "aspect_mask": mask}}


def _patch_datapack(source: Path, destination: Path, target: dict[str, Any]) -> None:
    environment = bundle = None
    try:
        environment, bundle = _load_bundle(source)
        changed = False
        for level_name, details in target["targets"].items():
            if details["state"] != "original":
                continue
            obj = bundle.files[level_name].objects.get(details["path_id"])
            if obj is None or obj.type.name != "MonoBehaviour":
                raise ValueError(f"{level_name} UIHelper changed during patching")
            raw = bytearray(obj.get_raw_data())
            if raw[_FORCE_ASPECT_OFFSET] != 1:
                raise ValueError(f"{level_name} UIHelper state changed during patching")
            raw[_FORCE_ASPECT_OFFSET] = 0
            obj.set_raw_data(bytes(raw))
            changed = True
        if not changed:
            return
        destination.write_bytes(bundle.save(packer="original"))
    finally:
        del bundle, environment
        gc.collect()
    verified = _probe_datapack(destination)
    if verified["state"] != "patched":
        destination.unlink(missing_ok=True)
        raise ValueError("Vampire Survivors UI post-verification failed")


def _patch_library(source: Path, destination: Path, offset: int) -> None:
    data = bytearray(source.read_bytes())
    candidates = _enable_candidates(data)
    if len(candidates) != 1 or candidates[0]["offset"] != offset:
        raise ValueError("Vampire Survivors aspect-mask target changed during patching")
    if candidates[0]["state"] == "original":
        _put_u32(data, offset, _PATCHED_RETURN)
    destination.write_bytes(data)
    verified = _probe_library(destination)
    if verified["state"] != "patched":
        destination.unlink(missing_ok=True)
        raise ValueError("Vampire Survivors aspect-mask post-verification failed")


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    status = probe(extracted)
    if status["state"] in {"unsupported", "ambiguous"}:
        raise ValueError(f"Vampire Survivors patch target is {status['state']}")
    output_dir.mkdir(parents=True, exist_ok=True)
    replacements: dict[str, Path] = {}

    ui = status["targets"]["ui_safe_areas"]
    if ui["state"] == "original":
        destination = output_dir / "datapack.unity3d"
        _patch_datapack(extracted[DATAPACK_ENTRY], destination, ui)
        replacements[DATAPACK_ENTRY] = destination

    mask = status["targets"]["aspect_mask"]
    if mask["state"] == "original":
        destination = output_dir / "libil2cpp.so"
        _patch_library(extracted[LIBRARY_ENTRY], destination, mask["offset"])
        replacements[LIBRARY_ENTRY] = destination
    return replacements
