"""Exact-build native 4:3 patch for AM2R 1.5.2.

AM2R's GameMaker YYC build compiles its widescreen option into each ABI's
``libyoyo.so``.  The tested build expands the logical 320x240 view by 106
columns when that option is enabled.  This module forces the saved option to
load as false and prevents the display menu from turning it back on.

The edits are fixed native-code locations, so every location is constrained by
the complete original or patched library hash, ELF architecture, executable
load mapping, and exact instruction bytes.  Unknown native builds fail closed.
"""

from __future__ import annotations

import hashlib
import io
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class PatchSite:
    name: str
    offset: int
    virtual_address: int
    original: bytes
    patched: bytes


@dataclass(frozen=True)
class LibrarySpec:
    abi: str
    entry: str
    machine: int
    size: int
    original_sha256: str
    patched_sha256: str
    sites: tuple[PatchSite, ...]


_LIBRARIES = (
    LibrarySpec(
        abi="armeabi",
        entry="lib/armeabi/libyoyo.so",
        machine=40,  # EM_ARM
        size=26_934_232,
        original_sha256="5454cd56950db215d9ebd8bb98f1cb74fb43fcb2ad489cf404c81ba7b3f4bb6b",
        patched_sha256="7df65fa7bbd0de501751ace839a9732865f86ec0bb596af6648cfba6933ed7d5",
        sites=(
            PatchSite(
                "load Widescreen low word as zero",
                0x70D5B4,
                0x70D5B4,
                bytes.fromhex("00 60 a0 e1"),  # mov r6, r0
                bytes.fromhex("00 60 a0 e3"),  # mov r6, #0
            ),
            PatchSite(
                "load Widescreen high word as zero",
                0x70D5B8,
                0x70D5B8,
                bytes.fromhex("01 50 a0 e1"),  # mov r5, r1
                bytes.fromhex("00 50 a0 e3"),  # mov r5, #0
            ),
            PatchSite(
                "keep display-menu Widescreen toggle false",
                0xE00E8C,
                0xE00E8C,
                bytes.fromhex("03 12 81 e3"),
                bytes.fromhex("00 10 a0 e3"),  # mov r1, #0
            ),
        ),
    ),
    LibrarySpec(
        abi="armeabi-v7a",
        entry="lib/armeabi-v7a/libyoyo.so",
        machine=40,  # EM_ARM
        size=24_829_588,
        original_sha256="6778842c0750eb5efd64c8e891ff13769b936299a1757195e568be082d1f5039",
        patched_sha256="f220dd1182750f4141d96c6a6aa7386ee17e4d5504119ab8dc4c96e6386b979c",
        sites=(
            PatchSite(
                "load Widescreen low word as zero",
                0x6AEDFC,
                0x6AEDFC,
                bytes.fromhex("00 40 a0 e1"),  # mov r4, r0
                bytes.fromhex("00 40 a0 e3"),  # mov r4, #0
            ),
            PatchSite(
                "load Widescreen high word as zero",
                0x6AEE00,
                0x6AEE00,
                bytes.fromhex("01 50 a0 e1"),  # mov r5, r1
                bytes.fromhex("00 50 a0 e3"),  # mov r5, #0
            ),
            PatchSite(
                "keep display-menu Widescreen toggle false",
                0xD21128,
                0xD21128,
                bytes.fromhex("f0 1f 43 e3"),  # movt r1, #0x3ff0
                bytes.fromhex("00 10 40 e3"),  # movt r1, #0
            ),
        ),
    ),
    LibrarySpec(
        abi="mips",
        entry="lib/mips/libyoyo.so",
        machine=8,  # EM_MIPS
        size=29_974_816,
        original_sha256="c3d47c1b0b30c625000144a0dc138585035d484da6d3f5476dda37d7a8f93fc6",
        patched_sha256="29bf8fb3deebf9fdfd86ba02fbfcbab53f8fc9f631e7dd88b3eadb5e3f505df7",
        sites=(
            PatchSite(
                "load Widescreen result as zero",
                0x72ACF4,
                0x72ACF4,
                bytes.fromhex("06 05 20 46"),  # mov.d f20, f0
                bytes.fromhex("01 05 20 46"),  # sub.d f20, f0, f0
            ),
            PatchSite(
                "keep display-menu Widescreen toggle false",
                0xE346EC,
                0xE346EC,
                bytes.fromhex("f0 3f 01 3c"),  # lui $at, 0x3ff0
                bytes.fromhex("00 00 01 3c"),  # lui $at, 0
            ),
        ),
    ),
    LibrarySpec(
        abi="x86",
        entry="lib/x86/libyoyo.so",
        machine=3,  # EM_386
        size=27_291_080,
        original_sha256="6d3bed090b63a55f7ebef4a45526038d163ca6330181a552235880c5bced30da",
        patched_sha256="1e24b8c58c45f91d32caefc47ecea441464e5e7dc3cc44eb655f05402d7415bf",
        sites=(
            PatchSite(
                "load Widescreen result as zero",
                0x6C6E42,
                0x6C6E42,
                bytes.fromhex("f2 0f 10 84 24 10 02 00 00"),
                bytes.fromhex("0f 57 c0 90 90 90 90 90 90"),  # xorps xmm0,xmm0; nops
            ),
            PatchSite(
                "keep display-menu Widescreen toggle false",
                0xD54802,
                0xD54802,
                bytes.fromhex("c7 40 04 00 00 f0 3f"),
                bytes.fromhex("c7 40 04 00 00 00 00"),
            ),
        ),
    ),
)

