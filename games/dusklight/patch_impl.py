"""Guarded nested-container 4:3 patch for Dusklight v1.4.1 arm64."""

from __future__ import annotations

import copy
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any


MANIFEST_ENTRY = "AndroidManifest.xml"
DATA1_ENTRY = "assets/data1"
CLASSES_ENTRY = "classes2.dex"
LAUNCH_RUNTIME_ENTRY = "lib/arm64-v8a/libapkvisionorg.so"
OVERLAY_RUNTIME_ENTRY = "lib/arm64-v8a/libAPKVISION.so"
REQUIRED_ENTRIES = (
    DATA1_ENTRY,
)

MANIFEST_SHA256 = "a3268d549ef0b39e23e6b6b984449e68c3fa33ca6f931817dcd7dd33000a2e3f"
CLASSES_SHA256 = "dd345f43820aee0084d67b7f496ab86da8776004015c76b69e2a75d601137089"
LAUNCH_RUNTIME_SHA256 = "3f89da72825933bd783e34b96d29fc5c6ad918ba6cb66beb10b1c02b36b4651f"
SOURCE_OVERLAY_SHA256 = "e88ac07b305fd3546c61e431b379f28187a065cb1f393b078c72d63690572ed9"

SOURCE_ISO_ENTRY = "files/Legend of Zelda, The - Twilight Princess (USA) apkvision.iso"
PATCHED_ISO_ENTRY = "files/Legend of Zelda, The - Twilight Princess (USA).iso"
CONFIG_ENTRY = "files/config.json"

SOURCE_CONFIG = {
    "backend.isoPath": (
        "/data/user/0/dev.twilitrealm.dusk/files/"
        "Legend of Zelda, The - Twilight Princess (USA) apkvision.iso"
    ),
    "backend.isoVerification": 1,
    "game.enableTouchControls": True,
}
PATCHED_ISO_PATH = (
    "/data/user/0/dev.twilitrealm.dusk/files/"
    "Legend of Zelda, The - Twilight Princess (USA).iso"
)

FOUR_THREE_CONFIG = {
    "video.lockAspectRatio": True,
    "game.menuScalingMode": 0,
    "game.disableCutscenePillarboxing": False,
}


class PatchError(RuntimeError):
    """The supplied nested build does not match the audited Dusklight target."""


def _skip_space(text: str, position: int) -> int:
    while position < len(text) and text[position] in " \t\r\n":
        position += 1
    return position


def _string_end(text: str, position: int) -> int:
    if position >= len(text) or text[position] != '"':
        raise ValueError("expected JSON string")
    position += 1
    while position < len(text):
        character = text[position]
        if character == "\\":
            position += 2
            continue
        position += 1
        if character == '"':
            return position
    raise ValueError("unterminated JSON string")


def _value_end(text: str, position: int) -> int:
    """Return the end of one already-validated top-level JSON value."""

    if text[position] == '"':
        return _string_end(text, position)
    if text[position] in "[{":
        stack = [text[position]]
        position += 1
        while position < len(text) and stack:
            character = text[position]
            if character == '"':
                position = _string_end(text, position)
                continue
            if character in "[{":
                stack.append(character)
            elif character in "]}":
                opener = stack.pop()
                if (opener, character) not in {("[", "]"), ("{", "}")}:
                    raise ValueError("mismatched JSON container")
            position += 1
        if stack:
            raise ValueError("unterminated JSON container")
        return position
    end = position
    while end < len(text) and text[end] not in ",}":
        end += 1
    return end - len(text[position:end]) + len(text[position:end].rstrip())


def _top_level_members(text: str) -> tuple[list[tuple[str, int, int, int]], int, int]:
    """Return ``(key, key_start, value_start, value_end)`` and root braces.

    This tiny locator is intentionally not a second JSON validator.  The
    caller first uses :func:`json.loads`; the positions are only used to alter
    the three 4:3 values while retaining every unrelated byte of the user's
    config.
    """

    start = _skip_space(text, 0)
    if start >= len(text) or text[start] != "{":
        raise ValueError("config root is not an object")
    position = _skip_space(text, start + 1)
    members: list[tuple[str, int, int, int]] = []
    if position < len(text) and text[position] == "}":
        return members, start, position
    while position < len(text):
        key_start = position
        key_end = _string_end(text, key_start)
        key = json.loads(text[key_start:key_end])
        position = _skip_space(text, key_end)
        if position >= len(text) or text[position] != ":":
            raise ValueError("expected colon after config key")
        value_start = _skip_space(text, position + 1)
        value_end = _value_end(text, value_start)
        members.append((key, key_start, value_start, value_end))
        position = _skip_space(text, value_end)
        if position < len(text) and text[position] == ",":
            position = _skip_space(text, position + 1)
            continue
        if position < len(text) and text[position] == "}":
            return members, start, position
        raise ValueError("expected comma or closing brace in config")
    raise ValueError("unterminated config object")


