#!/usr/bin/env python3
"""Non-destructively neutralize known APKVision runtime branding hooks.

The patcher intentionally keeps injected native libraries present.  Removing a
library which is still named by System.loadLibrary() makes Android abort during
class initialization.  Instead, this module patches only well-known overlay
entry points, removes known branding assets after a runtime patch was found,
strips stale APK signatures, and repacks to a different file.

Only the Python standard library is required.
"""

from __future__ import annotations

import argparse
import copy
import collections
import contextlib
import dataclasses
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path
from typing import Iterator, Sequence


APK_SUFFIX = ".apk"
APK_ALIGNMENT_EXTRA_ID = 0xD935
ZIP64_EXTRA_ID = 0x0001
# The ZIP32 size/offset fields use 0xFFFFFFFF as the ZIP64 sentinel, so this
# is the largest value that can be represented without an extension record.
ZIP32_LIMIT = 0xFFFFFFFE

KNOWN_AVCONFIG_SHA256 = {
    # Lexend font stored as assets/AVConfig.json in the accepted APK set.
    "301935ee6ea4053a7ad151c1ded2ee8f68ba187c63e6b4eb25d36e39b091247c",
}

BRANDING_ASSET_NAMES = {
    "assets/apkvision.config",
    "assets/avconfig.json",
}

STANDALONE_LIBRARY_NAMES = {
    "libapkvision.so",
    "libapkvisionorg.so",
}

STUB_MARKERS = (
    b"apkvision/",
    b"https://apkvision.org/",
    b"AVConfig.json",
    b"CheckOverlayPermission",
    b"SetWindowManagerActivity",
)

DEX_MARKERS = (
    b"Lapkvision/",
    b"com.apkvision.",
)

VOID_OVERLAY_METHODS = {
    ("krjUyALI", "(Landroid/app/Activity;)V"),
    ("vPoUAvVoP", "(Landroid/content/Context;)V"),
}

SUPPORT_START_METHODS = {
    ("Start", "(Landroid/content/Context;)V"),
    ("StartWithoutPermission", "(Landroid/content/Context;)V"),
}

DEX_MAGIC = b"dex\n"

# Valid 1x1 transparent RGBA PNG.  Keeping the expected asset path is safer
# than deleting it if an unrecognized fallback loader still opens the file.
TRANSPARENT_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000b49444154789c6360000200000500017a5eab3f0000000049454e44ae426082"
)


class PatchError(RuntimeError):
    """Raised when an APK cannot be patched without guessing."""


@contextlib.contextmanager
def _zip32_write_limit() -> Iterator[None]:
    """Let stdlib zipfile use the full unsigned ZIP32 range while writing.

    Python deliberately defaults ``ZIP64_LIMIT`` to 2 GiB, even though classic
    ZIP fields can hold unsigned values up to 0xFFFFFFFE. Android APK tooling
    rejects ZIP64 archives, so ordinary APKs between 2 GiB and 4 GiB must be
    written with the format's real ZIP32 limit. Keep the override scoped to a
    destination archive's complete lifetime because its central directory is
    emitted by ``ZipFile.close()``.
    """
    previous_limit = zipfile.ZIP64_LIMIT
    zipfile.ZIP64_LIMIT = ZIP32_LIMIT
    try:
        yield
    finally:
        zipfile.ZIP64_LIMIT = previous_limit


@dataclasses.dataclass(frozen=True)
class Change:
    kind: str
    entry: str
    detail: str
    offset: int | None = None


@dataclasses.dataclass
class PatchPlan:
    input_path: Path
    output_path: Path | None
    detected: bool = False
    detection_reasons: list[str] = dataclasses.field(default_factory=list)
    changes: list[Change] = dataclasses.field(default_factory=list)
    warnings: list[str] = dataclasses.field(default_factory=list)
    removed_entries: set[str] = dataclasses.field(default_factory=set)
    renamed_entries: dict[str, str] = dataclasses.field(default_factory=dict)
    modified_entries: dict[str, bytes] = dataclasses.field(default_factory=dict)
    replacement_files: dict[str, Path] = dataclasses.field(default_factory=dict)
    alignments: dict[str, int] = dataclasses.field(default_factory=dict)
    runtime_targets: int = 0
    runtime_patches: int = 0
    signature_entries: int = 0
    dry_run: bool = False
    wrote_output: bool = False

    def public_dict(self) -> dict[str, object]:
        return {
            "input": str(self.input_path),
            "output": str(self.output_path) if self.output_path else None,
            "dry_run": self.dry_run,
            "detected": self.detected,
            "detection_reasons": self.detection_reasons,
            "runtime_targets": self.runtime_targets,
            "runtime_patches": self.runtime_patches,
            "signature_entries_stripped": self.signature_entries,
            "removed_entries": sorted(self.removed_entries),
            "renamed_entries": dict(sorted(self.renamed_entries.items())),
            "replacement_files": {
                name: str(path) for name, path in sorted(self.replacement_files.items())
            },
            "changes": [dataclasses.asdict(change) for change in self.changes],
            "warnings": self.warnings,
            "wrote_output": self.wrote_output,
        }


@dataclasses.dataclass(frozen=True)
class _ProgramHeader:
    p_type: int
    offset: int
    vaddr: int
    filesz: int
    memsz: int
    flags: int


@dataclasses.dataclass(frozen=True)
class _SectionHeader:
    name: str
    sh_type: int
    flags: int
    addr: int
    offset: int
    size: int
    link: int
    info: int
    align: int
    entsize: int


@dataclasses.dataclass(frozen=True)
class NativeMethod:
    name: str
    descriptor: str
    function_vaddr: int
    table_vaddr: int


@dataclasses.dataclass(frozen=True)
class _DynamicSymbol:
    value: int
    size: int