# AM2R packages can legitimately contain only the ABI needed by their target
# device. The CLI discovers every lib/*/libyoyo.so through config globs; probe()
# then requires a nonempty subset and validates every implementation present.
SPLASH_ENTRY = "assets/splash.png"
REQUIRED_ENTRIES: tuple[str, ...] = (SPLASH_ENTRY,)


def _is_yoyo_library_entry(entry: str) -> bool:
    parts = entry.split("/")
    return len(parts) == 3 and parts[0] == "lib" and parts[2] == "libyoyo.so"


def _sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest()


def _elf_error(data: bytes | bytearray, spec: LibrarySpec) -> str | None:
    """Validate ELF identity and map every guarded file offset to its tested VA."""

    if len(data) < 52 or bytes(data[:4]) != b"\x7fELF":
        return "not an ELF binary"
    if bytes(data[4:6]) != b"\x01\x01":
        return "not a 32-bit little-endian ELF"
    if struct.unpack_from("<H", data, 16)[0] != 3:
        return "not an ELF shared object"
    if struct.unpack_from("<H", data, 18)[0] != spec.machine:
        return f"ELF machine does not match {spec.abi}"

    program_offset = struct.unpack_from("<I", data, 28)[0]
    program_size = struct.unpack_from("<H", data, 42)[0]
    program_count = struct.unpack_from("<H", data, 44)[0]
    if program_size < 32 or program_count == 0:
        return "ELF has no usable program-header table"
    if program_offset + program_size * program_count > len(data):
        return "ELF program-header table is truncated"

    executable_loads: list[tuple[int, int, int]] = []
    for index in range(program_count):
        offset = program_offset + index * program_size
        (
            segment_type,
            file_offset,
            virtual_address,
            _physical_address,
            file_size,
            _memory_size,
            flags,
            _alignment,
        ) = struct.unpack_from("<IIIIIIII", data, offset)
        if segment_type == 1 and flags & 1:  # PT_LOAD and PF_X
            executable_loads.append((file_offset, virtual_address, file_size))

    for site in spec.sites:
        end = site.offset + len(site.original)
        mappings = [
            segment
            for segment in executable_loads
            if segment[0] <= site.offset and end <= segment[0] + segment[2]
        ]
        if len(mappings) != 1:
            return f"{site.name}: patch site is not in one executable PT_LOAD segment"
        file_offset, virtual_address, _file_size = mappings[0]
        actual_va = virtual_address + site.offset - file_offset
        if actual_va != site.virtual_address:
            return (
                f"{site.name}: ELF mapping changed "
                f"(expected VA 0x{site.virtual_address:x}, got 0x{actual_va:x})"
            )
    return None