def _decode_config(data: bytes) -> tuple[str, bytes]:
    bom = b"\xef\xbb\xbf" if data.startswith(b"\xef\xbb\xbf") else b""
    body = data[len(bom) :]
    return body.decode("utf-8"), bom


def _config_analysis(data: bytes) -> tuple[str, str | None, dict[str, Any]]:
    try:
        text, _bom = _decode_config(data)
        decoded = json.loads(text)
        members, _root_start, _root_end = _top_level_members(text)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return "unsupported", f"invalid embedded config: {exc}", {}
    if not isinstance(decoded, dict):
        return "unsupported", "embedded config root is not an object", {}

    required_names = set(FOUR_THREE_CONFIG)
    member_names = [name for name, *_positions in members]
    duplicates = sorted(
        name for name in required_names if member_names.count(name) > 1
    )
    if duplicates:
        return (
            "ambiguous",
            "duplicate required config keys: " + ", ".join(duplicates),
            decoded,
        )

    all_patched = True
    for name, wanted in FOUR_THREE_CONFIG.items():
        if name not in decoded:
            all_patched = False
            continue
        current = decoded[name]
        if isinstance(wanted, bool):
            compatible_type = isinstance(current, bool)
            matches = current is wanted
        else:
            compatible_type = isinstance(current, int) and not isinstance(current, bool)
            matches = compatible_type and current == wanted
        if not compatible_type:
            return (
                "unsupported",
                f"required config key {name!r} has an incompatible value type",
                decoded,
            )
        if not matches:
            all_patched = False
    return ("patched" if all_patched else "original"), None, decoded


def _json_literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _patch_config(data: bytes, *, clean_iso_path: bool = False) -> bytes:
    """Patch only recognized top-level values, preserving unrelated text."""

    state, detail, decoded = _config_analysis(data)
    if state not in {"original", "patched"}:
        raise PatchError(detail or f"embedded config is {state}")

    text, bom = _decode_config(data)
    members, root_start, _root_end = _top_level_members(text)
    positions: dict[str, tuple[int, int]] = {
        name: (value_start, value_end)
        for name, _key_start, value_start, value_end in members
    }
    operations: list[tuple[int, int, str]] = []
    missing: list[tuple[str, Any]] = []
    for name, wanted in FOUR_THREE_CONFIG.items():
        if name in positions:
            if decoded.get(name) != wanted or type(decoded.get(name)) is not type(wanted):
                start, end = positions[name]
                operations.append((start, end, _json_literal(wanted)))
        else:
            missing.append((name, wanted))

    member_names = [name for name, *_positions in members]
    if (
        clean_iso_path
        and member_names.count("backend.isoPath") == 1
        and decoded.get("backend.isoPath") == SOURCE_CONFIG["backend.isoPath"]
    ):
        path_position = positions.get("backend.isoPath")
        if path_position is not None:
            operations.append(
                (*path_position, _json_literal(PATCHED_ISO_PATH))
            )

    if missing:
        if members:
            insertion_at = members[-1][3]
            if "\r\n" in text:
                newline = "\r\n"
            elif "\n" in text:
                newline = "\n"
            else:
                newline = ""
            if newline:
                first_key_start = members[0][1]
                line_start = text.rfind(newline, 0, first_key_start)
                indent_start = line_start + len(newline) if line_start >= 0 else root_start + 1
                indent = text[indent_start:first_key_start]
                if not indent.isspace():
                    indent = "    "
                added = ("," + newline + indent).join(
                    f'{_json_literal(name)}: {_json_literal(value)}'
                    for name, value in missing
                )
                insertion = "," + newline + indent + added
            else:
                insertion = ", " + ", ".join(
                    f'{_json_literal(name)}: {_json_literal(value)}'
                    for name, value in missing
                )
            operations.append((insertion_at, insertion_at, insertion))
        else:
            insertion_at = root_start + 1
            if "\r\n" in text:
                newline = "\r\n"
            elif "\n" in text:
                newline = "\n"
            else:
                newline = ""
            if newline:
                added = ("," + newline + "    ").join(
                    f'{_json_literal(name)}: {_json_literal(value)}'
                    for name, value in missing
                )
                insertion = newline + "    " + added + newline
            else:
                insertion = " " + ", ".join(
                    f'{_json_literal(name)}: {_json_literal(value)}'
                    for name, value in missing
                ) + " "
            operations.append((insertion_at, insertion_at, insertion))

    for start, end, replacement in sorted(operations, reverse=True):
        text = text[:start] + replacement + text[end:]
    result = bom + text.encode("utf-8")
    final_state, final_detail, _decoded = _config_analysis(result)
    if final_state != "patched":
        raise PatchError(
            f"embedded config postcondition failed: {final_detail or final_state}"
        )
    return result


