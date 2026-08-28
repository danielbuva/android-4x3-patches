"""Target-verified 4:3 and cleanup patch for Children of Morta 1.1.4.

The module never contains game assets.  It discovers Unity ``CanvasScaler``
objects by their serialized script identity and structure, rewrites only their
reference resolutions, applies four exact AArch64 edits, and creates a 4:3
Android splash with a uniform cover/crop transform. FirebaseApp initialization
and its manifest provider are deliberately preserved for Remote Config and
other game services.
"""

from __future__ import annotations

import gc
import hashlib
import io
import math
import struct
import warnings
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IL2CPP_ENTRY = "lib/arm64-v8a/libil2cpp.so"
SPLASH_ENTRY = "res/drawable/unity_static_splash.png"
CORE_ENTRY = "assets/AssetBundles/core"
HOME_ENTRY = "assets/AssetBundles/home"
RUN_SHARED_ENTRY = "assets/AssetBundles/run_shared_base"
DATAPACK_ENTRY = "assets/bin/Data/datapack.unity3d"

REQUIRED_ENTRIES = (
    IL2CPP_ENTRY,
    SPLASH_ENTRY,
    CORE_ENTRY,
    HOME_ENTRY,
    RUN_SHARED_ENTRY,
    DATAPACK_ENTRY,
)

_FALLBACK_UNITY_VERSION = "2022.3.62f2"
_CANVAS_RAW_SIZE = 76
_CANVAS_REFERENCE_OFFSET = 44
_EXTERNAL_CANVAS_SCRIPT = (0, -8797238614672040712)
_DATAPACK_CANVAS_SCRIPT = (1, 277)


class PatchError(RuntimeError):
    """The supplied build does not contain the audited targets uniquely."""


@dataclass(frozen=True)
class NativeEdit:
    name: str
    offset: int
    virtual_address: int
    original: bytes
    patched: bytes
    executable: bool = True


@dataclass(frozen=True)
class NativeSpec:
    entry: str
    machine: int
    size: int
    original_sha256: str
    patched_sha256: str
    edits: tuple[NativeEdit, ...]


_NATIVE = NativeSpec(
    entry=IL2CPP_ENTRY,
    machine=183,  # EM_AARCH64
    size=61_356_112,
    original_sha256="aeef1114ceffdbc161587ca07f0c8276b4f12716ad7d4c749e705ba0ac548008",
    patched_sha256="81bbc212912e75ba87cf271c6e368e1122084787e62c4547a9c18755f5388640",
    edits=(
        NativeEdit(
            "force CameraHandle.GetAspectRatio through the constant-aspect path",
            0x1E3864C,
            0x1E3C64C,
            bytes.fromhex("29 01 00 34"),  # cbz w9, physical-ratio path
            bytes.fromhex("0b 00 00 14"),  # b constant-ratio load
        ),
        NativeEdit(
            "change the cinematic aspect constant from 2.35 to 4:3",
            0x8BBD64,
            0x8BBD64,
            struct.pack("<f", 2.35),
            struct.pack("<f", 4.0 / 3.0),
            executable=False,
        ),
        NativeEdit(
            "force TitleScreenMoreGamesManager.Show to hide cross-promotion",
            0x1AD3428,
            0x1AD7428,
            bytes.fromhex("f4 03 01 2a"),  # mov w20, w1
            bytes.fromhex("f4 03 1f 2a"),  # mov w20, wzr
        ),
        NativeEdit(
            "return immediately from FirebaseAnalytics.LogEvent(string)",
            0x2123270,
            0x2127270,
            bytes.fromhex("fe 57 be a9"),
            bytes.fromhex("c0 03 5f d6"),  # ret
        ),
    ),
)


@dataclass(frozen=True)
class CanvasMapping:
    original: tuple[float, float]
    patched: tuple[float, float]
    count: int


@dataclass(frozen=True)
class CanvasRule:
    entry: str
    script_pointer: tuple[int, int]
    mappings: tuple[CanvasMapping, ...]
    neutral: tuple[tuple[tuple[float, float], int], ...] = ()
    names: tuple[tuple[str, int], ...] = ()


