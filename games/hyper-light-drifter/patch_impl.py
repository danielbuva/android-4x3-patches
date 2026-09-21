"""Exact-build ARM64 camera, menu layout, and startup timer transformations."""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from android4x3.errors import PatchError

DIRECTORY = Path(__file__).resolve().parent
FINGERPRINTS = json.loads((DIRECTORY / "fingerprints.json").read_text())
LIBRARY = "lib/arm64-v8a/libyoyo.so"
GAME = "assets/assets/game.droid"
REQUIRED_ENTRIES = (LIBRARY, GAME)
PAYLOAD_ADDRESS = 0x1E10000
HOOKS = json.loads((DIRECTORY / "native/hooks.json").read_text())


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def state(data: bytes, prefix: str) -> str:
    checksum = digest(data)
    for variant in ("original", "original_aspect", "4x3"):
        if checksum == FINGERPRINTS.get(f"{prefix}_{variant}"):
            return variant
    raise PatchError(f"Hyper Light Drifter: unsupported {prefix} revision; use the documented source APK")


def word(data: bytearray, offset: int, expected: int, replacement: int) -> None:
    if struct.unpack_from("<I", data, offset)[0] != expected:
        raise PatchError(f"Hyper Light Drifter: instruction mismatch at {offset:#x}")
    struct.pack_into("<I", data, offset, replacement)


def branch(data: bytearray, offset: int, expected: int, target: int, *, link: bool = True) -> None:
    delta = target - offset
    if delta % 4 or not -(1 << 27) <= delta < (1 << 27):
        raise PatchError("Hyper Light Drifter: branch target out of range")
    word(data, offset, expected, (0x94000000 if link else 0x14000000) | ((delta // 4) & 0x3FFFFFF))


def append_payload(data: bytearray) -> None:
    payload = bytes.fromhex((DIRECTORY / "native/payload.hex").read_text())
    if digest(payload) != FINGERPRINTS["payload_sha256"]:
        raise PatchError("Hyper Light Drifter: damaged patch payload")
    if data[:7] != b"\x7fELF\x02\x01\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise PatchError("Hyper Light Drifter: expected AArch64 ELF")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    entry_size, count = struct.unpack_from("<HH", data, 54)
    if entry_size != 56 or phoff + entry_size * count > len(data):
        raise PatchError("Hyper Light Drifter: invalid program headers")
    notes = []
    for i in range(count):
        offset = phoff + i * entry_size
        header = struct.unpack_from("<IIQQQQQQ", data, offset)
        if header[0] == 4:
            notes.append(offset)
        if header[0] == 1 and header[3] + header[6] > PAYLOAD_ADDRESS:
            raise PatchError("Hyper Light Drifter: payload overlaps a load segment")
    if len(notes) != 1:
        raise PatchError("Hyper Light Drifter: expected one replaceable note header")
    offset = (len(data) + 65535) & ~65535
    # Keep every original LOAD segment. Reuse the optional NOTE header for new RX code.
    struct.pack_into("<IIQQQQQQ", data, notes[0], 1, 5, offset, PAYLOAD_ADDRESS,
                     PAYLOAD_ADDRESS, len(payload), len(payload), 65536)
    data.extend(bytes(offset - len(data)))
    data.extend(payload)


def patch_native(data: bytes, *, original_aspect: bool = False) -> bytes:
    initial = state(data, "native")
    target = "original_aspect" if original_aspect else "4x3"
    if initial == target:
        return data
    if initial == "4x3":
        raise PatchError("Original-aspect output requires an original or original-aspect input")
    result = bytearray(data)
    if initial == "original":
        append_payload(result)
        branch(result, 0x147B368, 0x9414ECAA, HOOKS["startup"])
        branch(result, 0xD9F7E4, 0xD63F0100, HOOKS["aim_movement"])
        branch(result, 0xDA1B44, 0xD63F0100, HOOKS["aim_animation"])
        for offset, expected, target_address, _name in HOOKS["entries"]:
            branch(result, offset, expected, target_address, link=False)
    if not original_aspect:
        branch(result, 0x1347298, 0x9419BAEE, PAYLOAD_ADDRESS)
        branch(result, 0x14465B8, 0x9415CA26, HOOKS["background"])
        if struct.unpack_from("<d", result, 0x1B6AA30)[0] != 80.0:
            raise PatchError("Hyper Light Drifter: dialog band mismatch")
        struct.pack_into("<d", result, 0x1B6AA30, 144.0)
        for offset in (0x14499E8, 0x1465FF0, 0x14669AC):
            word(result, offset, 0xD2D00008, 0xD2C80008)
            word(result, offset + 12, 0xF2E80AC8, 0xF2E80C68)
        for offset in (0x141AF94, 0x141B178):
            word(result, offset, 0xD2DC0008, 0xD2D00008)
            word(result, offset + 8, 0xF2E80C08, 0xF2E80CC8)
        for offset in (0x1445D08, 0x1445E28):
            word(result, offset, 0x52A870E9, 0x52A87689)
        for offset, old in ((0x1B6A970, 206.0), (0x1B6A990, 205.0)):
            if struct.unpack_from("<d", result, offset)[0] != old:
                raise PatchError("Hyper Light Drifter: title prompt position mismatch")
            struct.pack_into("<d", result, offset, old + 45)
    if digest(result) != FINGERPRINTS[f"native_{target}"]:
        raise PatchError("Hyper Light Drifter: native output checksum mismatch")
    return bytes(result)


def patch_game(data: bytes) -> bytes:
    if state(data, "game") == "4x3":
        return data
    result = bytearray(data)
    # Fixed startup rooms use the same proportional projection as the title.
    # Their overlays already position themselves from the shared canvas height.
    for offset in (0x217FC8, 0x2183A4, 0x218780, 0x218B00):
        word(result, offset + 8, 480, 480)
        word(result, offset + 12, 270, 360)
    for offset, sprite in ((0x2182F0, 3528), (0x2186CC, 3528),
                           (0x218A4C, 3534), (0x218E3C, 3530)):
        word(result, offset + 56, sprite, sprite)
        word(result, offset + 20, 0, struct.unpack("<I", struct.pack("<f", 45.0))[0])
        word(result, offset + 64, 1, 0)
    if digest(result) != FINGERPRINTS["game_4x3"]:
        raise PatchError("Hyper Light Drifter: game data output checksum mismatch")
    return bytes(result)


def probe(extracted: dict[str, Path]) -> dict:
    try:
        native = state(extracted[LIBRARY].read_bytes(), "native")
        game = state(extracted[GAME].read_bytes(), "game")
        if (native == "4x3") != (game == "4x3"):
            raise PatchError("Hyper Light Drifter: mixed patch revisions; start from the source APK")
        return {"state": "patched" if native == "4x3" else "original", "targets": [
            {"name": "ARM64 camera, menu layout and startup timers", "state": native},
            {"name": "Proportionate title room", "state": game}]}
    except (PatchError, KeyError, OSError, ValueError, struct.error) as exc:
        return {"state": "unsupported", "detail": str(exc), "targets": []}


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    initial = probe(extracted)
    if initial["state"] == "unsupported":
        raise PatchError(initial["detail"])
    replacements = {}
    for entry, transform in ((LIBRARY, patch_native), (GAME, patch_game)):
        before = extracted[entry].read_bytes()
        after = transform(before)
        if after != before:
            path = output_dir.joinpath(*entry.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(after)
            replacements[entry] = path
    if probe({**extracted, **replacements})["state"] != "patched":
        raise PatchError("Hyper Light Drifter: combined postcondition failed")
    return replacements
