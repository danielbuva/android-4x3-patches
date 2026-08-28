"""Exact native 4:3 and narrowly scoped cleanup for Death Road to Canada."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import math
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ARM64_ENTRY = "lib/arm64-v8a/libmain.so"
ARMV7_ENTRY = "lib/armeabi-v7a/libmain.so"
DEX_ENTRY = "classes.dex"
SPLASH_ENTRY = "res/drawable-xxhdpi-v4/splash.png"
REQUIRED_ENTRIES = (DEX_ENTRY, SPLASH_ENTRY)


class PatchError(RuntimeError):
    """The supplied build does not contain the audited targets uniquely."""


@dataclass(frozen=True)
class NativeEdit:
    name: str
    offset: int
    virtual_address: int
    original: bytes
    patched: bytes


@dataclass(frozen=True)
class NativeSpec:
    abi: str
    entry: str
    elf_class: int
    machine: int
    size: int
    original_sha256: str
    patched_sha256: str
    edits: tuple[NativeEdit, ...]


_NATIVE_SPECS = (
    NativeSpec(
        "arm64-v8a",
        ARM64_ENTRY,
        2,
        183,  # EM_AARCH64
        7_460_800,
        "8301745f314041208aecd87f43a15f205689699756ddff3ae0030362b03c4a9b",
        "b543ea48115f995199948dce3e7a4010012406d8b69e6444a60326db05da5866",
        (
            NativeEdit(
                "SDL_main logical height 320 -> 360",
                0xF13B0,
                0xF13B0,
                bytes.fromhex("01 28 80 52"),  # mov w1, #320
                bytes.fromhex("01 2d 80 52"),  # mov w1, #360
            ),
        ),
    ),
    NativeSpec(
        "armeabi-v7a",
        ARMV7_ENTRY,
        1,
        40,  # EM_ARM
        6_554_816,
        "3e8ac21422ddd5f4f5515bd7b0cb83f83acf15da33f167d0da0cd797fee46747",
        "239ffd4456b15ab6d68846f42fc396f8864f111ceed05547d13c810e074fd88b",
        (
            NativeEdit(
                "SDL_main logical height 320 -> 360",
                0x8F1F8,
                0x8F1F8,
                bytes.fromhex("4f f4 a0 71"),  # mov.w r1, #320
                bytes.fromhex("4f f4 b4 71"),  # mov.w r1, #360
            ),
        ),
    ),
)


@dataclass(frozen=True)
class DexEdit:
    class_descriptor: str
    method_name: str
    descriptor: str
    original_prefix: bytes
    patched_prefix: bytes
    detail: str

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.class_descriptor, self.method_name, self.descriptor


_VOID = bytes.fromhex("0e 00 00 00")  # return-void; nop (one complete old 2-unit instruction)
_DEX_EDITS = (
    DexEdit(
        "Lcom/noodlecake/NoodleX/NoodleXFlurry;",
        "init",
        "()V",
        bytes.fromhex("63 00 9f 78"),
        _VOID,
        "disable NoodleX Flurry initialization",
    ),
    DexEdit(
        "Lcom/noodlecake/NoodleX/NoodleXFlurry;",
        "logEvent",
        "(Ljava/lang/String;Ljava/util/Map;)V",
        bytes.fromhex("63 00 9f 78"),
        _VOID,
        "disable the central NoodleX Flurry event sink",
    ),
    DexEdit(
        "Lcom/noodlecake/NoodleX/NoodleXFlurry;",
        "onStart",
        "()V",
        bytes.fromhex("63 00 9f 78"),
        _VOID,
        "disable Flurry activity-start tracking",
    ),
    DexEdit(
        "Lcom/noodlecake/NoodleX/NoodleXFlurry;",
        "onStop",
        "()V",
        bytes.fromhex("63 00 9f 78"),
        _VOID,
        "disable Flurry activity-stop tracking",
    ),
    DexEdit(
        "Lcom/noodlecake/NoodleX/NoodleXFlurry;",
        "setUserId",
        "(Ljava/lang/String;)V",
        bytes.fromhex("63 00 9f 78"),
        _VOID,
        "disable Flurry user-id assignment",
    ),
    DexEdit(
        "Lcom/flurry/android/agent/FlurryContentProvider;",
        "onCreate",
        "()Z",
        bytes.fromhex("6e 10 26 65 08 00"),
        bytes.fromhex("12 10 0f 00 00 00"),  # const/4 v0,1; return v0; nop
        "return success without starting Flurry from its manifest provider",
    ),
    DexEdit(
        "Lcom/noodlecake/NoodleX/NoodleXBridge;",
        "showMoreGames",
        "()V",
        bytes.fromhex("1a 00 83 95"),
        _VOID,
        "disable the More Games website cross-promotion",
    ),
)


@dataclass(frozen=True)
class PngSpec:
    entry: str
    original_size: tuple[int, int]
    patched_size: tuple[int, int]
    original_sha256: str
    patched_sha256: str


_SPLASH = PngSpec(
    SPLASH_ENTRY,
    (2560, 1600),
    (1920, 1440),
    "5b2abc500309db6ce69f2a67769c6773dc0ebf2230734647b763e7c653c44ba8",
    "a594c5abcbdc5bcb37c0008ad060e4bdc35a20554615e8ec49797510969c7746",
)


def _sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest()


def _overall(states: list[str]) -> str:
    if "ambiguous" in states:
        return "ambiguous"
    if "unsupported" in states:
        return "unsupported"
    return "patched" if states and set(states) == {"patched"} else "original"


def _normal_entries(extracted: dict[str, Path]) -> dict[str, tuple[str, Path]]:
    return {
        name.replace("\\", "/").lower(): (name.replace("\\", "/"), Path(path))
        for name, path in extracted.items()
    }


def _entry(extracted: dict[str, Path], wanted: str) -> tuple[str, Path] | None:
    return _normal_entries(extracted).get(wanted.lower())


def _destination(output_dir: Path, entry: str) -> Path:
    result = Path(output_dir).joinpath(*entry.split("/"))
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


def _elf_error(data: bytes | bytearray, spec: NativeSpec) -> str | None:
    if len(data) < 52 or bytes(data[:4]) != b"\x7fELF" or data[4] != spec.elf_class or data[5] != 1:
        return f"not the expected little-endian ELF class for {spec.abi}"
    if spec.elf_class == 2:
        values = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
        e_type, machine = values[0], values[1]
        phoff, phentsize, phnum = values[4], values[8], values[9]
        fmt, minimum = "<IIQQQQQQ", 56
    else:
        values = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
        e_type, machine = values[0], values[1]
        phoff, phentsize, phnum = values[4], values[8], values[9]
        fmt, minimum = "<IIIIIIII", 32
    if e_type != 3 or machine != spec.machine:
        return f"ELF type or machine does not match {spec.abi}"
    if phentsize < minimum or not phnum or phoff + phentsize * phnum > len(data):
        return "ELF program-header table is invalid"
    loads: list[tuple[int, int, int, int]] = []
    for index in range(phnum):
        fields = struct.unpack_from(fmt, data, phoff + index * phentsize)
        if spec.elf_class == 2:
            p_type, flags, file_offset, vaddr, _paddr, filesz, _memsz, _align = fields
        else:
            p_type, file_offset, vaddr, _paddr, filesz, _memsz, flags, _align = fields
        if p_type == 1:
            loads.append((file_offset, vaddr, filesz, flags))
    for edit in spec.edits:
        size = len(edit.original)
        matches = [
            load
            for load in loads
            if load[3] & 1 and load[1] <= edit.virtual_address <= load[1] + load[2] - size
        ]
        if len(matches) != 1:
            return f"{edit.name}: target is not in one executable PT_LOAD segment"
        file_offset, vaddr, _filesz, _flags = matches[0]
        if file_offset + edit.virtual_address - vaddr != edit.offset:
            return f"{edit.name}: ELF virtual-address mapping changed"
    return None


def _native_probe_data(data: bytes | bytearray, spec: NativeSpec) -> dict[str, Any]:
    result: dict[str, Any] = {"name": spec.entry, "entry": spec.entry, "abi": spec.abi}
    if len(data) != spec.size:
        result.update(state="unsupported", reason=f"library size is {len(data)}, expected {spec.size}")
        return result
    error = _elf_error(data, spec)
    if error:
        result.update(state="unsupported", reason=error)
        return result
    canonical = bytearray(data)
    targets: list[dict[str, Any]] = []
    states: list[str] = []
    for edit in spec.edits:
        actual = bytes(data[edit.offset : edit.offset + len(edit.original)])
        if actual == edit.original:
            state = "original"
        elif actual == edit.patched:
            state = "patched"
            canonical[edit.offset : edit.offset + len(edit.original)] = edit.original
        else:
            state = "unsupported"
        states.append(state)
        targets.append(
            {
                "name": edit.name,
                "state": state,
                "offset": edit.offset,
                "virtual_address": edit.virtual_address,
            }
        )
    result["targets"] = targets
    if "unsupported" in states:
        result.update(state="unsupported", reason="guarded native instruction changed")
        return result
    if _sha256(canonical) != spec.original_sha256:
        result.update(state="unsupported", reason="canonical native SHA-256 does not match the tested build")
        return result
    state = "patched" if set(states) == {"patched"} else "original"
    if state == "patched" and _sha256(data) != spec.patched_sha256:
        result.update(state="unsupported", reason="patched native SHA-256 postcondition disagrees")
        return result
    result["state"] = state
    return result


def _patch_native_data(data: bytes, spec: NativeSpec) -> bytes:
    before = _native_probe_data(data, spec)
    if before["state"] not in ("original", "patched"):
        raise PatchError(f"{spec.entry}: native target is {before['state']}")
    mutable = bytearray(data)
    for edit in spec.edits:
        actual = bytes(mutable[edit.offset : edit.offset + len(edit.original)])
        if actual == edit.original:
            mutable[edit.offset : edit.offset + len(edit.original)] = edit.patched
        elif actual != edit.patched:
            raise PatchError(f"{spec.entry}: target changed after probing")
    after = _native_probe_data(mutable, spec)
    if after["state"] != "patched":
        raise PatchError(f"{spec.entry}: native postcondition failed ({after['state']})")
    return bytes(mutable)


_DEX_IMAGE: Any | None = None


def _dex_image_type():
    global _DEX_IMAGE
    if _DEX_IMAGE is not None:
        return _DEX_IMAGE
    helper = Path(__file__).resolve().parents[2] / "tools" / "apkvision_neutralize.py"
    name = "android4x3_death_road_dex_helper"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, helper)
        if spec is None or spec.loader is None:
            raise PatchError("DEX helper is unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    _DEX_IMAGE = module.DexImage
    return _DEX_IMAGE


def _dex_probe_data(data: bytes, edits: tuple[DexEdit, ...] = _DEX_EDITS) -> tuple[dict[str, Any], dict[tuple[str, str, str], int]]:
    try:
        dex = _dex_image_type()(data)
        methods = list(dex.methods())
    except Exception as exc:
        return {"name": "Flurry and More Games cleanup", "state": "unsupported", "reason": str(exc)}, {}
    targets: list[dict[str, Any]] = []
    states: list[str] = []
    locations: dict[tuple[str, str, str], int] = {}
    for edit in edits:
        matches = [
            method
            for method in methods
            if (method.class_descriptor, method.name, method.descriptor) == edit.identity
        ]
        if len(matches) != 1:
            state = "ambiguous" if len(matches) > 1 else "unsupported"
            targets.append({"name": edit.detail, "state": state, "matches": len(matches)})
            states.append(state)
            continue
        method = matches[0]
        if not method.code_offset or method.code_offset + 16 > len(data):
            targets.append({"name": edit.detail, "state": "unsupported", "reason": "method has no valid code item"})
            states.append("unsupported")
            continue
        units = struct.unpack_from("<I", data, method.code_offset + 12)[0]
        offset = method.code_offset + 16
        if units * 2 < len(edit.original_prefix):
            state = "unsupported"
        else:
            actual = data[offset : offset + len(edit.original_prefix)]
            if actual == edit.original_prefix:
                state = "original"
            elif actual == edit.patched_prefix:
                state = "patched"
            else:
                state = "unsupported"
        locations[edit.identity] = offset
        states.append(state)
        targets.append({"name": edit.detail, "state": state, "offset": offset})
    return {"name": "Flurry and More Games cleanup", "state": _overall(states), "targets": targets}, locations


def _patch_dex_data(data: bytes, edits: tuple[DexEdit, ...] = _DEX_EDITS) -> bytes:
    before, locations = _dex_probe_data(data, edits)
    if before["state"] not in ("original", "patched"):
        raise PatchError(f"DEX cleanup targets are {before['state']}")
    dex = _dex_image_type()(data)
    for edit in edits:
        offset = locations[edit.identity]
        actual = bytes(dex.data[offset : offset + len(edit.original_prefix)])
        if actual == edit.original_prefix:
            dex.data[offset : offset + len(edit.original_prefix)] = edit.patched_prefix
        elif actual != edit.patched_prefix:
            raise PatchError(f"{edit.detail}: state changed after probing")
    result = dex.finish()
    after, _locations = _dex_probe_data(result, edits)
    if after["state"] != "patched":
        raise PatchError(f"DEX postcondition failed: {after['state']}")
    return result


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            image.load()
            return image.size
    except Exception:
        return None


def _png_probe_data(data: bytes, spec: PngSpec = _SPLASH) -> dict[str, Any]:
    digest = _sha256(data)
    dimensions = _png_dimensions(data)
    if digest == spec.original_sha256 and dimensions == spec.original_size:
        state = "original"
    elif digest == spec.patched_sha256 and dimensions == spec.patched_size:
        state = "patched"
    else:
        state = "unsupported"
    return {
        "name": "4:3 Android splash (uniform cover crop)",
        "state": state,
        "dimensions": list(dimensions) if dimensions else None,
        "sha256": digest,
    }


def _cover_crop_png(data: bytes, target_size: tuple[int, int]) -> bytes:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as source:
        source.load()
        image = source.convert("RGBA")
    target_width, target_height = target_size
    scale = max(target_width / image.width, target_height / image.height)
    scaled_size = (math.ceil(image.width * scale), math.ceil(image.height * scale))
    image = image.resize(scaled_size, Image.Resampling.LANCZOS)
    left = (image.width - target_width) // 2
    top = (image.height - target_height) // 2
    image = image.crop((left, top, left + target_width, top + target_height))
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _patch_png_data(data: bytes, spec: PngSpec = _SPLASH) -> bytes:
    before = _png_probe_data(data, spec)
    if before["state"] == "patched":
        return data
    if before["state"] != "original":
        raise PatchError("splash image is not the audited source")
    result = _cover_crop_png(data, spec.patched_size)
    after = _png_probe_data(result, spec)
    if after["state"] != "patched":
        raise PatchError("splash image postcondition failed")
    return result


def _analyse(extracted: dict[str, Path]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    states: list[str] = []
    details: dict[str, Any] = {"native": {}}
    normal = _normal_entries(extracted)
    supported = {spec.entry.lower(): spec for spec in _NATIVE_SPECS}
    native_entries = {
        key: value for key, value in normal.items()
        if key.startswith("lib/") and key.endswith("/libmain.so")
    }
    for key, found in native_entries.items():
        spec = supported.get(key)
        if spec is None:
            result = {
                "name": found[0],
                "entry": found[0],
                "state": "unsupported",
                "reason": "present libmain.so ABI/path is not audited",
            }
        else:
            result = _native_probe_data(found[1].read_bytes(), spec)
        rows.append(result)
        states.append(result["state"])
        if spec is not None:
            details["native"][spec.entry] = result
    if not details["native"]:
        result = {
            "name": "lib/*/libmain.so",
            "state": "unsupported",
            "reason": "no audited native ABI is present",
        }
        rows.append(result)
        states.append(result["state"])

    dex_entry = _entry(extracted, DEX_ENTRY)
    if dex_entry is None:
        dex, locations = {"name": DEX_ENTRY, "state": "unsupported", "reason": "required entry missing"}, {}
    else:
        dex, locations = _dex_probe_data(dex_entry[1].read_bytes())
    rows.append(dex)
    states.append(dex["state"])
    details["dex"] = (dex, locations)

    splash_entry = _entry(extracted, SPLASH_ENTRY)
    splash = (
        {"name": SPLASH_ENTRY, "state": "unsupported", "reason": "required entry missing"}
        if splash_entry is None
        else _png_probe_data(splash_entry[1].read_bytes())
    )
    rows.append(splash)
    states.append(splash["state"])
    details["splash"] = splash
    return {"state": _overall(states), "targets": rows}, details


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Classify all present audited ABIs, cleanup targets, and the splash."""

    report, _details = _analyse(extracted)
    return report


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Emit exact replacement entries and verify their combined state."""

    report, details = _analyse(extracted)
    if report["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"Death Road to Canada targets are {report['state']}")
    if report["state"] == "patched":
        return {}
    replacements: dict[str, Path] = {}
    try:
        for spec in _NATIVE_SPECS:
            native_result = details["native"].get(spec.entry)
            if native_result is None or native_result["state"] != "original":
                continue
            source_entry = _entry(extracted, spec.entry)
            assert source_entry is not None
            output = _destination(output_dir, source_entry[0])
            output.write_bytes(_patch_native_data(source_entry[1].read_bytes(), spec))
            replacements[source_entry[0]] = output

        dex_entry = _entry(extracted, DEX_ENTRY)
        if details["dex"][0]["state"] == "original" and dex_entry is not None:
            output = _destination(output_dir, dex_entry[0])
            output.write_bytes(_patch_dex_data(dex_entry[1].read_bytes()))
            replacements[dex_entry[0]] = output

        splash_entry = _entry(extracted, SPLASH_ENTRY)
        if details["splash"]["state"] == "original" and splash_entry is not None:
            output = _destination(output_dir, splash_entry[0])
            output.write_bytes(_patch_png_data(splash_entry[1].read_bytes()))
            replacements[splash_entry[0]] = output

        combined = dict(extracted)
        combined.update(replacements)
        after = probe(combined)
        if after["state"] != "patched":
            raise PatchError(f"combined postcondition failed: {after['state']}")
        return replacements
    except Exception:
        for path in replacements.values():
            path.unlink(missing_ok=True)
        raise
