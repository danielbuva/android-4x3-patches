"""Guarded Unreal 4.27.2 camera and Android theme edits for Afterimage."""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from android4x3.errors import PatchError
from android4x3.manifest import _chunks, _string_pool

LIBRARY = "lib/arm64-v8a/libUE4.so"
RESOURCES = "resources.arsc"
REQUIRED_ENTRIES = (LIBRARY, RESOURCES)
FOCUS_ATTRIBUTE = 0x01010562  # android:defaultFocusHighlightEnabled, API 26


@dataclass(frozen=True)
class Site:
    name: str
    rva: int
    offset: int
    before: bytes
    original: bytes
    patched: bytes
    after: bytes


@dataclass(frozen=True)
class NativeSpec:
    size: int
    original_sha256: str
    patched_sha256: str
    sites: tuple[Site, ...]


SPEC = NativeSpec(
    109920816,
    "4c718bb89b763d080f60284f1675ca73a7ce323e27e4241792c515552de833f9",
    "0f70aa2409b5171583a59438f85f7b4a105dd77ab067038c7f0efb104e142d25",
    (
        Site("CameraComponent full viewport", 0x4A551B0, 0x4A511B0,
             bytes.fromhex("601a00bd800a42bd603200bd88324839"),
             bytes.fromhex("09010033"), bytes.fromhex("29791f12"),
             bytes.fromhex("69d2003929791e128832483908011f12")),
        Site("Projection preserves horizontal field of view", 0x4A598D0, 0x4A558D0,
             bytes.fromhex("0a00261e4401497a64d941fa0419417a"),
             bytes.fromhex("210a0054"), bytes.fromhex("1f2003d5"),
             bytes.fromhex("4001221e2101221ee94d82526950a772")),
    ),
)


def native_state(data: bytes, spec: NativeSpec | None = None) -> list[str]:
    spec = SPEC if spec is None else spec
    if len(data) != spec.size or data[:7] != b"\x7fELF\x02\x01\x01":
        raise PatchError("Afterimage: unknown native size or ELF format")
    if struct.unpack_from("<H", data, 18)[0] != 183:
        raise PatchError("Afterimage: expected AArch64")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phsize, phcount = struct.unpack_from("<HH", data, 54)
    if phsize != 56 or phoff + phsize * phcount > len(data):
        raise PatchError("Afterimage: invalid ELF segment table")
    segments = [struct.unpack_from("<IIQQQQQQ", data, phoff + i * phsize)
                for i in range(phcount)]
    canonical = bytearray(data)
    states = []
    for site in spec.sites:
        mappings = [s for s in segments if s[0] == 1 and s[1] & 1
                    and s[3] <= site.rva and site.rva + len(site.original) <= s[3] + s[5]
                    and s[2] + site.rva - s[3] == site.offset]
        if len(mappings) != 1:
            raise PatchError(f"Afterimage: invalid executable mapping for {site.name}")
        actual = data[site.offset:site.offset + len(site.original)]
        if actual not in (site.original, site.patched):
            raise PatchError(f"Afterimage: changed instruction at {site.name}")
        context = site.before + actual + site.after
        if (data.count(context) != 1 or
                data.find(context) != site.offset - len(site.before)):
            raise PatchError(f"Afterimage: missing or ambiguous context for {site.name}")
        canonical[site.offset:site.offset + len(site.original)] = site.original
        states.append("patched" if actual == site.patched else "original")
    if hashlib.sha256(canonical).hexdigest() != spec.original_sha256:
        raise PatchError("Afterimage: unrecognized native revision or unrelated native modification")
    if all(s == "patched" for s in states) and hashlib.sha256(data).hexdigest() != spec.patched_sha256:
        raise PatchError("Afterimage: final native hash mismatch")
    return states


def patch_native(data: bytes, spec: NativeSpec | None = None) -> bytes:
    spec = SPEC if spec is None else spec
    native_state(data, spec)
    result = bytearray(data)
    for site in spec.sites:
        result[site.offset:site.offset + len(site.original)] = site.patched
    native_state(bytes(result), spec)
    return bytes(result)


