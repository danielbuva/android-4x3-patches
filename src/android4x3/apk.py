"""APK inspection, selective extraction, and structure-preserving repacking."""

from __future__ import annotations

import collections
import copy
import fnmatch
import importlib.util
import os
import shutil
import stat
import struct
import sys
import tempfile
import zipfile
from pathlib import Path
from types import ModuleType

from .errors import PatchError
from .manifest import ManifestInfo, parse_manifest


def inspect_apk(path: Path) -> ManifestInfo:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            duplicates = [name for name, count in collections.Counter(i.filename for i in infos).items() if count > 1]
            if duplicates:
                raise PatchError("APK has duplicate entries: " + ", ".join(sorted(duplicates)[:5]))
            if any(info.flag_bits & 1 for info in infos):
                raise PatchError("encrypted APK entries are unsupported")
            try:
                manifest = archive.read("AndroidManifest.xml")
            except KeyError as exc:
                raise PatchError("APK is missing AndroidManifest.xml") from exc
            return parse_manifest(manifest)
    except zipfile.BadZipFile as exc:
        raise PatchError(f"not a valid APK/ZIP archive: {path}") from exc


def resolve_entries(apk: Path, required: tuple[str, ...], extra_globs: tuple[str, ...]) -> list[str]:
    with zipfile.ZipFile(apk, "r") as archive:
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
    selected: set[str] = set()
    missing: list[str] = []
    for pattern in (*required, *extra_globs):
        matches = [name for name in names if fnmatch.fnmatchcase(name, pattern)]
        if not matches and pattern in required:
            missing.append(pattern)
        selected.update(matches)
    if missing:
        raise PatchError("missing required APK entries: " + ", ".join(missing))
    return sorted(selected)


def _safe_destination(root: Path, entry: str) -> Path:
    relative = Path(entry)
    if relative.is_absolute() or ".." in relative.parts:
        raise PatchError(f"unsafe APK entry path: {entry}")
    destination = (root / relative).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError as exc:
        raise PatchError(f"unsafe APK entry path: {entry}") from exc
    return destination


def extract_entries(apk: Path, entries: list[str], root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    with zipfile.ZipFile(apk, "r") as archive:
        for entry in entries:
            destination = _safe_destination(root, entry)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry, "r") as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            result[entry] = destination
    return result