class ElfImage:
    """Small, strict ELF reader for the metadata needed by this patcher."""

    PT_LOAD = 1
    PF_X = 1
    SHT_RELA = 4
    SHT_REL = 9
    SHT_DYNSYM = 11
    SHN_UNDEF = 0

    EM_386 = 3
    EM_ARM = 40
    EM_X86_64 = 62
    EM_AARCH64 = 183

    RELATIVE_RELOCATION_TYPES = {
        EM_386: 8,  # R_386_RELATIVE
        EM_ARM: 23,  # R_ARM_RELATIVE
        EM_X86_64: 8,  # R_X86_64_RELATIVE
        EM_AARCH64: 1027,  # R_AARCH64_RELATIVE
    }

    def __init__(self, data: bytes | bytearray):
        self.data = data
        if len(data) < 0x34 or data[:4] != b"\x7fELF":
            raise PatchError("not an ELF image")
        elf_class = data[4]
        endian = data[5]
        if elf_class not in (1, 2):
            raise PatchError(f"unsupported ELF class {elf_class}")
        if endian != 1:
            raise PatchError("only little-endian ELF images are supported")
        self.is_64 = elf_class == 2
        self.pointer_size = 8 if self.is_64 else 4
        self._parse_header()
        self.program_headers = self._parse_program_headers()
        self.sections = self._parse_section_headers()

    def _parse_header(self) -> None:
        if self.is_64:
            fmt = "<HHIQQQIHHHHHH"
        else:
            fmt = "<HHIIIIIHHHHHH"
        values = self._unpack_from(fmt, 16)
        (
            _e_type,
            self.machine,
            _e_version,
            _e_entry,
            self.phoff,
            self.shoff,
            _e_flags,
            _e_ehsize,
            self.phentsize,
            self.phnum,
            self.shentsize,
            self.shnum,
            self.shstrndx,
        ) = values

    def _parse_program_headers(self) -> list[_ProgramHeader]:
        fmt = "<IIQQQQQQ" if self.is_64 else "<IIIIIIII"
        expected = struct.calcsize(fmt)
        if self.phentsize < expected:
            raise PatchError("truncated ELF program header size")
        result: list[_ProgramHeader] = []
        for index in range(self.phnum):
            values = self._unpack_from(fmt, self.phoff + index * self.phentsize)
            if self.is_64:
                p_type, flags, offset, vaddr, _paddr, filesz, memsz, _align = values
            else:
                p_type, offset, vaddr, _paddr, filesz, memsz, flags, _align = values
            result.append(_ProgramHeader(p_type, offset, vaddr, filesz, memsz, flags))
        return result

    def _parse_section_headers(self) -> list[_SectionHeader]:
        fmt = "<IIQQQQIIQQ" if self.is_64 else "<IIIIIIIIII"
        expected = struct.calcsize(fmt)
        if self.shentsize < expected:
            raise PatchError("truncated ELF section header size")

        raw: list[tuple[int, ...]] = []
        for index in range(self.shnum):
            raw.append(self._unpack_from(fmt, self.shoff + index * self.shentsize))

        if not raw:
            return []
        if not 0 <= self.shstrndx < len(raw):
            raise PatchError("invalid ELF section-name table index")
        string_header = raw[self.shstrndx]
        strings_offset = string_header[4]
        strings_size = string_header[5]
        strings = self._slice(strings_offset, strings_size)

        result: list[_SectionHeader] = []
        for values in raw:
            (
                name_offset,
                sh_type,
                flags,
                addr,
                offset,
                size,
                link,
                info,
                align,
                entsize,
            ) = values
            name = _read_c_string_from_blob(strings, name_offset) or ""
            result.append(
                _SectionHeader(name, sh_type, flags, addr, offset, size, link, info, align, entsize)
            )
        return result

    def _slice(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0 or offset + size > len(self.data):
            raise PatchError("ELF structure points outside the file")
        return bytes(self.data[offset : offset + size])

    def _unpack_from(self, fmt: str, offset: int) -> tuple[int, ...]:
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(self.data):
            raise PatchError("truncated ELF structure")
        return struct.unpack_from(fmt, self.data, offset)

    def va_to_offset(self, vaddr: int, size: int = 1, executable: bool = False) -> int:
        for segment in self.program_headers:
            if segment.p_type != self.PT_LOAD:
                continue
            if executable and not (segment.flags & self.PF_X):
                continue
            if segment.vaddr <= vaddr and vaddr + size <= segment.vaddr + segment.filesz:
                offset = segment.offset + vaddr - segment.vaddr
                if offset + size <= len(self.data):
                    return offset
        raise PatchError(f"ELF virtual address 0x{vaddr:x} is not file-backed")

    def c_string_at_va(self, vaddr: int, limit: int = 512) -> str | None:
        try:
            offset = self.va_to_offset(vaddr)
        except PatchError:
            return None
        end = min(len(self.data), offset + limit)
        nul = bytes(self.data).find(b"\0", offset, end)
        if nul < 0 or nul == offset:
            return None
        value = bytes(self.data[offset:nul])
        if any(byte < 0x20 or byte > 0x7E for byte in value):
            return None
        return value.decode("ascii")

    def dynamic_symbol_info(self, wanted_name: str) -> _DynamicSymbol | None:
        symbol_fmt = "<IBBHQQ" if self.is_64 else "<IIIBBH"
        default_size = struct.calcsize(symbol_fmt)
        for section in self.sections:
            if section.sh_type != self.SHT_DYNSYM:
                continue
            if not 0 <= section.link < len(self.sections):
                continue
            strings = self.sections[section.link]
            string_data = self._slice(strings.offset, strings.size)
            entry_size = section.entsize or default_size
            if entry_size < default_size:
                continue
            count = section.size // entry_size
            for index in range(count):
                values = self._unpack_from(symbol_fmt, section.offset + index * entry_size)
                if self.is_64:
                    name_offset, _info, _other, shndx, value, _size = values
                else:
                    name_offset, value, _size, _info, _other, shndx = values
                name = _read_c_string_from_blob(string_data, name_offset)
                if name == wanted_name and shndx != self.SHN_UNDEF and value:
                    return _DynamicSymbol(value, _size)
        return None

    def dynamic_symbol(self, wanted_name: str) -> int | None:
        symbol = self.dynamic_symbol_info(wanted_name)
        return symbol.value if symbol is not None else None

    def relative_relocations(self) -> dict[int, int]:
        """Return relative relocation target-address -> addend mappings."""
        result: dict[int, int] = {}
        ptr_fmt = "<Q" if self.is_64 else "<I"
        for section in self.sections:
            if section.sh_type not in (self.SHT_REL, self.SHT_RELA):
                continue
            if section.sh_type == self.SHT_RELA:
                fmt = "<QQq" if self.is_64 else "<IIi"
            else:
                fmt = "<QQ" if self.is_64 else "<II"
            default_size = struct.calcsize(fmt)
            entry_size = section.entsize or default_size
            if entry_size < default_size:
                continue
            for index in range(section.size // entry_size):
                values = self._unpack_from(fmt, section.offset + index * entry_size)
                target, info = values[0], values[1]
                symbol_index = info >> (32 if self.is_64 else 8)
                relocation_type = info & (0xFFFFFFFF if self.is_64 else 0xFF)
                if symbol_index != 0:
                    continue
                if relocation_type != self.RELATIVE_RELOCATION_TYPES.get(self.machine):
                    continue
                if section.sh_type == self.SHT_RELA:
                    addend = values[2]
                else:
                    try:
                        raw_offset = self.va_to_offset(target, self.pointer_size)
                    except PatchError:
                        continue
                    addend = struct.unpack_from(ptr_fmt, self.data, raw_offset)[0]
                if addend >= 0:
                    result[target] = addend
        return result

    def native_methods(self) -> list[NativeMethod]:
        """Recover JNINativeMethod triples from relative relocations."""
        relocations = self.relative_relocations()
        result: list[NativeMethod] = []
        pointer_size = self.pointer_size
        for table_vaddr, name_vaddr in relocations.items():
            descriptor_vaddr = relocations.get(table_vaddr + pointer_size)
            function_vaddr = relocations.get(table_vaddr + 2 * pointer_size)
            if descriptor_vaddr is None or function_vaddr is None:
                continue
            name = self.c_string_at_va(name_vaddr)
            descriptor = self.c_string_at_va(descriptor_vaddr)
            if not name or not descriptor or not _looks_like_method_descriptor(descriptor):
                continue
            function_base = _normalize_function_vaddr(self.machine, function_vaddr)
            try:
                self.va_to_offset(function_base, executable=True)
            except PatchError:
                continue
            result.append(NativeMethod(name, descriptor, function_vaddr, table_vaddr))
        return result


@dataclasses.dataclass(frozen=True)
class _DexMethod:
    class_descriptor: str
    name: str
    descriptor: str
    code_offset: int


class DexImage:
    """Minimal DEX parser supporting in-place replacement of void methods."""

    HEADER_SIZE = 0x70

    def __init__(self, data: bytes | bytearray):
        self.data = bytearray(data)
        if len(self.data) < self.HEADER_SIZE or self.data[:4] != DEX_MAGIC:
            raise PatchError("not a standard DEX file")
        declared_size = self._u32(0x20)
        header_size = self._u32(0x24)
        endian_tag = self._u32(0x28)
        if declared_size != len(self.data):
            raise PatchError("DEX file-size field does not match the entry size")
        if header_size != self.HEADER_SIZE or endian_tag != 0x12345678:
            raise PatchError("unsupported DEX header")
        self.string_ids_size = self._u32(0x38)
        self.string_ids_off = self._u32(0x3C)
        self.type_ids_size = self._u32(0x40)
        self.type_ids_off = self._u32(0x44)
        self.proto_ids_size = self._u32(0x48)
        self.proto_ids_off = self._u32(0x4C)
        self.method_ids_size = self._u32(0x58)
        self.method_ids_off = self._u32(0x5C)
        self.class_defs_size = self._u32(0x60)
        self.class_defs_off = self._u32(0x64)
        self._strings: list[str] | None = None
        self._types: list[str] | None = None

    def _check(self, offset: int, size: int) -> None:
        if offset < 0 or size < 0 or offset + size > len(self.data):
            raise PatchError("DEX structure points outside the file")

    def _u16(self, offset: int) -> int:
        self._check(offset, 2)
        return struct.unpack_from("<H", self.data, offset)[0]

    def _u32(self, offset: int) -> int:
        self._check(offset, 4)
        return struct.unpack_from("<I", self.data, offset)[0]

    def _uleb128(self, offset: int) -> tuple[int, int]:
        value = 0
        shift = 0
        for index in range(5):
            self._check(offset, 1)
            byte = self.data[offset]
            offset += 1
            if index == 4 and byte & 0xF0:
                raise PatchError("DEX ULEB128 value exceeds 32 bits")
            value |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                return value, offset
            shift += 7
        raise PatchError("invalid DEX ULEB128 value")

    @property
    def strings(self) -> list[str]:
        if self._strings is None:
            self._check(self.string_ids_off, self.string_ids_size * 4)
            result: list[str] = []
            for index in range(self.string_ids_size):
                data_offset = self._u32(self.string_ids_off + index * 4)
                _utf16_size, cursor = self._uleb128(data_offset)
                nul = self.data.find(0, cursor)
                if nul < 0:
                    raise PatchError("unterminated DEX string")
                result.append(bytes(self.data[cursor:nul]).decode("utf-8", "replace"))
            self._strings = result
        return self._strings

    @property
    def types(self) -> list[str]:
        if self._types is None:
            self._check(self.type_ids_off, self.type_ids_size * 4)
            result: list[str] = []
            for index in range(self.type_ids_size):
                string_index = self._u32(self.type_ids_off + index * 4)
                if string_index >= len(self.strings):
                    raise PatchError("invalid DEX type string index")
                result.append(self.strings[string_index])
            self._types = result
        return self._types

    def _proto_descriptor(self, proto_index: int) -> str:
        if proto_index >= self.proto_ids_size:
            raise PatchError("invalid DEX prototype index")
        offset = self.proto_ids_off + proto_index * 12
        self._check(offset, 12)
        return_type_index = self._u32(offset + 4)
        parameters_off = self._u32(offset + 8)
        if return_type_index >= len(self.types):
            raise PatchError("invalid DEX return type")
        parameters: list[str] = []
        if parameters_off:
            count = self._u32(parameters_off)
            self._check(parameters_off + 4, count * 2)
            for index in range(count):
                type_index = self._u16(parameters_off + 4 + index * 2)
                if type_index >= len(self.types):
                    raise PatchError("invalid DEX parameter type")
                parameters.append(self.types[type_index])
        return "(" + "".join(parameters) + ")" + self.types[return_type_index]

    def _method_identity(self, method_index: int) -> tuple[str, str, str]:
        if method_index >= self.method_ids_size:
            raise PatchError("invalid DEX method index")
        offset = self.method_ids_off + method_index * 8
        self._check(offset, 8)
        class_index = self._u16(offset)
        proto_index = self._u16(offset + 2)
        name_index = self._u32(offset + 4)
        if class_index >= len(self.types) or name_index >= len(self.strings):
            raise PatchError("invalid DEX method identity")
        return self.types[class_index], self.strings[name_index], self._proto_descriptor(proto_index)

    def methods(self) -> Iterator[_DexMethod]:
        self._check(self.class_defs_off, self.class_defs_size * 32)
        for class_index in range(self.class_defs_size):
            class_def = self.class_defs_off + class_index * 32
            class_data_off = self._u32(class_def + 24)
            if not class_data_off:
                continue
            cursor = class_data_off
            static_fields, cursor = self._uleb128(cursor)
            instance_fields, cursor = self._uleb128(cursor)
            direct_methods, cursor = self._uleb128(cursor)
            virtual_methods, cursor = self._uleb128(cursor)
            field_count = static_fields + instance_fields
            method_count = direct_methods + virtual_methods
            minimum_bytes = field_count * 2 + method_count * 3
            if minimum_bytes > len(self.data) - cursor:
                raise PatchError("DEX class-data counts exceed the remaining entry size")
            for _ in range(field_count):
                _field_diff, cursor = self._uleb128(cursor)
                _field_access, cursor = self._uleb128(cursor)
            for method_count in (direct_methods, virtual_methods):
                method_index = 0
                for _ in range(method_count):
                    method_diff, cursor = self._uleb128(cursor)
                    method_index += method_diff
                    _method_access, cursor = self._uleb128(cursor)
                    code_offset, cursor = self._uleb128(cursor)
                    class_desc, name, descriptor = self._method_identity(method_index)
                    yield _DexMethod(class_desc, name, descriptor, code_offset)

    def replace_void_method(self, method: _DexMethod) -> tuple[bool, int]:
        if not method.code_offset:
            return False, 0
        self._check(method.code_offset, 16)
        instructions_size = self._u32(method.code_offset + 12)
        instructions_offset = method.code_offset + 16
        byte_size = instructions_size * 2
        self._check(instructions_offset, byte_size)
        if byte_size < 2:
            raise PatchError("DEX method has an empty code item")
        replacement = b"\x0e\x00" + b"\x00" * (byte_size - 2)  # return-void; nop...
        before = bytes(self.data[instructions_offset : instructions_offset + byte_size])
        if before == replacement:
            return False, instructions_offset
        self.data[instructions_offset : instructions_offset + byte_size] = replacement
        return True, instructions_offset

    def finish(self) -> bytes:
        self.data[12:32] = hashlib.sha1(self.data[32:]).digest()
        struct.pack_into("<I", self.data, 8, zlib.adler32(self.data[12:]) & 0xFFFFFFFF)
        return bytes(self.data)


def _read_c_string_from_blob(blob: bytes, offset: int) -> str | None:
    if offset < 0 or offset >= len(blob):
        return None
    nul = blob.find(b"\0", offset)
    if nul < 0:
        return None
    try:
        return blob[offset:nul].decode("ascii")
    except UnicodeDecodeError:
        return None


def _looks_like_method_descriptor(value: str) -> bool:
    if not value.startswith("(") or ")" not in value:
        return False
    closing = value.find(")")
    return closing > 0 and closing + 1 < len(value) and len(value) < 400


def _normalize_function_vaddr(machine: int, vaddr: int) -> int:
    if machine == ElfImage.EM_ARM:
        return vaddr & ~1
    return vaddr


def _function_patch(machine: int, thumb: bool, return_jni_version: bool, prefix: bytes = b"") -> bytes:
    if return_jni_version:
        if machine == ElfImage.EM_AARCH64:
            body = bytes.fromhex("c00080522000a072c0035fd6")
        elif machine == ElfImage.EM_ARM and thumb:
            body = bytes.fromhex("40f20600c0f201007047")
        elif machine == ElfImage.EM_ARM:
            body = bytes.fromhex("060000e3010040e31eff2fe1")
        elif machine in (ElfImage.EM_386, ElfImage.EM_X86_64):
            body = bytes.fromhex("b806000100c3")
        else:
            raise PatchError(f"unsupported ELF machine {machine}")
    else:
        if machine == ElfImage.EM_AARCH64:
            body = bytes.fromhex("c0035fd6")
        elif machine == ElfImage.EM_ARM and thumb:
            body = bytes.fromhex("7047")
        elif machine == ElfImage.EM_ARM:
            body = bytes.fromhex("1eff2fe1")
        elif machine in (ElfImage.EM_386, ElfImage.EM_X86_64):
            body = b"\xc3"
        else:
            raise PatchError(f"unsupported ELF machine {machine}")
    return prefix + body


def _landing_pad_prefix(elf: ElfImage, function_offset: int) -> bytes:
    first = bytes(elf.data[function_offset : function_offset + 4])
    if elf.machine == ElfImage.EM_AARCH64 and first in {
        bytes.fromhex("5f2403d5"),  # bti c
        bytes.fromhex("9f2403d5"),  # bti j
        bytes.fromhex("df2403d5"),  # bti jc
    }:
        return first
    if elf.machine in (ElfImage.EM_386, ElfImage.EM_X86_64) and first in {
        bytes.fromhex("f30f1efa"),  # endbr64
        bytes.fromhex("f30f1efb"),  # endbr32
    }:
        return first
    return b""


def _patch_elf_function(
    mutable: bytearray,
    elf: ElfImage,
    function_vaddr: int,
    return_jni_version: bool,
    function_size: int | None = None,
) -> tuple[bool, int]:
    thumb = elf.machine == ElfImage.EM_ARM and bool(function_vaddr & 1)
    normalized = _normalize_function_vaddr(elf.machine, function_vaddr)
    offset = elf.va_to_offset(normalized, executable=True)
    prefix = _landing_pad_prefix(elf, offset)
    patch = _function_patch(elf.machine, thumb, return_jni_version, prefix)
    if function_size is not None and function_size < len(patch):
        raise PatchError(
            f"ELF function is only {function_size} bytes; {len(patch)} bytes are required for a safe patch"
        )
    # Re-resolve with the complete patch size so the write cannot cross the
    # executable file-backed segment even when a malformed address is supplied.
    offset = elf.va_to_offset(normalized, len(patch), executable=True)
    if bytes(mutable[offset : offset + len(patch)]) == patch:
        return False, offset
    mutable[offset : offset + len(patch)] = patch
    return True, offset


def patch_native_entry(entry_name: str, data: bytes, strong_apk_marker: bool) -> tuple[bytes, list[Change], int, int]:
    """Patch a known native payload and return data, changes, targets, patches."""
    basename = Path(entry_name).name.lower()
    if basename not in STANDALONE_LIBRARY_NAMES and basename != "libstub.so":
        return data, [], 0, 0
    try:
        mutable = bytearray(data)
        elf = ElfImage(mutable)
    except PatchError as exc:
        raise PatchError(f"{entry_name}: {exc}") from exc

    changes: list[Change] = []
    targets = 0
    patches = 0
    if basename in STANDALONE_LIBRARY_NAMES:
        function = elf.dynamic_symbol_info("JNI_OnLoad")
        if function is None:
            raise PatchError(f"{entry_name}: exported JNI_OnLoad was not found")
        targets += 1
        if function.size <= 0:
            raise PatchError(f"{entry_name}: JNI_OnLoad has no trustworthy ELF symbol size")
        changed, offset = _patch_elf_function(
            mutable,
            elf,
            function.value,
            return_jni_version=True,
            function_size=function.size,
        )
        if changed:
            patches += 1
            detail = "return JNI_VERSION_1_6 without initializing the injected library"
            changes.append(Change("native-jni-onload", entry_name, detail, offset))
        else:
            changes.append(Change("already-neutralized", entry_name, "JNI_OnLoad already returns immediately", offset))

    if basename == "libstub.so":
        methods = elf.native_methods()
        available = {(method.name, method.descriptor) for method in methods}
        wanted = set(VOID_OVERLAY_METHODS)
        if SUPPORT_START_METHODS.issubset(available) and strong_apk_marker:
            wanted.update(SUPPORT_START_METHODS)
        seen_functions: set[int] = set()
        for method in methods:
            key = (method.name, method.descriptor)
            if key not in wanted or method.function_vaddr in seen_functions:
                continue
            seen_functions.add(method.function_vaddr)
            targets += 1
            changed, offset = _patch_elf_function(
                mutable,
                elf,
                method.function_vaddr,
                return_jni_version=False,
            )
            label = f"{method.name}{method.descriptor}"
            if changed:
                patches += 1
                changes.append(Change("native-overlay-method", entry_name, f"replace {label} with a no-op", offset))
            else:
                changes.append(Change("already-neutralized", entry_name, f"{label} is already a no-op", offset))

    return bytes(mutable), changes, targets, patches


def _is_dex_overlay_method(method: _DexMethod) -> bool:
    identity = (method.name, method.descriptor)
    if "apkvision" in method.class_descriptor.lower() and identity in VOID_OVERLAY_METHODS:
        return True
    if method.class_descriptor == "Lcom/android/support/Main;" and identity in SUPPORT_START_METHODS:
        return True
    return False


def patch_dex_entry(entry_name: str, data: bytes) -> tuple[bytes, list[Change], int, int]:
    try:
        dex = DexImage(data)
        methods = list(dex.methods())
    except PatchError as exc:
        raise PatchError(f"{entry_name}: {exc}") from exc
    available = {(method.class_descriptor, method.name, method.descriptor) for method in methods}
    has_start_pair = all(
        ("Lcom/android/support/Main;", name, descriptor) in available
        for name, descriptor in SUPPORT_START_METHODS
    )

    changes: list[Change] = []
    targets = 0
    patches = 0
    for method in methods:
        if not _is_dex_overlay_method(method):
            continue
        if method.class_descriptor == "Lcom/android/support/Main;" and not has_start_pair:
            continue
        if not method.code_offset:
            # Native declarations are handled by the libstub relocation scanner.
            continue
        targets += 1
        changed, offset = dex.replace_void_method(method)
        label = f"{method.class_descriptor}->{method.name}{method.descriptor}"
        if changed:
            patches += 1
            changes.append(Change("dex-overlay-method", entry_name, f"replace {label} with return-void", offset))
        else:
            changes.append(Change("already-neutralized", entry_name, f"{label} already returns immediately", offset))
    return dex.finish() if patches else data, changes, targets, patches


def _namespace_replacements(namespace: str) -> tuple[tuple[bytes, bytes], ...]:
    if not re.fullmatch(r"[a-z][a-z0-9_]{8}", namespace):
        raise PatchError("replacement namespace must be exactly nine lowercase ASCII characters")
    if namespace == "apkvision":
        raise PatchError("replacement namespace must differ from apkvision")
    title = namespace[0].upper() + namespace[1:]
    return (
        (b"apkvision", namespace.encode("ascii")),
        (b"APKVISION", namespace.upper().encode("ascii")),
        (b"ApkVision", title.encode("ascii")),
    )


def rename_namespace_bytes(entry_name: str, data: bytes, namespace: str) -> tuple[bytes, int]:
    """Validate a legacy rename request, but never mutate binary containers.

    DEX string_ids must remain sorted by UTF-16 value, ELF strings may be
    covered by symbol hashes or used for RegisterNatives, and compiled resource
    pools may carry their own ordering/index invariants. A same-length blind
    rewrite is therefore not game-agnostically safe in any of those formats.
    """
    del entry_name
    _namespace_replacements(namespace)
    return data, 0


def _is_dex_name(name: str) -> bool:
    basename = Path(name).name
    return bool(re.fullmatch(r"classes(?:\d+)?\.dex", basename))


def _is_signature_entry(name: str) -> bool:
    upper = name.upper()
    if not upper.startswith("META-INF/"):
        return False
    leaf = upper[len("META-INF/") :]
    if "/" in leaf:
        return False
    if leaf == "MANIFEST.MF" or leaf.startswith("SIG-"):
        return True
    return leaf.endswith((".SF", ".RSA", ".DSA", ".EC"))


def _branding_asset_is_known(name: str, data: bytes) -> bool:
    lower = name.lower()
    if lower == "assets/apkvision.config":
        return True
    if lower != "assets/avconfig.json":
        return False
    digest = hashlib.sha256(data).hexdigest()
    if digest in KNOWN_AVCONFIG_SHA256:
        return True
    return data.startswith((b"\x00\x01\x00\x00", b"OTTO"))


def _local_data_offset(apk: zipfile.ZipFile, info: zipfile.ZipInfo) -> int:
    if apk.fp is None:
        raise PatchError("ZIP file is closed")
    apk.fp.seek(info.header_offset)
    header = apk.fp.read(30)
    if len(header) != 30:
        raise PatchError(f"truncated local ZIP header for {info.filename}")
    signature, *_middle, filename_len, extra_len = struct.unpack("<IHHHHHIIIHH", header)
    if signature != 0x04034B50:
        raise PatchError(f"invalid local ZIP header for {info.filename}")
    return info.header_offset + 30 + filename_len + extra_len


def _wanted_alignment(apk: zipfile.ZipFile, info: zipfile.ZipInfo) -> int:
    if info.compress_type != zipfile.ZIP_STORED or info.is_dir():
        return 1
    data_offset = _local_data_offset(apk, info)
    if info.filename.lower().endswith(".so"):
        for alignment in (16384, 4096, 4):
            if data_offset % alignment == 0:
                return alignment
        return 1
    return 4 if data_offset % 4 == 0 else 1


def _strip_extra_fields(extra: bytes, unwanted_ids: set[int]) -> bytes:
    cursor = 0
    kept = bytearray()
    while cursor + 4 <= len(extra):
        field_id, size = struct.unpack_from("<HH", extra, cursor)
        end = cursor + 4 + size
        if end > len(extra):
            return extra  # Preserve malformed/unknown data rather than truncating it.
        if field_id not in unwanted_ids:
            kept.extend(extra[cursor:end])
        cursor = end
    if cursor != len(extra):
        return extra
    return bytes(kept)


def _clone_zip_info(info: zipfile.ZipInfo, new_name: str) -> zipfile.ZipInfo:
    cloned = copy.copy(info)
    cloned.filename = new_name
    cloned.orig_filename = new_name
    cloned.extra = _strip_extra_fields(info.extra, {ZIP64_EXTRA_ID, APK_ALIGNMENT_EXTRA_ID})
    cloned.CRC = 0
    cloned.compress_size = 0
    # Keep file_size: ZipFile uses it to decide whether a ZIP64 local header is needed.
    return cloned


def _add_alignment_padding(
    output_zip: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    alignment: int,
    zip64: bool,
) -> None:
    if alignment <= 1:
        return
    if output_zip.fp is None:
        raise PatchError("output ZIP is closed")
    encoded_name, _flags = info._encodeFilenameFlags()  # type: ignore[attr-defined]
    zip64_extra_size = 20 if zip64 else 0
    base = output_zip.fp.tell() + 30 + len(encoded_name) + len(info.extra) + zip64_extra_size
    payload_size = (-(base + 4)) % alignment
    field = struct.pack("<HH", APK_ALIGNMENT_EXTRA_ID, payload_size) + b"\0" * payload_size
    if len(info.extra) + len(field) > 0xFFFF:
        raise PatchError(f"cannot align {info.filename}: ZIP extra field would be too large")
    info.extra += field


def _structural_markers(infos: Sequence[zipfile.ZipInfo]) -> list[str]:
    reasons: list[str] = []
    lower_names = {info.filename.lower() for info in infos}
    for asset in sorted(BRANDING_ASSET_NAMES):
        if asset in lower_names:
            reasons.append(f"branding asset {asset}")
    for info in infos:
        basename = Path(info.filename).name.lower()
        if basename in STANDALONE_LIBRARY_NAMES:
            reasons.append(f"injected library {info.filename}")
    return reasons


def analyze_apk(
    input_path: Path,
    output_path: Path | None = None,
    *,
    dry_run: bool = False,
    remove_branding: bool = True,
    rename_namespace: str | None = None,
    allow_no_runtime_patch: bool = False,
    replace_entries: Sequence[tuple[str, Path]] | None = None,
) -> PatchPlan:
    """Analyze and prepare modifications without writing an output APK."""
    input_path = input_path.expanduser().resolve()
    if not input_path.is_file():
        raise PatchError(f"input APK does not exist: {input_path}")
    if input_path.suffix.lower() != APK_SUFFIX:
        raise PatchError("input file must have an .apk suffix")
    if output_path is not None:
        output_path = output_path.expanduser().resolve()
        if output_path == input_path:
            raise PatchError("output path must differ from the input; originals are never overwritten")
    if rename_namespace is not None:
        _namespace_replacements(rename_namespace)

    plan = PatchPlan(input_path=input_path, output_path=output_path, dry_run=dry_run)
    with zipfile.ZipFile(input_path, "r") as apk:
        infos = apk.infolist()
        names = [info.filename for info in infos]
        duplicates = sorted(name for name, count in collections.Counter(names).items() if count > 1)
        if duplicates:
            raise PatchError("duplicate ZIP entries are not supported: " + ", ".join(duplicates[:5]))
        info_by_name = {info.filename: info for info in infos}
        for entry_name, local_path in replace_entries or ():
            if entry_name in plan.replacement_files:
                raise PatchError(f"replacement entry was specified more than once: {entry_name}")
            info = info_by_name.get(entry_name)
            if info is None:
                raise PatchError(f"replacement target is not an exact APK entry: {entry_name}")
            if info.is_dir():
                raise PatchError(f"replacement target is a directory: {entry_name}")
            if _is_signature_entry(entry_name):
                raise PatchError(f"signature entries cannot be replaced: {entry_name}")
            resolved = local_path.expanduser().resolve()
            if not resolved.is_file():
                raise PatchError(f"replacement file does not exist or is not a regular file: {resolved}")
            plan.replacement_files[entry_name] = resolved
            plan.changes.append(
                Change(
                    "replace-entry",
                    entry_name,
                    f"replace from {resolved} while retaining the entry's ZIP compression and alignment",
                )
            )
        for info in infos:
            if info.flag_bits & 0x1:
                raise PatchError(f"encrypted ZIP entry is not supported: {info.filename}")
            plan.alignments[info.filename] = _wanted_alignment(apk, info)

        plan.detection_reasons.extend(_structural_markers(infos))
        candidate_data: dict[str, bytes] = {}
        for info in infos:
            lower = info.filename.lower()
            basename = Path(lower).name
            if (
                _is_dex_name(info.filename)
                or basename == "libstub.so"
                or basename in STANDALONE_LIBRARY_NAMES
                or lower in BRANDING_ASSET_NAMES
            ):
                replacement = plan.replacement_files.get(info.filename)
                candidate_data[info.filename] = replacement.read_bytes() if replacement else apk.read(info)

        for name, data in candidate_data.items():
            lower = name.lower()
            basename = Path(lower).name
            if basename == "libstub.so" and any(marker in data for marker in STUB_MARKERS):
                plan.detection_reasons.append(f"APKVision marker in {name}")
            if _is_dex_name(name) and any(marker in data for marker in DEX_MARKERS):
                plan.detection_reasons.append(f"APKVision classes in {name}")
        plan.detection_reasons = list(dict.fromkeys(plan.detection_reasons))
        plan.detected = bool(plan.detection_reasons)
        if not plan.detected and not plan.replacement_files:
            plan.warnings.append("no recognized APKVision runtime or branding markers were found")
            return plan

        strong_marker = plan.detected
        for info in infos:
            name = info.filename
            lower = name.lower()
            basename = Path(lower).name
            if _is_signature_entry(name):
                plan.removed_entries.add(name)
                plan.signature_entries += 1
                plan.changes.append(Change("strip-signature", name, "remove stale v1 APK signature entry"))
                continue
            if not plan.detected:
                continue
            if basename == "libstub.so" or basename in STANDALONE_LIBRARY_NAMES:
                original = candidate_data[name]
                try:
                    modified, changes, targets, patches = patch_native_entry(name, original, strong_marker)
                except PatchError as exc:
                    plan.warnings.append(str(exc))
                    continue
                plan.runtime_targets += targets
                plan.runtime_patches += patches
                plan.changes.extend(changes)
                if modified != original:
                    plan.modified_entries[name] = modified
            elif _is_dex_name(name):
                original = candidate_data[name]
                try:
                    modified, changes, targets, patches = patch_dex_entry(name, original)
                except PatchError as exc:
                    plan.warnings.append(str(exc))
                    continue
                plan.runtime_targets += targets
                plan.runtime_patches += patches
                plan.changes.extend(changes)
                if modified != original:
                    plan.modified_entries[name] = modified

        runtime_safe = not plan.detected or plan.runtime_targets > 0 or allow_no_runtime_patch
        if not runtime_safe:
            plan.warnings.append(
                "recognized branding was found, but no supported runtime entry point was found; "
                "writing is blocked unless --allow-no-runtime-patch is used"
            )

        if remove_branding and plan.detected and runtime_safe:
            for info in infos:
                if info.filename.lower() not in BRANDING_ASSET_NAMES:
                    continue
                if info.filename in plan.replacement_files:
                    continue
                data = candidate_data[info.filename]
                if _branding_asset_is_known(info.filename, data):
                    if info.filename.lower() == "assets/apkvision.config":
                        if data != TRANSPARENT_PNG:
                            plan.modified_entries[info.filename] = TRANSPARENT_PNG
                            plan.changes.append(
                                Change(
                                    "replace-branding-asset",
                                    info.filename,
                                    "replace APKVision logo with a valid 1x1 transparent PNG",
                                )
                            )
                    else:
                        plan.removed_entries.add(info.filename)
                        plan.changes.append(
                            Change("remove-branding-asset", info.filename, "remove known APKVision-only font asset")
                        )
                else:
                    plan.warnings.append(f"kept unrecognized asset payload: {info.filename}")

        if rename_namespace is not None:
            plan.warnings.append(
                "namespace rewriting was requested but left unchanged: blind same-length edits can violate "
                "DEX ordering, ELF symbol/registration, compiled-resource, and load-path invariants"
            )

        resulting_names = [
            plan.renamed_entries.get(info.filename, info.filename)
            for info in infos
            if info.filename not in plan.removed_entries
        ]
        if len(resulting_names) != len(set(resulting_names)):
            raise PatchError("namespace renaming would create duplicate ZIP entries")

    return plan


def _copy_with_sha256(source: object, target: object) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    while True:
        block = source.read(1024 * 1024)  # type: ignore[attr-defined]
        if not block:
            break
        target.write(block)  # type: ignore[attr-defined]
        digest.update(block)
        total += len(block)
    return total, digest.hexdigest()


def _write_apk(plan: PatchPlan, *, force: bool, full_verify: bool) -> None:
    if plan.output_path is None:
        raise PatchError("an output path is required when not using --dry-run")
    output = plan.output_path
    if output.exists() and not force:
        raise PatchError(f"output already exists (use --force to replace it): {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    os.close(descriptor)
    temp_path = Path(temp_name)
    expected: list[tuple[str, int]] = []
    modified_output_names: dict[str, tuple[int, str]] = {}
    try:
        with zipfile.ZipFile(plan.input_path, "r") as source:
            with _zip32_write_limit():
                with zipfile.ZipFile(temp_path, "w", allowZip64=True) as destination:
                    destination.comment = source.comment
                    for info in source.infolist():
                        if info.filename in plan.removed_entries:
                            continue
                        new_name = plan.renamed_entries.get(info.filename, info.filename)
                        cloned = _clone_zip_info(info, new_name)
                        data = plan.modified_entries.get(info.filename)
                        replacement = plan.replacement_files.get(info.filename) if data is None else None
                        if data is not None:
                            resulting_size = len(data)
                        elif replacement is not None:
                            resulting_size = replacement.stat().st_size
                        else:
                            resulting_size = info.file_size
                        cloned.file_size = resulting_size
                        zip64_needed = resulting_size * 1.05 > zipfile.ZIP64_LIMIT
                        _add_alignment_padding(
                            destination,
                            cloned,
                            plan.alignments.get(info.filename, 1),
                            zip64_needed,
                        )
                        with destination.open(cloned, "w", force_zip64=zip64_needed) as target:
                            if data is not None:
                                target.write(data)
                                modified_output_names[new_name] = (
                                    len(data),
                                    hashlib.sha256(data).hexdigest(),
                                )
                            elif replacement is not None:
                                with replacement.open("rb") as replacement_stream:
                                    actual_size, digest = _copy_with_sha256(replacement_stream, target)
                                if actual_size != resulting_size:
                                    raise PatchError(
                                        f"replacement file changed while it was being read: {replacement}"
                                    )
                                modified_output_names[new_name] = (actual_size, digest)
                            else:
                                with source.open(info, "r") as original:
                                    shutil.copyfileobj(original, target, length=1024 * 1024)
                        expected.append((new_name, info.compress_type))

        input_mode = stat.S_IMODE(plan.input_path.stat().st_mode)
        os.chmod(temp_path, input_mode)
        _verify_output(temp_path, expected, modified_output_names, plan, full_verify=full_verify)
        os.replace(temp_path, output)
        plan.wrote_output = True
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        finally:
            raise


def _verify_output(
    output: Path,
    expected: Sequence[tuple[str, int]],
    modified_entries: dict[str, tuple[int, str]],
    plan: PatchPlan,
    *,
    full_verify: bool,
) -> None:
    with zipfile.ZipFile(output, "r") as apk:
        infos = apk.infolist()
        actual = [(info.filename, info.compress_type) for info in infos]
        if actual != list(expected):
            raise PatchError("output entry order or compression methods changed unexpectedly")
        if any(_is_signature_entry(info.filename) for info in infos):
            raise PatchError("a stale v1 signature entry remains in the output")
        for name, (wanted_size, wanted_digest) in modified_entries.items():
            digest = hashlib.sha256()
            actual_size = 0
            with apk.open(name, "r") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
                    actual_size += len(block)
            if actual_size != wanted_size or digest.hexdigest() != wanted_digest:
                raise PatchError(f"modified entry failed round-trip verification: {name}")
        for info in infos:
            original_name = next(
                (old for old, new in plan.renamed_entries.items() if new == info.filename),
                info.filename,
            )
            alignment = plan.alignments.get(original_name, 1)
            if alignment > 1 and _local_data_offset(apk, info) % alignment:
                raise PatchError(f"stored-entry alignment was not preserved for {info.filename}")
        if full_verify:
            bad = apk.testzip()
            if bad is not None:
                raise PatchError(f"CRC verification failed for {bad}")


def neutralize_apk(
    input_path: Path,
    output_path: Path | None = None,
    *,
    dry_run: bool = False,
    remove_branding: bool = True,
    rename_namespace: str | None = None,
    allow_no_runtime_patch: bool = False,
    replace_entries: Sequence[tuple[str, Path]] | None = None,
    force: bool = False,
    full_verify: bool = False,
) -> PatchPlan:
    if output_path is None and not dry_run:
        input_resolved = input_path.expanduser().resolve()
        output_path = input_resolved.with_name(input_resolved.stem + "-neutralized.apk")
    plan = analyze_apk(
        input_path,
        output_path,
        dry_run=dry_run,
        remove_branding=remove_branding,
        rename_namespace=rename_namespace,
        allow_no_runtime_patch=allow_no_runtime_patch,
        replace_entries=replace_entries,
    )
    if dry_run or (not plan.detected and not plan.replacement_files):
        return plan
    if plan.detected and plan.runtime_targets == 0 and not allow_no_runtime_patch:
        raise PatchError(plan.warnings[-1])
    _write_apk(plan, force=force, full_verify=full_verify)
    return plan


def format_report(plan: PatchPlan) -> str:
    lines = [
        f"Input: {plan.input_path}",
        f"Detected APKVision payload: {'yes' if plan.detected else 'no'}",
    ]
    if plan.output_path:
        lines.append(f"Output: {plan.output_path}")
    lines.append(f"Runtime targets: {plan.runtime_targets} ({plan.runtime_patches} newly patched)")
    lines.append(f"Signature entries to strip: {plan.signature_entries}")
    lines.append(f"Branding/signature entries removed: {len(plan.removed_entries)}")
    lines.append(f"Namespace entry renames: {len(plan.renamed_entries)}")
    lines.append(f"Explicit entry replacements: {len(plan.replacement_files)}")
    if plan.detection_reasons:
        lines.append("Detection:")
        lines.extend(f"  - {reason}" for reason in plan.detection_reasons)
    if plan.changes:
        lines.append("Changes:")
        for change in plan.changes:
            location = f" @ 0x{change.offset:x}" if change.offset is not None else ""
            lines.append(f"  - [{change.kind}] {change.entry}{location}: {change.detail}")
    if plan.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in plan.warnings)
    if plan.dry_run:
        lines.append("Dry run: no output was written.")
    elif plan.wrote_output:
        lines.append("Output verified and written atomically; the input was not modified.")
    return "\n".join(lines)


def _parse_replacement_spec(value: str) -> tuple[str, Path]:
    entry_name, separator, local_name = value.partition("=")
    if not separator or not entry_name or not local_name:
        raise argparse.ArgumentTypeError("expected APK_ENTRY=LOCAL_FILE")
    return entry_name, Path(local_name)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Neutralize recognized APKVision overlays without modifying the source APK."
    )
    parser.add_argument("input", type=Path, help="source APK (opened read-only)")
    parser.add_argument("-o", "--output", type=Path, help="new APK path (default: *-neutralized.apk)")
    parser.add_argument("--dry-run", action="store_true", help="analyze and report without writing")
    parser.add_argument("--force", action="store_true", help="replace an existing output file")
    parser.add_argument(
        "--replace-entry",
        action="append",
        default=[],
        type=_parse_replacement_spec,
        metavar="APK_ENTRY=LOCAL_FILE",
        help=(
            "replace an existing APK entry from a local file; repeat for multiple replacements "
            "(the original compression method and alignment are retained)"
        ),
    )
    parser.add_argument(
        "--keep-branding-assets",
        action="store_true",
        help="keep assets/AVConfig.json and assets/apkvision.config",
    )
    parser.add_argument(
        "--rename-namespace",
        metavar="NINE_CHARS",
        help=(
            "validate a legacy nine-character namespace request but leave binary strings and entry paths "
            "unchanged for ART/linker safety"
        ),
    )
    parser.add_argument(
        "--allow-no-runtime-patch",
        action="store_true",
        help="allow asset/signature-only repacking when no supported runtime entry point is found",
    )
    parser.add_argument(
        "--full-verify",
        action="store_true",
        help="read every output entry again for a complete CRC pass (slower on multi-GB APKs)",
    )
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        plan = neutralize_apk(
            args.input,
            args.output,
            dry_run=args.dry_run,
            remove_branding=not args.keep_branding_assets,
            rename_namespace=args.rename_namespace,
            allow_no_runtime_patch=args.allow_no_runtime_patch,
            replace_entries=args.replace_entry,
            force=args.force,
            full_verify=args.full_verify,
        )
    except (PatchError, zipfile.BadZipFile, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(plan.public_dict(), indent=2, sort_keys=True))
    else:
        print(format_report(plan))
    return 0 if plan.detected or plan.replacement_files else 3


if __name__ == "__main__":
    raise SystemExit(main())
