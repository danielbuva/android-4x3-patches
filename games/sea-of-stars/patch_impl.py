"""Semantic Sea of Stars 4:3 patch.

Only target APK entries are emitted. The shared framework owns APK rebuilding,
optional branding cleanup, alignment, signing, and final verification.
"""

from __future__ import annotations

import gc
import io
import struct
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_ENTRIES = ("lib/arm64-v8a/libil2cpp.so",)

_IL2CPP_ENTRY = REQUIRED_ENTRIES[0]
_STUB_ENTRY = "lib/arm64-v8a/libstub.so"
_BUNDLE_PREFIX = "assets/aa/android/"
_FALLBACK_UNITY_VERSION = "2022.3.62f3"

PREFERRED_ENTRIES = (
    "assets/aa/Android/6d3223da354de646ab79d5660dcac9d2.bundle",
    "assets/aa/Android/ebe33395c1decf71e77c043c3949cd83.bundle",
    _STUB_ENTRY,
)
_PREFERRED_BUNDLES = tuple(
    entry for entry in PREFERRED_ENTRIES if entry.endswith(".bundle")
)

_OLD_ASPECT = struct.pack("<ff", 16.0, 9.0)
_NEW_ASPECT = struct.pack("<ff", 4.0, 3.0)
_MAX_ASPECT = (24.049999237060547, 9.0)

# The two instructions consume the packed int2 supplied to the shared
# GameResolutionController.SetResolution path. The instruction between them is
# deliberately left as context rather than copied into the replacement.
_NATIVE_OLD_A = bytes.fromhex("f3 03 01 aa")  # mov x19, x1
_NATIVE_OLD_B = bytes.fromhex("35 fc 60 d3")  # lsr x21, x1, #32
_NATIVE_NEW_A = bytes.fromhex("13 50 80 52")  # mov w19, #640
_NATIVE_NEW_B = bytes.fromhex("15 3c 80 52")  # mov w21, #480

_STUB_DESCRIPTOR = "(Landroid/content/Context;)Ljava/lang/String;"
_STUB_OLD_PREFIX = bytes.fromhex(
    "ff c3 02 d1 fd 7b 06 a9 f9 3b 00 f9 f8 5f 08 a9"
)
_STUB_NEW_PREFIX = bytes.fromhex("e0 03 1f aa c0 03 5f d6")


class PatchError(RuntimeError):
    """The input does not contain one safely identifiable patch target."""


@dataclass(frozen=True)
class _UnityTarget:
    entry: str
    serialized_file: str
    path_id: int
    role: str
    status: str
    byte_offset: int


def _normal_entries(extracted: dict[str, Path]) -> dict[str, tuple[str, Path]]:
    return {
        name.replace("\\", "/").lower(): (name.replace("\\", "/"), Path(path))
        for name, path in extracted.items()
    }


def _entry(extracted: dict[str, Path], wanted: str) -> tuple[str, Path] | None:
    return _normal_entries(extracted).get(wanted.lower())


def _bundle_entries(extracted: dict[str, Path]) -> list[tuple[str, Path]]:
    entries = [
        value
        for key, value in _normal_entries(extracted).items()
        if key.startswith(_BUNDLE_PREFIX) and key.endswith(".bundle")
    ]
    preferred = {name.lower(): index for index, name in enumerate(_PREFERRED_BUNDLES)}
    return sorted(entries, key=lambda item: (preferred.get(item[0].lower(), 999), item[0]))


def _pair(value: Any) -> tuple[float, float] | None:
    try:
        return (float(value.x), float(value.y))
    except (AttributeError, TypeError, ValueError):
        return None


def _same_pair(actual: tuple[float, float] | None, expected: tuple[float, float]) -> bool:
    return actual is not None and all(abs(a - b) < 0.0001 for a, b in zip(actual, expected))


def _unity_modules():
    try:
        import UnityPy
        from UnityPy import config
    except ImportError as exc:  # pragma: no cover - dependency preflight owns this
        raise PatchError("UnityPy is required for the Sea of Stars patch") from exc
    config.FALLBACK_UNITY_VERSION = _FALLBACK_UNITY_VERSION
    return UnityPy


