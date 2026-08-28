"""Fail-closed coverage for optional standalone APKVision JNI cleanup."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from tools import apkvision_neutralize as branding


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_unknown_standalone_jni_onload_library_is_silently_unchanged(
    tmp_path: Path,
) -> None:
    # A name and JNI_OnLoad marker used to be enough to reach the ELF rewrite.
    # This deliberately malformed invented payload also proves the digest gate
    # runs before parsing or touching an unknown native implementation.
    unknown = b"\x7fELF invented launch-critical JNI_OnLoad implementation"

    modified, changes, targets, patches = branding.patch_native_entry(
        "lib/arm64-v8a/libapkvision.so", unknown, True
    )

    assert modified == unknown
    assert changes == []
    assert targets == 0
    assert patches == 0

    source = tmp_path / "unknown.apk"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("lib/arm64-v8a/libapkvision.so", unknown)
    plan = branding.analyze_apk(source, dry_run=True)
    assert not plan.detected
    assert plan.modified_entries == {}
    assert plan.warnings == []


def test_exact_allowlisted_overlay_only_library_is_patched(
    monkeypatch,
) -> None:
    original = b"invented-safe-overlay" + b"\x11" * 32
    function_offset = 8

    class SyntheticElf:
        EM_ARM = branding.ElfImage.EM_ARM
        EM_AARCH64 = branding.ElfImage.EM_AARCH64
        EM_386 = branding.ElfImage.EM_386
        EM_X86_64 = branding.ElfImage.EM_X86_64

        def __init__(self, data):
            self.data = data
            self.machine = self.EM_AARCH64

        def dynamic_symbol_info(self, name: str):
            assert name == "JNI_OnLoad"
            return branding._DynamicSymbol(function_offset, 12)

        def va_to_offset(self, vaddr: int, size: int = 1, executable: bool = False):
            assert vaddr == function_offset
            assert function_offset + size <= len(self.data)
            assert executable
            return function_offset

    monkeypatch.setattr(
        branding,
        "KNOWN_SAFE_STANDALONE_NATIVE_SHA256",
        {"libapkvision.so": frozenset({_digest(original)})},
    )
    monkeypatch.setattr(branding, "ElfImage", SyntheticElf)

    modified, changes, targets, patches = branding.patch_native_entry(
        "lib/arm64-v8a/libapkvision.so", original, True
    )

    assert modified != original
    assert targets == 1
    assert patches == 1
    assert [change.kind for change in changes] == ["native-jni-onload"]
    assert modified[function_offset : function_offset + 12] == bytes.fromhex(
        "c00080522000a072c0035fd6"
    )


def test_close_but_not_allowlisted_library_never_reaches_elf_parser(
    monkeypatch,
) -> None:
    safe = b"invented-safe-overlay" + b"\x11" * 32
    changed = safe[:-1] + b"\x12"
    monkeypatch.setattr(
        branding,
        "KNOWN_SAFE_STANDALONE_NATIVE_SHA256",
        {"libapkvisionorg.so": frozenset({_digest(safe)})},
    )

    class ForbiddenElf:
        def __init__(self, _data):
            raise AssertionError("unknown native fingerprint was parsed")

    monkeypatch.setattr(branding, "ElfImage", ForbiddenElf)
    result = branding.patch_native_entry(
        "lib/x86/libapkvisionorg.so", changed, True
    )
    assert result == (changed, [], 0, 0)


def test_sor4_protected_libstub_recipe_is_guarded_resumable_and_idempotent(
    monkeypatch,
) -> None:
    calls = ((0x20, "wrapper"), (0x30, "overlay"), (0x40, "context"), (0x50, "service"))
    original = bytearray(b"\xa5" * 0x80)
    for offset, _detail in calls:
        original[offset : offset + 4] = branding._AARCH64_BLR_X8
    patched = bytearray(original)
    for offset, _detail in calls:
        patched[offset : offset + 4] = branding._AARCH64_NOP

    monkeypatch.setattr(branding, "SOR4_V145_STARTUP_CALLS", calls)
    monkeypatch.setattr(
        branding, "SOR4_V145_LIBSTUB_ORIGINAL_SHA256", _digest(bytes(original))
    )
    monkeypatch.setattr(
        branding, "SOR4_V145_LIBSTUB_PATCHED_SHA256", _digest(bytes(patched))
    )

    mixed = bytearray(original)
    mixed[calls[0][0] : calls[0][0] + 4] = branding._AARCH64_NOP
    result, changes, targets, patches = branding.patch_native_entry(
        "lib/arm64-v8a/libstub.so", bytes(mixed), True
    )
    assert result == patched
    assert targets == 4
    assert patches == 3
    assert [change.kind for change in changes].count("already-neutralized") == 1

    second, changes, targets, patches = branding.patch_native_entry(
        "lib/arm64-v8a/libstub.so", result, True
    )
    assert second == result
    assert targets == 4
    assert patches == 0
    assert {change.kind for change in changes} == {"already-neutralized"}

    unfamiliar = bytearray(original)
    unfamiliar[0] ^= 1

    class ForbiddenElf:
        def __init__(self, _data):
            raise branding.PatchError("unrecognized synthetic ELF")

    monkeypatch.setattr(branding, "ElfImage", ForbiddenElf)
    try:
        branding.patch_native_entry("lib/arm64-v8a/libstub.so", bytes(unfamiliar), True)
    except branding.PatchError:
        pass
    else:  # pragma: no cover - proves a near-match never uses the recipe
        raise AssertionError("unrecognized protected libstub reached the audited recipe")