def focus_theme(data: bytes) -> tuple[str, bytes]:
    """Add one false attribute to the named base theme, preserving other resources.

    Accept dense 32-bit entry tables only. Sparse/offset16/compact entries and
    unfamiliar theme definitions fail closed instead of attempting a rebuild.
    """
    if len(data) < 12 or struct.unpack_from("<HHI", data) != (2, 12, len(data)):
        raise PatchError("Afterimage: malformed resource table")
    targets = []
    for typ, package, package_size in _chunks(data, 12, len(data)):
        if typ != 0x200:
            continue
        header = struct.unpack_from("<H", data, package + 2)[0]
        if header < 288:
            raise PatchError("Afterimage: unsupported resource package header")
        name = data[package + 12:package + 268].decode("utf-16-le").split("\0", 1)[0]
        if name != "com.aurogon.Afterimage":
            continue
        pools = [struct.unpack_from("<I", data, package + n)[0] for n in (268, 276)]
        strings = []
        for relative in pools:
            p = package + relative
            if not package + header <= p < package + package_size - 8:
                raise PatchError("Afterimage: invalid resource string pool")
            strings.append(_string_pool(data, p, struct.unpack_from("<I", data, p + 4)[0]))
        types, keys = strings
        for kind, chunk, chunk_size in _chunks(data, package + header, package + package_size):
            if kind != 0x201:
                continue
            type_id, flags, _, count, start = struct.unpack_from("<BBHII", data, chunk + 8)
            if not 0 < type_id <= len(types):
                raise PatchError("Afterimage: invalid resource type")
            if types[type_id - 1] != "style":
                continue
            h = struct.unpack_from("<H", data, chunk + 2)[0]
            if flags or h < 24 or h + count * 4 > start or start > chunk_size:
                raise PatchError("Afterimage: unsupported style entry table")
            offsets = struct.unpack_from(f"<{count}I", data, chunk + h)
            for index, relative in enumerate(offsets):
                if relative == 0xFFFFFFFF:
                    continue
                entry = chunk + start + relative
                if not chunk + start <= entry <= chunk + chunk_size - 8:
                    raise PatchError("Afterimage: style entry outside chunk")
                size, entry_flags, key = struct.unpack_from("<HHI", data, entry)
                if key >= len(keys):
                    raise PatchError("Afterimage: invalid style key")
                if keys[key] != "UE4BaseTheme":
                    continue
                if size != 16 or not entry_flags & 1 or entry_flags & ~3:
                    raise PatchError("Afterimage: unexpected base theme format")
                parent, item_count = struct.unpack_from("<II", data, entry + 8)
                if parent != 0x0103000A or item_count > 1:
                    raise PatchError("Afterimage: unfamiliar base theme definition")
                end = entry + 16 + item_count * 12
                if end > chunk + chunk_size or any(0 <= r < 0xFFFFFFFF and
                        relative < r < relative + 16 + item_count * 12 for r in offsets):
                    raise PatchError("Afterimage: overlapping theme entries")
                state = "original"
                if item_count:
                    if data[entry + 16:end] != struct.pack("<IHBBI", FOCUS_ATTRIBUTE, 8, 0, 0x12, 0):
                        raise PatchError("Afterimage: unfamiliar focus attribute")
                    state = "patched"
                targets.append((state, package, chunk, h, offsets, entry, pools))
    if len(targets) != 1:
        raise PatchError("Afterimage: expected one unique UE4BaseTheme")
    state, package, chunk, h, offsets, entry, pools = targets[0]
    if state == "patched":
        return state, data
    if any(package + relative >= chunk for relative in pools):
        raise PatchError("Afterimage: unsupported resource pool placement")
    result = bytearray(data)
    insert = entry + 16
    for root in (0, package, chunk):
        struct.pack_into("<I", result, root + 4, struct.unpack_from("<I", data, root + 4)[0] + 12)
    start = struct.unpack_from("<I", data, chunk + 16)[0]
    for i, relative in enumerate(offsets):
        if relative != 0xFFFFFFFF and chunk + start + relative >= insert:
            struct.pack_into("<I", result, chunk + h + i * 4, relative + 12)
    struct.pack_into("<I", result, entry + 12, 1)
    result[insert:insert] = struct.pack("<IHBBI", FOCUS_ATTRIBUTE, 8, 0, 0x12, 0)
    if focus_theme(bytes(result))[0] != "patched":
        raise PatchError("Afterimage: theme postcondition failed")
    return state, bytes(result)


def probe(extracted: dict[str, Path]) -> dict:
    try:
        native = native_state(extracted[LIBRARY].read_bytes())
        focus, _ = focus_theme(extracted[RESOURCES].read_bytes())
        states = native + [focus]
        return {"state": "patched" if all(s == "patched" for s in states) else "original",
                "targets": [{"name": s.name, "state": state} for s, state in zip(SPEC.sites, native)]
                           + [{"name": "Android focus border disabled", "state": focus}]}
    except (PatchError, KeyError, OSError, ValueError, IndexError, struct.error) as exc:
        return {"state": "unsupported", "detail": str(exc), "targets": []}


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    initial = probe(extracted)
    if initial["state"] == "unsupported":
        raise PatchError(initial["detail"])
    replacements = {}
    for entry, transform in ((LIBRARY, patch_native), (RESOURCES, lambda data: focus_theme(data)[1])):
        before = extracted[entry].read_bytes()
        after = transform(before)
        if after != before:
            path = output_dir.joinpath(*entry.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(after)
            replacements[entry] = path
    if probe({**extracted, **replacements})["state"] != "patched":
        raise PatchError("Afterimage: combined postcondition failed")
    return replacements