def _load_bundle(path: Path):
    UnityPy = _unity_modules()
    # These bundles intentionally record Unity version 0.0.0 and rely on the
    # configured fallback. UnityPy's warning is expected and would otherwise
    # corrupt the CLI's machine-readable JSON output on stderr/stdout capture.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        environment = UnityPy.load(io.BytesIO(path.read_bytes()))
    top = list(environment.files.values())
    if len(top) != 1 or getattr(top[0], "signature", None) != "UnityFS":
        del environment
        gc.collect()
        raise PatchError(f"{path.name}: not a supported UnityFS bundle")
    return environment, top[0]


def _object_name(data: Any) -> str | None:
    try:
        pointer = data.m_GameObject
        if not pointer.path_id:
            return None
        return pointer.read().m_Name
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _aspect_status(data: Any, raw: bytes) -> tuple[str, int]:
    decoded = _pair(getattr(data, "minReferenceAspectRatio", None))
    if _same_pair(decoded, (16.0, 9.0)):
        needle, status = _OLD_ASPECT, "original"
    elif _same_pair(decoded, (4.0, 3.0)):
        needle, status = _NEW_ASPECT, "patched"
    else:
        return "unsupported", -1
    offsets: list[int] = []
    cursor = 0
    while True:
        cursor = raw.find(needle, cursor)
        if cursor < 0:
            break
        offsets.append(cursor)
        cursor += 1
    if len(offsets) != 1:
        return "ambiguous", -1
    return status, offsets[0]


def _inspect_bundle(entry: str, path: Path) -> list[_UnityTarget]:
    environment = bundle = None
    found: list[_UnityTarget] = []
    try:
        environment, bundle = _load_bundle(path)
        for serialized_name, serialized in bundle.files.items():
            if not hasattr(serialized, "objects"):
                continue
            for path_id, obj in serialized.objects.items():
                if obj.type.name != "MonoBehaviour":
                    continue
                raw = obj.get_raw_data()
                if len(raw) not in (52, 100, 164):
                    continue
                try:
                    data = obj.read(check_read=False)
                except (KeyError, TypeError, ValueError):
                    continue
                name = _object_name(data)
                role: str | None = None
                if name == "MobileResolutionManager":
                    if not _same_pair(_pair(getattr(data, "maxReferenceAspectRatio", None)), _MAX_ASPECT):
                        continue
                    role = "mobile-resolution-manager"
                elif name == "UICanvas":
                    if not (
                        _same_pair(_pair(getattr(data, "referenceResolution", None)), (640.0, 360.0))
                        and _same_pair(_pair(getattr(data, "outputResolution", None)), (640.0, 360.0))
                        and _same_pair(_pair(getattr(data, "maxReferenceAspectRatio", None)), _MAX_ASPECT)
                    ):
                        continue
                    role = "ui-resolution-controller"
                elif name == "RpgCamera":
                    if not (
                        _same_pair(_pair(getattr(data, "referenceResolution", None)), (640.0, 360.0))
                        and _same_pair(_pair(getattr(data, "outputResolution", None)), (0.0, 0.0))
                        and _same_pair(_pair(getattr(data, "maxReferenceAspectRatio", None)), _MAX_ASPECT)
                    ):
                        continue
                    role = "game-resolution-controller"
                if role is None or int(getattr(data, "m_Enabled", 0)) != 1:
                    continue
                status, offset = _aspect_status(data, raw)
                found.append(
                    _UnityTarget(entry, serialized_name, path_id, role, status, offset)
                )
    except Exception:
        # Addressables globs may include bundles with layouts UnityPy cannot
        # decode under this game's fallback version. They are not candidates.
        return []
    finally:
        del bundle
        del environment
        gc.collect()
    return found