def _data1_state(path: Path) -> tuple[str, str | None]:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = tuple(info.filename for info in archive.infolist())
            if len(names) != len(set(names)):
                return "unsupported", "assets/data1 has duplicate entries"
            if CONFIG_ENTRY not in names:
                return "unsupported", f"assets/data1 is missing {CONFIG_ENTRY}"
            config = archive.read(CONFIG_ENTRY)
            state, detail, _decoded = _config_analysis(config)
            return state, detail
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as exc:
        return "unsupported", f"invalid assets/data1: {exc}"


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    missing = [entry for entry in (DATA1_ENTRY,) if entry not in extracted]
    if missing:
        return {"state": "unsupported", "targets": [], "detail": f"missing {missing}"}
    data_state, detail = _data1_state(extracted[DATA1_ENTRY])
    return {
        "state": data_state,
        "detail": detail,
        "targets": [
            {"name": "Aurora viewport fit", "state": data_state},
            {"name": "GameCube menu scaling", "state": data_state},
            {"name": "cutscene pillarboxing", "state": data_state},
        ],
    }


def _clone_info(info: zipfile.ZipInfo, name: str, size: int) -> zipfile.ZipInfo:
    cloned = copy.copy(info)
    cloned.filename = name
    cloned.orig_filename = name
    cloned.file_size = size
    cloned.CRC = 0
    cloned.compress_size = 0
    return cloned


def _build_data1(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    previous_limit = zipfile.ZIP64_LIMIT
    try:
        zipfile.ZIP64_LIMIT = 0xFFFFFFFE
        with zipfile.ZipFile(source, "r") as original, zipfile.ZipFile(
            destination, "w", allowZip64=False
        ) as output:
            output.comment = original.comment
            names = {info.filename for info in original.infolist()}
            source_config = original.read(CONFIG_ENTRY)
            _state, _detail, decoded = _config_analysis(source_config)
            clean_iso = (
                SOURCE_ISO_ENTRY in names
                and PATCHED_ISO_ENTRY not in names
                and decoded.get("backend.isoPath") == SOURCE_CONFIG["backend.isoPath"]
            )
            config = _patch_config(source_config, clean_iso_path=clean_iso)
            for info in original.infolist():
                if clean_iso and info.filename == SOURCE_ISO_ENTRY:
                    name, size, payload = PATCHED_ISO_ENTRY, info.file_size, None
                elif info.filename == CONFIG_ENTRY:
                    name, size, payload = info.filename, len(config), config
                else:
                    name, size, payload = info.filename, info.file_size, None
                cloned = _clone_info(info, name, size)
                with output.open(cloned, "w", force_zip64=False) as target:
                    if payload is not None:
                        target.write(payload)
                    else:
                        with original.open(info, "r") as input_stream:
                            shutil.copyfileobj(input_stream, target, length=8 * 1024 * 1024)
    finally:
        zipfile.ZIP64_LIMIT = previous_limit
    state, detail = _data1_state(destination)
    if state != "patched":
        raise PatchError(f"rebuilt assets/data1 verification failed: {detail or state}")


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    state = probe(extracted)["state"]
    if state == "patched":
        return {}
    if state != "original":
        raise PatchError(f"Dusklight targets are {state}")
    replacement = output_dir / DATA1_ENTRY
    _build_data1(extracted[DATA1_ENTRY], replacement)
    return {DATA1_ENTRY: replacement}