_CANVAS_RULES = (
    CanvasRule(
        CORE_ENTRY,
        _EXTERNAL_CANVAS_SCRIPT,
        (
            CanvasMapping((1280.0, 720.0), (1280.0, 960.0), 164),
            CanvasMapping((1920.0, 1080.0), (1920.0, 1440.0), 6),
            CanvasMapping((1200.0, 720.0), (1200.0, 900.0), 4),
        ),
        neutral=(((800.0, 600.0), 2),),
    ),
    CanvasRule(
        HOME_ENTRY,
        _EXTERNAL_CANVAS_SCRIPT,
        (CanvasMapping((1280.0, 720.0), (1280.0, 960.0), 1),),
        names=(("Text Canvas", 1),),
    ),
    CanvasRule(
        RUN_SHARED_ENTRY,
        _EXTERNAL_CANVAS_SCRIPT,
        (CanvasMapping((1280.0, 720.0), (1280.0, 960.0), 1),),
        names=(("DoubleBossHPBar", 1),),
    ),
    CanvasRule(
        DATAPACK_ENTRY,
        _DATAPACK_CANVAS_SCRIPT,
        (CanvasMapping((1280.0, 720.0), (1280.0, 960.0), 2),),
        names=(("Loading Indicator", 1), ("Splash screens menu", 1)),
    ),
)


@dataclass(frozen=True)
class CanvasTarget:
    serialized_file: str
    path_id: int
    name: str
    state: str
    value: tuple[float, float] | None
    original: tuple[float, float] | None
    patched: tuple[float, float] | None


@dataclass(frozen=True)
class PngSpec:
    entry: str
    original_size: tuple[int, int]
    patched_size: tuple[int, int]
    original_sha256: str
    patched_sha256: str