def _discover_unity(extracted: dict[str, Path]) -> list[_UnityTarget]:
    found: list[_UnityTarget] = []
    for entry, path in _bundle_entries(extracted):
        # Inspect the complete candidate set. Stopping after the expected roles
        # are first found would allow a later duplicate to evade ambiguity
        # detection on a differently packed APK.
        candidates = _inspect_bundle(entry, path)
        found.extend(
            candidate
            for candidate in candidates
            if candidate.role != "game-resolution-controller"
        )
        gameplay = [
            candidate
            for candidate in candidates
            if candidate.role == "game-resolution-controller"
        ]
        # The live 4:3 target is one Addressables scene cohort: six distinct
        # serialized scenes, each with one RpgCamera controller. Other content
        # bundles contain individual 16:9 controller prefabs/scene fragments;
        # those are not loaded by this runtime path and were intentionally not
        # part of the verified patch. Retaining the cohort relationship avoids
        # treating every serialized controller in the game as the same target.
        if len(gameplay) >= 6 and len({item.serialized_file for item in gameplay}) >= 6:
            found.extend(gameplay)
    return found


def _is_aarch64_elf(data: bytes) -> bool:
    return len(data) >= 20 and data[:6] == b"\x7fELF\x02\x01" and struct.unpack_from("<H", data, 18)[0] == 183


def _instruction_hits(data: bytes, first: bytes, second: bytes) -> list[int]:
    hits: list[int] = []
    cursor = 0
    while True:
        cursor = data.find(first, cursor)
        if cursor < 0:
            return hits
        if cursor % 4 == 0 and data[cursor + 8 : cursor + 12] == second:
            hits.append(cursor)
        cursor += 1