def _site_state(data: bytes | bytearray, site: PatchSite) -> str:
    actual = bytes(data[site.offset : site.offset + len(site.original)])
    if actual == site.original:
        return "original"
    if actual == site.patched:
        return "patched"
    return "unsupported"


def _probe_data(data: bytes | bytearray, spec: LibrarySpec) -> dict[str, Any]:
    digest = _sha256(data)
    result: dict[str, Any] = {
        "name": spec.entry,
        "entry": spec.entry,
        "abi": spec.abi,
        "sha256": digest,
    }
    if len(data) != spec.size:
        result.update(
            state="unsupported",
            reason=f"library size is {len(data)}, expected {spec.size}",
        )
        return result

    elf_error = _elf_error(data, spec)
    if elf_error is not None:
        result.update(state="unsupported", reason=elf_error)
        return result

    if digest == spec.original_sha256:
        expected_state = "original"
    elif digest == spec.patched_sha256:
        expected_state = "patched"
    else:
        result.update(
            state="unsupported",
            reason="SHA-256 does not match the tested original or patched native build",
        )
        return result

    targets = [
        {
            "name": site.name,
            "state": _site_state(data, site),
            "offset": site.offset,
            "virtual_address": site.virtual_address,
        }
        for site in spec.sites
    ]
    result["targets"] = targets
    if any(target["state"] != expected_state for target in targets):
        result.update(
            state="unsupported",
            reason="library hash and guarded instruction state disagree",
        )
    else:
        result["state"] = expected_state
    return result


def _probe_library(path: Path, spec: LibrarySpec) -> dict[str, Any]:
    try:
        return _probe_data(path.read_bytes(), spec)
    except OSError as exc:
        return {
            "name": spec.entry,
            "entry": spec.entry,
            "abi": spec.abi,
            "state": "unsupported",
            "reason": f"cannot read required library: {exc}",
        }


def _splash_state(data: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": "landscape startup image",
        "entry": SPLASH_ENTRY,
    }
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            image_format = image.format
    except Exception as exc:
        result.update(state="unsupported", reason=f"startup image is not readable: {exc}")
        return result
    result.update(width=width, height=height)
    if image_format != "PNG" or width <= 0 or height <= 0:
        result.update(state="unsupported", reason="startup image is not a valid PNG")
    elif width * 3 == height * 4:
        result["state"] = "patched"
    elif width * 3 > height * 4:
        result["state"] = "original"
    else:
        result.update(
            state="unsupported",
            reason="startup image is portrait or narrower than 4:3",
        )
    return result


def _crop_splash_to_4x3(data: bytes) -> bytes:
    before = _splash_state(data)
    if before["state"] != "original":
        raise RuntimeError(
            f"{SPLASH_ENTRY}: expected a landscape startup image, got {before['state']}"
        )
    with Image.open(io.BytesIO(data)) as source:
        source.load()
        target_width = source.height * 4 // 3
        if target_width * 3 != source.height * 4:
            raise RuntimeError(
                f"{SPLASH_ENTRY}: image height cannot produce an exact integer 4:3 crop"
            )
        left = (source.width - target_width) // 2
        cropped = source.crop((left, 0, left + target_width, source.height))
        output = io.BytesIO()
        cropped.save(output, format="PNG", optimize=False)
    result = output.getvalue()
    after = _splash_state(result)
    if after["state"] != "patched":
        raise RuntimeError(f"{SPLASH_ENTRY}: 4:3 startup-image postcondition failed")
    return result