_SPLASH = PngSpec(
    SPLASH_ENTRY,
    (1920, 1079),
    (1440, 1080),
    "bef7c9750f5409bfc44f45c7e46ba025801ad35d9602feda1ced0e83a6dd68c6",
    "105cd37d7f7b4afd2a4e152b1e22ae1912e22f45f0ac9a75088daf699a83b29a",
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
    if len(data) < 64 or bytes(data[:6]) != b"\x7fELF\x02\x01":
        return "not a 64-bit little-endian ELF"
    values = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
    e_type, machine = values[0], values[1]
    phoff, phentsize, phnum = values[4], values[8], values[9]
    if e_type != 3 or machine != spec.machine:
        return "ELF type or machine does not match the audited arm64 library"
    if phentsize < 56 or not phnum or phoff + phentsize * phnum > len(data):
        return "ELF program-header table is invalid"
    loads: list[tuple[int, int, int, int]] = []
    for index in range(phnum):
        offset = phoff + index * phentsize
        p_type, flags, file_offset, vaddr, _paddr, filesz, _memsz, _align = struct.unpack_from(
            "<IIQQQQQQ", data, offset
        )
        if p_type == 1:
            loads.append((file_offset, vaddr, filesz, flags))
    for edit in spec.edits:
        size = len(edit.original)
        matches = [
            load
            for load in loads
            if load[1] <= edit.virtual_address <= load[1] + load[2] - size
            and (not edit.executable or load[3] & 1)
        ]
        if len(matches) != 1:
            return f"{edit.name}: target is not in one expected PT_LOAD segment"
        file_offset, vaddr, _filesz, _flags = matches[0]
        mapped = file_offset + edit.virtual_address - vaddr
        if mapped != edit.offset:
            return f"{edit.name}: ELF virtual-address mapping changed"
    return None


def _native_probe_data(data: bytes | bytearray, spec: NativeSpec = _NATIVE) -> dict[str, Any]:
    result: dict[str, Any] = {"name": "gameplay, analytics, and More Games native targets"}
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
        result.update(state="unsupported", reason="one or more guarded native instructions changed")
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


def _patch_native_data(data: bytes, spec: NativeSpec = _NATIVE) -> bytes:
    before = _native_probe_data(data, spec)
    if before["state"] not in ("original", "patched"):
        raise PatchError(f"native targets are {before['state']}")
    mutable = bytearray(data)
    for edit in spec.edits:
        current = bytes(mutable[edit.offset : edit.offset + len(edit.original)])
        if current == edit.original:
            mutable[edit.offset : edit.offset + len(edit.original)] = edit.patched
        elif current != edit.patched:
            raise PatchError(f"{edit.name}: state changed after probing")
    after = _native_probe_data(mutable, spec)
    if after["state"] != "patched":
        raise PatchError(f"native postcondition failed: {after['state']}")
    return bytes(mutable)


def _unity_module():
    try:
        import UnityPy
        from UnityPy import config
    except ImportError as exc:  # pragma: no cover - dependency preflight owns this
        raise PatchError("UnityPy is required for the Children of Morta patch") from exc
    config.FALLBACK_UNITY_VERSION = _FALLBACK_UNITY_VERSION
    return UnityPy


def _load_bundle(path: Path):
    UnityPy = _unity_module()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        environment = UnityPy.load(io.BytesIO(path.read_bytes()))
    top = list(environment.files.values())
    if len(top) != 1 or getattr(top[0], "signature", None) != "UnityFS":
        del environment
        gc.collect()
        raise PatchError(f"{path.name}: expected one UnityFS bundle")
    return environment, top[0]


def _pointer(raw: bytes, offset: int) -> tuple[int, int] | None:
    if len(raw) < offset + 12:
        return None
    return struct.unpack_from("<iq", raw, offset)


def _game_object_name(data: Any) -> str | None:
    try:
        pointer = data.m_GameObject
        return str(pointer.read().m_Name) if pointer.path_id else None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _pair(raw: bytes) -> tuple[float, float] | None:
    if len(raw) != _CANVAS_RAW_SIZE:
        return None
    return struct.unpack_from("<ff", raw, _CANVAS_REFERENCE_OFFSET)


def _near_pair(left: tuple[float, float] | None, right: tuple[float, float]) -> bool:
    return left is not None and all(math.isclose(a, b, rel_tol=0.0, abs_tol=0.0001) for a, b in zip(left, right))


def _inspect_bundle(rule: CanvasRule, path: Path) -> tuple[dict[str, Any], list[CanvasTarget]]:
    environment = bundle = None
    targets: list[CanvasTarget] = []
    try:
        environment, bundle = _load_bundle(path)
        for serialized_name, serialized in bundle.files.items():
            if not hasattr(serialized, "objects"):
                continue
            for path_id, obj in serialized.objects.items():
                if obj.type.name != "MonoBehaviour":
                    continue
                raw = bytes(obj.get_raw_data())
                if _pointer(raw, 16) != rule.script_pointer:
                    continue
                try:
                    data = obj.read(check_read=False)
                except Exception:
                    continue
                name = _game_object_name(data) or ""
                value = _pair(raw)
                state = "unsupported"
                old: tuple[float, float] | None = None
                new: tuple[float, float] | None = None
                for mapping in rule.mappings:
                    if _near_pair(value, mapping.original):
                        state, old, new = "original", mapping.original, mapping.patched
                        break
                    if _near_pair(value, mapping.patched):
                        state, old, new = "patched", mapping.original, mapping.patched
                        break
                if any(_near_pair(value, neutral) for neutral, _count in rule.neutral):
                    state = "neutral"
                targets.append(
                    CanvasTarget(serialized_name, int(path_id), name, state, value, old, new)
                )
    except Exception as exc:
        return {"name": rule.entry, "state": "unsupported", "reason": str(exc)}, []
    finally:
        del bundle
        del environment
        gc.collect()

    expected_total = sum(item.count for item in rule.mappings) + sum(count for _pair_value, count in rule.neutral)
    if len(targets) != expected_total:
        state = "ambiguous" if len(targets) > expected_total else "unsupported"
        return {
            "name": rule.entry,
            "state": state,
            "reason": f"found {len(targets)} CanvasScaler objects, expected {expected_total}",
        }, targets
    if rule.names and Counter(item.name for item in targets) != Counter(dict(rule.names)):
        return {"name": rule.entry, "state": "unsupported", "reason": "CanvasScaler object names changed"}, targets
    for mapping in rule.mappings:
        count = sum(
            1
            for item in targets
            if item.original == mapping.original and item.patched == mapping.patched
        )
        if count != mapping.count:
            return {
                "name": rule.entry,
                "state": "unsupported",
                "reason": f"resolution cohort {mapping.original} has {count} objects, expected {mapping.count}",
            }, targets
    for value, count in rule.neutral:
        actual = sum(
            1
            for item in targets
            if item.state == "neutral" and _near_pair(item.value, value)
        )
        if actual != count:
            return {"name": rule.entry, "state": "unsupported", "reason": "neutral 4:3 cohort changed"}, targets
    if any(item.state == "unsupported" for item in targets):
        return {"name": rule.entry, "state": "unsupported", "reason": "unrecognized CanvasScaler resolution"}, targets
    mapped = [item.state for item in targets if item.state != "neutral"]
    state = "patched" if mapped and set(mapped) == {"patched"} else "original"
    return {
        "name": rule.entry,
        "state": state,
        "matches": len(targets),
        "original_remaining": mapped.count("original"),
    }, targets
def _patch_bundle(rule: CanvasRule, source: Path, output: Path, targets: list[CanvasTarget]) -> None:
    environment = bundle = None
    try:
        environment, bundle = _load_bundle(source)
        for target in targets:
            if target.state != "original" or target.original is None or target.patched is None:
                continue
            obj = bundle.files[target.serialized_file].objects[target.path_id]
            raw = bytearray(obj.get_raw_data())
            actual = struct.unpack_from("<ff", raw, _CANVAS_REFERENCE_OFFSET)
            if not _near_pair(actual, target.original):
                raise PatchError(f"{rule.entry}: CanvasScaler changed after probing")
            struct.pack_into("<ff", raw, _CANVAS_REFERENCE_OFFSET, *target.patched)
            obj.set_raw_data(bytes(raw))
        output.write_bytes(bundle.save(packer="original"))
    finally:
        del bundle
        del environment
        gc.collect()
    verified, _verified_targets = _inspect_bundle(rule, output)
    if verified["state"] != "patched":
        output.unlink(missing_ok=True)
        raise PatchError(f"{rule.entry}: Unity bundle postcondition failed ({verified['state']})")


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
        "name": "4:3 Android static splash (uniform cover crop)",
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
    scaled = (math.ceil(image.width * scale), math.ceil(image.height * scale))
    image = image.resize(scaled, Image.Resampling.LANCZOS)
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
        raise PatchError("static splash is not the audited source image")
    result = _cover_crop_png(data, spec.patched_size)
    after = _png_probe_data(result, spec)
    if after["state"] != "patched":
        raise PatchError("static splash postcondition failed")
    return result


def _analyse(extracted: dict[str, Path]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    details: dict[str, Any] = {"bundles": {}}
    states: list[str] = []
    for rule in _CANVAS_RULES:
        found = _entry(extracted, rule.entry)
        if found is None:
            report, targets = {"name": rule.entry, "state": "unsupported", "reason": "required entry missing"}, []
        else:
            report, targets = _inspect_bundle(rule, found[1])
        rows.append(report)
        states.append(report["state"])
        details["bundles"][rule.entry] = (rule, targets)

    native_entry = _entry(extracted, IL2CPP_ENTRY)
    native = (
        {"name": IL2CPP_ENTRY, "state": "unsupported", "reason": "required entry missing"}
        if native_entry is None
        else _native_probe_data(native_entry[1].read_bytes())
    )
    rows.append(native)
    states.append(native["state"])
    details["native"] = native

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
    """Classify semantic Unity, exact native, cleanup, and splash targets."""

    report, _details = _analyse(extracted)
    return report


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Emit only changed APK entries and verify the combined patched state."""

    report, details = _analyse(extracted)
    if report["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"Children of Morta targets are {report['state']}")
    if report["state"] == "patched":
        return {}

    replacements: dict[str, Path] = {}
    try:
        for rule in _CANVAS_RULES:
            bundle_report = next(row for row in report["targets"] if row["name"] == rule.entry)
            if bundle_report["state"] != "original":
                continue
            source_entry = _entry(extracted, rule.entry)
            assert source_entry is not None
            output = _destination(output_dir, source_entry[0])
            _patch_bundle(rule, source_entry[1], output, details["bundles"][rule.entry][1])
            replacements[source_entry[0]] = output

        native_entry = _entry(extracted, IL2CPP_ENTRY)
        if details["native"]["state"] == "original" and native_entry is not None:
            output = _destination(output_dir, native_entry[0])
            output.write_bytes(_patch_native_data(native_entry[1].read_bytes()))
            replacements[native_entry[0]] = output

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