def _branding_backend(repo_root: Path) -> ModuleType:
    path = repo_root / "tools" / "apkvision_neutralize.py"
    spec = importlib.util.spec_from_file_location("android4x3_optional_branding", path)
    if spec is None or spec.loader is None:
        raise PatchError("optional branding backend is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _plain_plan(backend: ModuleType, input_apk: Path, output_apk: Path, replacements: dict[str, Path]):
    plan = backend.PatchPlan(input_path=input_apk.resolve(), output_path=output_apk.resolve())
    with zipfile.ZipFile(input_apk, "r") as archive:
        infos = archive.infolist()
        names = {info.filename for info in infos}
        for entry, path in replacements.items():
            if entry not in names:
                raise PatchError(f"replacement target disappeared from APK: {entry}")
            plan.replacement_files[entry] = path.resolve()
        for info in infos:
            plan.alignments[info.filename] = backend._wanted_alignment(archive, info)
            if backend._is_signature_entry(info.filename):
                plan.removed_entries.add(info.filename)
                plan.signature_entries += 1
    return plan


def _strip_repack_extra_fields(extra: bytes) -> bytes:
    """Drop stale ZIP64/zipalign fields while retaining unknown metadata."""
    cursor = 0
    kept = bytearray()
    while cursor + 4 <= len(extra):
        field_id, size = struct.unpack_from("<HH", extra, cursor)
        end = cursor + 4 + size
        if end > len(extra):
            return extra
        if field_id not in {0x0001, 0xD935}:
            kept.extend(extra[cursor:end])
        cursor = end
    return bytes(kept) if cursor == len(extra) else extra


def _is_v1_signature(name: str) -> bool:
    upper = name.upper()
    if not upper.startswith("META-INF/"):
        return False
    leaf = upper[len("META-INF/") :]
    if "/" in leaf:
        return False
    return leaf == "MANIFEST.MF" or leaf.startswith("SIG-") or leaf.endswith(
        (".SF", ".RSA", ".DSA", ".EC")
    )


def _stdlib_core_repack(
    input_apk: Path,
    output_apk: Path,
    replacements: dict[str, Path],
) -> None:
    """Core-only fallback used when the optional branding helper cannot run.

    The final workflow always runs Android's zipalign after this intermediate
    repack, so stale alignment padding is removed here and recreated there.
    """
    output_apk.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_apk.name}.", suffix=".tmp", dir=output_apk.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    previous_zip64_limit = zipfile.ZIP64_LIMIT
    try:
        with zipfile.ZipFile(input_apk, "r") as source:
            infos = source.infolist()
            names = {info.filename for info in infos}
            missing = sorted(set(replacements) - names)
            if missing:
                raise PatchError(
                    "replacement target disappeared from APK: " + ", ".join(missing)
                )
            # Android APKs cannot use ZIP64, while Python otherwise starts
            # emitting it at 2 GiB even though classic ZIP fields reach 4 GiB.
            zipfile.ZIP64_LIMIT = 0xFFFFFFFE
            with zipfile.ZipFile(temporary, "w", allowZip64=False) as destination:
                destination.comment = source.comment
                for info in infos:
                    if _is_v1_signature(info.filename):
                        continue
                    cloned = copy.copy(info)
                    cloned.extra = _strip_repack_extra_fields(info.extra)
                    cloned.CRC = 0
                    cloned.compress_size = 0
                    replacement = replacements.get(info.filename)
                    cloned.file_size = replacement.stat().st_size if replacement else info.file_size
                    with destination.open(cloned, "w", force_zip64=False) as target:
                        if replacement is not None:
                            with replacement.open("rb") as replacement_stream:
                                shutil.copyfileobj(replacement_stream, target, length=1024 * 1024)
                        else:
                            with source.open(info, "r") as original:
                                shutil.copyfileobj(original, target, length=1024 * 1024)
        os.chmod(temporary, stat.S_IMODE(input_apk.stat().st_mode))
        os.replace(temporary, output_apk)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        zipfile.ZIP64_LIMIT = previous_zip64_limit


def repack_with_optional_branding(
    repo_root: Path,
    input_apk: Path,
    output_apk: Path,
    replacements: dict[str, Path],
) -> None:
    """Repack core changes; optional branding failures are deliberately silent."""
    pairs = list(replacements.items())
    backend: ModuleType | None = None
    try:
        backend = _branding_backend(repo_root)
        plan = backend.analyze_apk(
            input_apk,
            output_apk,
            remove_branding=True,
            allow_no_runtime_patch=False,
            replace_entries=pairs,
        )
        if not plan.detected and not plan.replacement_files:
            plan = _plain_plan(backend, input_apk, output_apk, replacements)
        backend._write_apk(plan, force=True, full_verify=False)
        return
    except Exception:
        pass
    if backend is not None:
        try:
            plan = _plain_plan(backend, input_apk, output_apk, replacements)
            backend._write_apk(plan, force=True, full_verify=False)
            return
        except Exception:
            pass
    _stdlib_core_repack(input_apk, output_apk, replacements)


def verify_zip(path: Path, *, full: bool = False, allow_signatures: bool = False) -> None:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            if full:
                bad = archive.testzip()
                if bad:
                    raise PatchError(f"CRC verification failed for {bad}")
            if not allow_signatures and any(name.upper().startswith("META-INF/") and name.upper().endswith((".RSA", ".DSA", ".EC", ".SF", "MANIFEST.MF")) for name in archive.namelist()):
                raise PatchError("stale v1 signing records remain after repacking")
    except zipfile.BadZipFile as exc:
        raise PatchError("APK is not a valid ZIP archive") from exc