def _native_state(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    if not _is_aarch64_elf(data):
        return "unsupported", -1
    original = _instruction_hits(data, _NATIVE_OLD_A, _NATIVE_OLD_B)
    patched = _instruction_hits(data, _NATIVE_NEW_A, _NATIVE_NEW_B)
    if len(original) + len(patched) > 1:
        return "ambiguous", -1
    if original:
        return "original", original[0]
    if patched:
        return "patched", patched[0]
    return "unsupported", -1


@dataclass(frozen=True)
class _LoadSegment:
    offset: int
    vaddr: int
    filesz: int
    executable: bool


class _Aarch64Elf:
    """Minimal ELF64 relocation reader for one JNINativeMethod target."""

    def __init__(self, data: bytes):
        if not _is_aarch64_elf(data):
            raise PatchError("not an AArch64 ELF image")
        self.data = data
        header = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
        self.phoff, self.shoff = header[4], header[5]
        self.phentsize, self.phnum = header[8], header[9]
        self.shentsize, self.shnum = header[10], header[11]
        self.loads = self._loads()
        self.sections = self._sections()

    def _loads(self) -> list[_LoadSegment]:
        result: list[_LoadSegment] = []
        for index in range(self.phnum):
            off = self.phoff + index * self.phentsize
            if off < 0 or off + 56 > len(self.data):
                raise PatchError("truncated ELF program header")
            p_type, flags, file_off, vaddr, _paddr, filesz, _memsz, _align = struct.unpack_from(
                "<IIQQQQQQ", self.data, off
            )
            if p_type == 1:
                result.append(_LoadSegment(file_off, vaddr, filesz, bool(flags & 1)))
        return result

    def _sections(self) -> list[tuple[int, int, int, int]]:
        result: list[tuple[int, int, int, int]] = []
        for index in range(self.shnum):
            off = self.shoff + index * self.shentsize
            if off < 0 or off + 64 > len(self.data):
                raise PatchError("truncated ELF section header")
            values = struct.unpack_from("<IIQQQQIIQQ", self.data, off)
            result.append((values[1], values[4], values[5], values[9]))
        return result

    def va_to_offset(self, vaddr: int, size: int = 1, executable: bool = False) -> int:
        for segment in self.loads:
            if executable and not segment.executable:
                continue
            if segment.vaddr <= vaddr and vaddr + size <= segment.vaddr + segment.filesz:
                offset = segment.offset + vaddr - segment.vaddr
                if offset + size <= len(self.data):
                    return offset
        raise PatchError("ELF address is not file-backed")

    def c_string(self, vaddr: int) -> str | None:
        try:
            offset = self.va_to_offset(vaddr)
        except PatchError:
            return None
        end = self.data.find(b"\0", offset, min(len(self.data), offset + 512))
        if end <= offset:
            return None
        try:
            return self.data[offset:end].decode("ascii")
        except UnicodeDecodeError:
            return None

    def relative_relocations(self) -> dict[int, int]:
        result: dict[int, int] = {}
        for section_type, offset, size, entry_size in self.sections:
            if section_type not in (4, 9):
                continue
            fmt = "<QQq" if section_type == 4 else "<QQ"
            minimum = struct.calcsize(fmt)
            stride = entry_size or minimum
            if stride < minimum:
                continue
            for cursor in range(offset, offset + size, stride):
                if cursor + minimum > len(self.data):
                    raise PatchError("truncated ELF relocation")
                values = struct.unpack_from(fmt, self.data, cursor)
                target, info = values[0], values[1]
                if info >> 32 or (info & 0xFFFFFFFF) != 1027:  # R_AARCH64_RELATIVE
                    continue
                if section_type == 4:
                    addend = values[2]
                else:
                    addend = struct.unpack_from("<Q", self.data, self.va_to_offset(target, 8))[0]
                if addend >= 0:
                    result[target] = addend
        return result

    def native_method(self, name: str, descriptor: str) -> list[int]:
        relocations = self.relative_relocations()
        matches: list[int] = []
        for table, name_va in relocations.items():
            descriptor_va = relocations.get(table + 8)
            function_va = relocations.get(table + 16)
            if descriptor_va is None or function_va is None:
                continue
            if self.c_string(name_va) != name or self.c_string(descriptor_va) != descriptor:
                continue
            try:
                matches.append(self.va_to_offset(function_va, 8, executable=True))
            except PatchError:
                continue
        return matches


def _stub_state(path: Path) -> tuple[str, int]:
    try:
        data = path.read_bytes()
        matches = _Aarch64Elf(data).native_method("a", _STUB_DESCRIPTOR)
    except (OSError, PatchError, struct.error):
        return "absent", -1
    if len(matches) != 1:
        return "absent", -1
    offset = matches[0]
    if data[offset : offset + len(_STUB_NEW_PREFIX)] == _STUB_NEW_PREFIX:
        return "patched", offset
    if data[offset : offset + len(_STUB_OLD_PREFIX)] == _STUB_OLD_PREFIX:
        return "original", offset
    # The helper is source-specific. An unrecognized implementation is ignored
    # rather than becoming a compatibility requirement for legitimate builds.
    return "absent", -1


def _analyse(extracted: dict[str, Path]) -> tuple[dict[str, Any], list[_UnityTarget], tuple[str, int], tuple[str, int]]:
    unity_targets = _discover_unity(extracted)
    by_role: dict[str, list[_UnityTarget]] = {}
    for target in unity_targets:
        by_role.setdefault(target.role, []).append(target)

    target_rows: list[dict[str, Any]] = []
    overall: list[str] = []
    for role in (
        "mobile-resolution-manager",
        "ui-resolution-controller",
        "game-resolution-controller",
    ):
        values = by_role.get(role, [])
        if not values:
            state = "unsupported"
        elif role == "game-resolution-controller" and (
            len(values) != 6 or len({value.entry for value in values}) != 1
        ):
            state = "ambiguous"
        elif role != "game-resolution-controller" and len(values) != 1:
            state = "ambiguous"
        elif any(value.status == "ambiguous" for value in values):
            state = "ambiguous"
        elif any(value.status == "unsupported" for value in values):
            state = "unsupported"
        elif all(value.status == "patched" for value in values):
            state = "patched"
        else:
            state = "original"
        target_rows.append({"name": role, "state": state, "matches": len(values)})
        overall.append(state)

    native_entry = _entry(extracted, _IL2CPP_ENTRY)
    native = ("unsupported", -1) if native_entry is None else _native_state(native_entry[1])
    target_rows.append({"name": "gameplay-640x480-native", "state": native[0], "matches": 1 if native[1] >= 0 else 0})
    overall.append(native[0])

    stub = ("absent", -1)
    stub_entry = _entry(extracted, _STUB_ENTRY)
    if stub_entry is not None:
        stub = _stub_state(stub_entry[1])
        if stub[0] in ("original", "patched"):
            target_rows.append({"name": "surfaceview-startup-helper", "state": stub[0], "matches": 1, "optional": True})

    if "ambiguous" in overall:
        state = "ambiguous"
    elif "unsupported" in overall:
        state = "unsupported"
    elif all(item == "patched" for item in overall):
        state = "patched"
    else:
        state = "original"
    return {"state": state, "targets": target_rows}, unity_targets, native, stub


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Return compatibility and original/already-patched target states."""

    report, _unity, _native, _stub = _analyse(extracted)
    return report


def _replacement_path(output_dir: Path, entry: str) -> Path:
    path = output_dir.joinpath(*entry.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _patch_unity_bundle(source: Path, targets: list[_UnityTarget], output: Path) -> None:
    environment = bundle = None
    try:
        environment, bundle = _load_bundle(source)
        for target in targets:
            if target.status != "original":
                continue
            serialized = bundle.files[target.serialized_file]
            obj = serialized.objects[target.path_id]
            raw = bytearray(obj.get_raw_data())
            if raw[target.byte_offset : target.byte_offset + 8] != _OLD_ASPECT:
                raise PatchError(f"{target.role}: source bytes changed after probing")
            raw[target.byte_offset : target.byte_offset + 8] = _NEW_ASPECT
            obj.set_raw_data(bytes(raw))
        result = bundle.save(packer="original")
        output.write_bytes(result)
    finally:
        del bundle
        del environment
        gc.collect()

    verified = {
        (item.serialized_file, item.path_id): item.status
        for item in _inspect_bundle(targets[0].entry, output)
    }
    for target in targets:
        if verified.get((target.serialized_file, target.path_id)) != "patched":
            raise PatchError(f"{target.role}: replacement bundle verification failed")


def _patch_native(source: Path, offset: int, output: Path) -> None:
    data = bytearray(source.read_bytes())
    if data[offset : offset + 4] != _NATIVE_OLD_A or data[offset + 8 : offset + 12] != _NATIVE_OLD_B:
        raise PatchError("native gameplay target changed after probing")
    data[offset : offset + 4] = _NATIVE_NEW_A
    data[offset + 8 : offset + 12] = _NATIVE_NEW_B
    output.write_bytes(data)
    if _native_state(output)[0] != "patched":
        raise PatchError("native gameplay replacement verification failed")


def _patch_stub(source: Path, offset: int, output: Path) -> None:
    data = bytearray(source.read_bytes())
    if data[offset : offset + len(_STUB_OLD_PREFIX)] != _STUB_OLD_PREFIX:
        raise PatchError("startup helper changed after probing")
    data[offset : offset + len(_STUB_NEW_PREFIX)] = _STUB_NEW_PREFIX
    output.write_bytes(data)
    if _stub_state(output)[0] != "patched":
        raise PatchError("startup helper replacement verification failed")


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Emit replacements for every safely recognized original-state target."""

    report, unity_targets, native, stub = _analyse(extracted)
    if report["state"] not in ("original", "patched"):
        raise PatchError(f"Sea of Stars core patch targets are {report['state']}")

    replacements: dict[str, Path] = {}
    grouped: dict[str, list[_UnityTarget]] = {}
    for target in unity_targets:
        if target.status == "original":
            grouped.setdefault(target.entry, []).append(target)
    entry_map = _normal_entries(extracted)
    for entry, targets in grouped.items():
        source = entry_map[entry.lower()][1]
        output = _replacement_path(Path(output_dir), entry)
        _patch_unity_bundle(source, targets, output)
        replacements[entry] = output

    native_entry = _entry(extracted, _IL2CPP_ENTRY)
    if native[0] == "original" and native_entry is not None:
        output = _replacement_path(Path(output_dir), native_entry[0])
        _patch_native(native_entry[1], native[1], output)
        replacements[native_entry[0]] = output

    stub_entry = _entry(extracted, _STUB_ENTRY)
    if stub[0] == "original" and stub_entry is not None:
        output = _replacement_path(Path(output_dir), stub_entry[0])
        _patch_stub(stub_entry[1], stub[1], output)
        replacements[stub_entry[0]] = output

    return replacements