def _overall(results: list[dict[str, Any]]) -> str:
    states = {result["state"] for result in results}
    if "ambiguous" in states:
        return "ambiguous"
    if "unsupported" in states:
        return "unsupported"
    if states == {"patched"}:
        return "patched"
    return "original"


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Classify every present audited ABI without requiring absent ABIs."""

    specs = {spec.entry: spec for spec in _LIBRARIES}
    present = sorted(
        (entry, Path(path))
        for entry, path in extracted.items()
        if _is_yoyo_library_entry(entry)
    )
    results: list[dict[str, Any]] = []
    if SPLASH_ENTRY in REQUIRED_ENTRIES:
        splash = extracted.get(SPLASH_ENTRY)
        if splash is None or not Path(splash).is_file():
            results.append(
                {
                    "name": "landscape startup image",
                    "entry": SPLASH_ENTRY,
                    "state": "unsupported",
                    "reason": "required startup image is missing",
                }
            )
        else:
            try:
                results.append(_splash_state(Path(splash).read_bytes()))
            except OSError as exc:
                results.append(
                    {
                        "name": "landscape startup image",
                        "entry": SPLASH_ENTRY,
                        "state": "unsupported",
                        "reason": f"cannot read startup image: {exc}",
                    }
                )
    if not present:
        return {
            "state": "unsupported",
            "targets": [],
            "detail": "AM2R contains no discoverable lib/<abi>/libyoyo.so implementation",
        }

    for entry, source in present:
        spec = specs.get(entry)
        if spec is None:
            results.append(
                {
                    "name": entry,
                    "entry": entry,
                    "abi": entry.split("/")[1],
                    "state": "unsupported",
                    "reason": "present libyoyo.so ABI is not an audited AM2R implementation",
                }
            )
        elif not source.is_file():
            results.append(
                {
                    "name": entry,
                    "entry": entry,
                    "abi": spec.abi,
                    "state": "unsupported",
                    "reason": "discovered native library is missing or not a regular file",
                }
            )
        else:
            results.append(_probe_library(source, spec))
    state = _overall(results)
    report: dict[str, Any] = {"state": state, "targets": results}
    if state == "unsupported":
        report["detail"] = (
            "every AM2R libyoyo.so present must match an audited 1.5.2 ABI implementation"
        )
    return report


def _patch_data(data: bytes, spec: LibrarySpec) -> bytes:
    before = _probe_data(data, spec)
    if before["state"] != "original":
        raise RuntimeError(
            f"{spec.entry}: expected the guarded original library, got {before['state']}"
        )

    patched = bytearray(data)
    for site in spec.sites:
        end = site.offset + len(site.original)
        if bytes(patched[site.offset:end]) != site.original:
            raise RuntimeError(f"{spec.entry}: {site.name} changed during patching")
        if len(site.original) != len(site.patched):
            raise RuntimeError(f"{spec.entry}: {site.name} is not an in-place edit")
        patched[site.offset:end] = site.patched

    after = _probe_data(patched, spec)
    if after["state"] != "patched":
        raise RuntimeError(
            f"{spec.entry}: native postcondition failed ({after.get('reason', after['state'])})"
        )
    return bytes(patched)


def _destination(output_dir: Path, entry: str) -> Path:
    destination = Path(output_dir).joinpath(*entry.split("/"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Patch every recognized ABI present and verify that same subset."""

    status = probe(extracted)
    if status["state"] in {"unsupported", "ambiguous"}:
        raise RuntimeError(f"AM2R native targets are {status['state']}; refusing to guess")
    if status["state"] == "patched":
        return {}

    specs = {spec.entry: spec for spec in _LIBRARIES}
    states = {target["entry"]: target["state"] for target in status["targets"]}
    replacements: dict[str, Path] = {}
    try:
        if states.get(SPLASH_ENTRY) == "original":
            destination = _destination(Path(output_dir), SPLASH_ENTRY)
            destination.write_bytes(
                _crop_splash_to_4x3(Path(extracted[SPLASH_ENTRY]).read_bytes())
            )
            replacements[SPLASH_ENTRY] = destination

        for entry, state in states.items():
            if entry == SPLASH_ENTRY or state != "original":
                continue
            spec = specs[entry]
            source = Path(extracted[entry])
            destination = _destination(Path(output_dir), entry)
            destination.write_bytes(_patch_data(source.read_bytes(), spec))
            replacements[entry] = destination

        combined = dict(extracted)
        combined.update(replacements)
        verified = probe(combined)
        if verified["state"] != "patched":
            raise RuntimeError(
                f"AM2R combined native postcondition failed: {verified['state']}"
            )
        return replacements
    except Exception:
        for destination in replacements.values():
            destination.unlink(missing_ok=True)
        raise
