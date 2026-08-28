"""Guarded true-4:3 display selection for Huntdown's arm64 build.

The game already has a resolution-independent 4:3 renderer.  Two guarded
branches bypass the optional ``force169`` preference, and story videos switch
from letterboxing to a proportional vertical fit (center side crop).

Recognized analytics and distributor-injected files are cleaned opportunistically.
Those source-specific targets are never required for 4:3 compatibility: absent or
unknown files are preserved silently. Purchases, cloud saves, authentication,
achievements, and Play Games are deliberately outside this patch.
"""

from __future__ import annotations

import hashlib
import importlib.util
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LIBRARY_ENTRY = "lib/arm64-v8a/libil2cpp.so"
DEX_ENTRY = "classes3.dex"
INJECTED_DATA_ENTRY = "assets/data0"
# Only the renderer library is a core patch input. The two source-specific
# entries are extraction hints in config.json and may legitimately be absent.
REQUIRED_ENTRIES = (LIBRARY_ENTRY,)

_FALSE = bytes.fromhex("00 00 80 52 c0 03 5f d6")
_EMPTY_ZIP = bytes.fromhex("504b0506000000000000000000000000000000000000")


class PatchError(RuntimeError):
    """The supplied entries do not match the audited Huntdown build."""


@dataclass(frozen=True)
class NativeSite:
    name: str
    scope: str
    rva: int
    offset: int
    before: bytes
    original: bytes
    patched: bytes
    after: bytes
    signature_sha256: str


@dataclass(frozen=True)
class NativeSpec:
    entry: str
    size: int
    original_sha256: str
    cleanup_sha256: str
    patched_sha256: str
    sites: tuple[NativeSite, ...]


@dataclass(frozen=True)
class DexSpec:
    entry: str
    size: int
    class_descriptor: str
    method_name: str
    descriptor: str
    code_offset: int
    instruction_offset: int
    original: bytes
    patched: bytes
    original_instruction_sha256: str
    original_sha256: str
    patched_sha256: str

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.class_descriptor, self.method_name, self.descriptor


@dataclass(frozen=True)
class DataSpec:
    entry: str
    original_size: int
    original_sha256: str
    patched: bytes
    patched_sha256: str


def _site(
    name: str,
    scope: str,
    rva: int,
    before: str,
    original: str,
    patched: bytes | str,
    after: str,
    signature_sha256: str,
) -> NativeSite:
    return NativeSite(
        name=name,
        scope=scope,
        rva=rva,
        offset=rva - 0x4000,
        before=bytes.fromhex(before),
        original=bytes.fromhex(original),
        patched=bytes.fromhex(patched) if isinstance(patched, str) else patched,
        after=bytes.fromhex(after),
        signature_sha256=signature_sha256,
    )


_NATIVE_SITES = (
    _site(
        "Analytics.<LoginWith>d__13.MoveNext",
        "analytics",
        0x19C38C0,
        "e1031faafe57c2a826ae7514c0035fd6",
        "ff4303d1fd7b07a9",
        _FALSE,
        "fc6f08a9fa6709a9f85f0aa9f6570ba9",
        "4a54aea6a26b999f699104df4f7f94fa4a004d8bc6694a12b2500bf0a4712039",
    ),
    _site(
        "Analytics.<LoginWithXbox>d__14.MoveNext",
        "analytics",
        0x19C424C,
        "4611fc97000c40f9c0035fd6c0035fd6",
        "ff8301d1fe1b00f9",
        _FALSE,
        "f65704a9f44f05a9d42b01d0f30300aa",
        "18abb3342c5c69f8351027b701e40a0fc47019a461671ed61d7e5776ea372e40",
    ),
    _site(
        "Analytics.<SendToServer>d__21.MoveNext",
        "analytics",
        0x19C4698,
        "1f0d003141000054dd000014c0035fd6",
        "ff0301d1fe0302a9",
        _FALSE,
        "f44f03a9d42b01d0f30300aa88464639",
        "c46374c7d01a12d564f7605e9a3d3a729cecdf507e3a7aee86222e00409ae697",
    ),
    _site(
        "Gfx.Init ignore force169",
        "4:3 gameplay and menus",
        0x1BDD3BC,
        "604200b9e1031faae00308aa501f6d94",
        "20020036",
        "11000014",
        "e0031faa25a46c94682e40b909591753",
        "9a8e87b34d38bc55ec8ec649339a21862e4031b14901c5a1fff95fdc09d2ca81",
    ),
    _site(
        "Gfx.GetViewSize ignore force169",
        "4:3 gameplay and menus",
        0x1BDE19C,
        "98b2891a7f02086b77b2881ad81b6d94",
        "40040036",
        "22000014",
        "2811915229c99a52c00240f90811b172",
        "99a973c949bc8aa33ebfab2a784804eaaf37bdf981fc9140f925aeef327099f6",
    ),
    _site(
        "Vignettes.Init video FitVertically",
        "4:3 intro and story videos",
        0x1CA4580,
        "084540b9a9008052e2031faa1f010071",
        "48008052",
        "28008052",
        "21c1881a73157594608e40f9c00500b4",
        "90f83ada302489ef1f26e44f074756797dd1580e30bbd666419c3f17b481867c",
    ),
)

_NATIVE_SPEC = NativeSpec(
    entry=LIBRARY_ENTRY,
    size=66_267_936,
    original_sha256="df7ef60193104e4e6f940741569ed398c741d3ed9247b2cf4456db49bc264793",
    cleanup_sha256="c2b11060ff373173062fccde5efbb3832efd1acebaabb64347c655142e3e18f6",
    patched_sha256="2bb8decd8cfa5302ac0be008189f49cff53ce9181efee33302c68ce503546317",
    sites=_NATIVE_SITES,
)
_CLEANUP_ONLY_SHA256 = _NATIVE_SPEC.cleanup_sha256

_DEX_ORIGINAL = bytes.fromhex(
    "1200123135101b007120010320000a0138011200122133100c007110000302000a01"
    "390109007120020320002804712002032000d800000128e50e00"
)
_DEX_PATCHED = b"\x0e\x00" + b"\x00" * (len(_DEX_ORIGINAL) - 2)
_DEX_SPEC = DexSpec(
    entry=DEX_ENTRY,
    size=104_820,
    class_descriptor="Lcom/save;",
    method_name="a",
    descriptor="(Landroid/content/Context;)V",
    code_offset=99_592,
    instruction_offset=99_608,
    original=_DEX_ORIGINAL,
    patched=_DEX_PATCHED,
    original_instruction_sha256="2960f1b2cd68efa91a5407c75550a593fb2129837b395d5c83c9f1af12c484ec",
    original_sha256="3f7ebc862a4ae01f87e3ae8f433270e69863f09651db10d6dd043a538f9490a9",
    patched_sha256="66d26323fa5fdd74fd6f1c4c4a987c41c7f58a2bc00110e74e334bdbfb2c9fe5",
)

_DATA_SPEC = DataSpec(
    entry=INJECTED_DATA_ENTRY,
    original_size=989,
    original_sha256="58f4ae3d53922a6b82b3794eafcb273065dadcac815635abd8e50e5a9fc4e3f3",
    patched=_EMPTY_ZIP,
    patched_sha256="8739c76e681f900923b900c9df0ef75cf421d39cabb54650c4b9ad19b6a76d85",
)


def _sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest()


def _overall(states: list[str]) -> str:
    if "ambiguous" in states:
        return "ambiguous"
    if "unsupported" in states:
        return "unsupported"
    return "patched" if states and set(states) == {"patched"} else "original"


def _find_all(data: bytes | bytearray, needle: bytes) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while True:
        offset = data.find(needle, cursor)
        if offset < 0:
            return offsets
        offsets.append(offset)
        cursor = offset + 1


def _elf_error(data: bytes | bytearray, spec: NativeSpec) -> str | None:
    if len(data) < 64 or bytes(data[:6]) != b"\x7fELF\x02\x01":
        return "not a 64-bit little-endian ELF"
    header = struct.unpack_from("<HHIQQQIHHHHHH", data, 16)
    if header[0] != 3 or header[1] != 183:
        return "ELF type or machine is not ARM64 ET_DYN"
    phoff, phentsize, phnum = header[4], header[8], header[9]
    if phentsize < 56 or not phnum or phoff + phentsize * phnum > len(data):
        return "ELF program-header table is invalid"
    loads: list[tuple[int, int, int]] = []
    for index in range(phnum):
        fields = struct.unpack_from("<IIQQQQQQ", data, phoff + index * phentsize)
        p_type, flags, file_offset, vaddr, _paddr, file_size, _mem_size, _align = fields
        if p_type == 1 and flags & 1:
            loads.append((file_offset, vaddr, file_size))
    # The audited size and complete-file hashes remain useful fingerprints, but
    # unrelated vendor/source changes must not reject a build. Each core edit is
    # instead guarded by its full instruction context and ELF mapping.
    for site in _four_three_sites(spec):
        end = site.offset + len(site.original)
        mappings = [
            item
            for item in loads
            if item[0] <= site.offset and end <= item[0] + item[2]
        ]
        if len(mappings) != 1:
            return f"{site.name}: target is not in one executable PT_LOAD"
        file_offset, vaddr, _size = mappings[0]
        if vaddr + site.offset - file_offset != site.rva:
            return f"{site.name}: RVA-to-file mapping changed"
    return None


def _native_site_state(data: bytes | bytearray, site: NativeSite) -> tuple[str, str | None]:
    if len(site.original) != len(site.patched):
        return "unsupported", "replacement is not an in-place edit"
    original_signature = site.before + site.original + site.after
    patched_signature = site.before + site.patched + site.after
    if _sha256(original_signature) != site.signature_sha256:
        return "unsupported", "audited signature metadata disagrees"
    original = _find_all(data, original_signature)
    patched = _find_all(data, patched_signature)
    expected = site.offset - len(site.before)
    if len(original) + len(patched) != 1:
        state = "ambiguous" if original or patched else "unsupported"
        return state, f"complete signature count is {len(original) + len(patched)}, expected 1"
    actual = original[0] if original else patched[0]
    if actual != expected:
        return "unsupported", f"complete signature moved to 0x{actual:x}"
    return ("original" if original else "patched"), None


def _native_probe_data(
    data: bytes | bytearray, spec: NativeSpec | None = None
) -> dict[str, Any]:
    spec = _NATIVE_SPEC if spec is None else spec
    result: dict[str, Any] = {
        "name": "Huntdown arm64 4:3 renderer",
        "entry": spec.entry,
        "sha256": _sha256(data),
    }
    error = _elf_error(data, spec)
    if error is not None:
        result.update(state="unsupported", reason=error, targets=[])
        return result
    targets: list[dict[str, Any]] = []
    states: list[str] = []
    for site in _four_three_sites(spec):
        state, reason = _native_site_state(data, site)
        row: dict[str, Any] = {
            "name": site.name,
            "scope": site.scope,
            "state": state,
            "offset": site.offset,
            "rva": site.rva,
        }
        if reason:
            row["reason"] = reason
        targets.append(row)
        states.append(state)
    result["targets"] = targets
    if "ambiguous" in states:
        result.update(state="ambiguous", reason="a native signature is not unique")
        return result
    if "unsupported" in states:
        result.update(state="unsupported", reason="a guarded native signature changed")
        return result
    state = "patched" if states and set(states) == {"patched"} else "original"
    result["state"] = state
    return result


def _patch_native_data(data: bytes, spec: NativeSpec | None = None) -> bytes:
    spec = _NATIVE_SPEC if spec is None else spec
    before = _native_probe_data(data, spec)
    if before["state"] not in ("original", "patched"):
        raise PatchError(f"native targets are {before['state']}")
    mutable = bytearray(data)
    for site in _four_three_sites(spec):
        state, _reason = _native_site_state(mutable, site)
        if state == "original":
            mutable[site.offset : site.offset + len(site.original)] = site.patched
        elif state != "patched":
            raise PatchError(f"{site.name}: state changed after probing")
    # Optional cleanup is best effort. An unknown or ambiguous analytics site
    # belongs to the user-supplied build and is intentionally left byte-for-byte.
    for site in _cleanup_sites(spec):
        state, _reason = _native_site_state(mutable, site)
        if state == "original":
            mutable[site.offset : site.offset + len(site.original)] = site.patched
    result = bytes(mutable)
    after = _native_probe_data(result, spec)
    if after["state"] != "patched":
        raise PatchError(f"native postcondition failed: {after['state']}")
    return result


def _cleanup_sites(spec: NativeSpec) -> tuple[NativeSite, ...]:
    return tuple(site for site in spec.sites if site.scope == "analytics")


def _four_three_sites(spec: NativeSpec) -> tuple[NativeSite, ...]:
    cleanup = set(_cleanup_sites(spec))
    return tuple(site for site in spec.sites if site not in cleanup)


def _native_cleanup_probe_data(
    data: bytes | bytearray, spec: NativeSpec | None = None
) -> dict[str, Any]:
    """Recognize cleanup-only state and reject any enabled 4:3 site."""

    spec = _NATIVE_SPEC if spec is None else spec
    result = _native_probe_data(data, spec)
    if result["state"] in ("unsupported", "ambiguous"):
        return result
    core_states = {target["name"]: target["state"] for target in result["targets"]}
    if any(core_states[site.name] != "original" for site in _four_three_sites(spec)):
        result.update(
            state="unsupported",
            reason="cleanup-only input contains a 4:3 native change",
        )
        return result
    cleanup_states = [
        _native_site_state(data, site)[0] for site in _cleanup_sites(spec)
    ]
    # Unsupported/ambiguous optional sites are a silent no-op. A uniquely
    # recognized original site is the only condition that requests cleanup.
    result["state"] = "original" if "original" in cleanup_states else "patched"
    return result


def _patch_native_cleanup_data(
    data: bytes, spec: NativeSpec | None = None
) -> bytes:
    spec = _NATIVE_SPEC if spec is None else spec
    before = _native_cleanup_probe_data(data, spec)
    if before["state"] not in ("original", "patched"):
        raise PatchError(f"cleanup-only native targets are {before['state']}")
    mutable = bytearray(data)
    for site in _cleanup_sites(spec):
        state, _reason = _native_site_state(mutable, site)
        if state == "original":
            mutable[site.offset : site.offset + len(site.original)] = site.patched
    result = bytes(mutable)
    after = _native_cleanup_probe_data(result, spec)
    if after["state"] != "patched":
        raise PatchError(f"cleanup-only native postcondition failed: {after['state']}")
    return result


_DEX_IMAGE: Any | None = None


def _dex_image_type():
    global _DEX_IMAGE
    if _DEX_IMAGE is not None:
        return _DEX_IMAGE
    helper = Path(__file__).resolve().parents[2] / "tools" / "apkvision_neutralize.py"
    name = "android4x3_huntdown_dex_helper"
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


def _dex_probe_data(
    data: bytes, spec: DexSpec | None = None
) -> tuple[dict[str, Any], int | None]:
    spec = _DEX_SPEC if spec is None else spec
    result: dict[str, Any] = {
        "name": "disable distributor-injected save extractor",
        "entry": spec.entry,
        "sha256": _sha256(data),
    }
    if len(data) != spec.size:
        result.update(state="unsupported", reason=f"DEX size is {len(data)}, expected {spec.size}")
        return result, None
    if _sha256(spec.original) != spec.original_instruction_sha256:
        result.update(state="unsupported", reason="audited DEX instruction metadata disagrees")
        return result, None
    try:
        dex = _dex_image_type()(data)
        matches = [
            method
            for method in dex.methods()
            if (method.class_descriptor, method.name, method.descriptor) == spec.identity
        ]
    except Exception as exc:
        result.update(state="unsupported", reason=str(exc))
        return result, None
    if len(matches) != 1:
        state = "ambiguous" if matches else "unsupported"
        result.update(state=state, reason=f"DEX method match count is {len(matches)}")
        return result, None
    method = matches[0]
    if method.code_offset != spec.code_offset or method.code_offset + 16 > len(data):
        result.update(state="unsupported", reason="DEX code-item offset changed")
        return result, None
    units = struct.unpack_from("<I", data, method.code_offset + 12)[0]
    offset = method.code_offset + 16
    if offset != spec.instruction_offset or units * 2 != len(spec.original):
        result.update(state="unsupported", reason="DEX instruction extent changed")
        return result, None
    actual = data[offset : offset + len(spec.original)]
    if actual == spec.original:
        state, expected_hash = "original", spec.original_sha256
    elif actual == spec.patched:
        state, expected_hash = "patched", spec.patched_sha256
    else:
        result.update(state="unsupported", reason="guarded DEX instructions changed", offset=offset)
        return result, offset
    if _sha256(data) != expected_hash:
        result.update(state="unsupported", reason=f"{state} DEX SHA-256 disagrees", offset=offset)
        return result, offset
    result.update(state=state, offset=offset, code_offset=method.code_offset)
    return result, offset


def _patch_dex_data(data: bytes, spec: DexSpec | None = None) -> bytes:
    spec = _DEX_SPEC if spec is None else spec
    before, offset = _dex_probe_data(data, spec)
    if before["state"] == "patched":
        return data
    if before["state"] != "original" or offset is None:
        raise PatchError(f"DEX extractor target is {before['state']}")
    dex = _dex_image_type()(data)
    actual = bytes(dex.data[offset : offset + len(spec.original)])
    if actual != spec.original:
        raise PatchError("DEX extractor changed after probing")
    dex.data[offset : offset + len(spec.original)] = spec.patched
    result = dex.finish()
    after, _ = _dex_probe_data(result, spec)
    if after["state"] != "patched":
        raise PatchError(f"DEX postcondition failed: {after['state']}")
    return result


def _data_probe_data(data: bytes, spec: DataSpec | None = None) -> dict[str, Any]:
    spec = _DATA_SPEC if spec is None else spec
    digest = _sha256(data)
    if len(data) == spec.original_size and digest == spec.original_sha256:
        state = "original"
    elif data == spec.patched and digest == spec.patched_sha256:
        state = "patched"
    else:
        state = "unsupported"
    return {
        "name": "remove injected playerprefs/device identifiers from assets/data0",
        "entry": spec.entry,
        "state": state,
        "size": len(data),
        "sha256": digest,
    }


def _analyse(
    extracted: dict[str, Path], *, cleanup_only: bool = False
) -> tuple[dict[str, Any], dict[str, Any]]:
    details: dict[str, Any] = {}

    native_path = extracted.get(LIBRARY_ENTRY)
    native = (
        {
            "name": LIBRARY_ENTRY,
            "entry": LIBRARY_ENTRY,
            "state": "unsupported",
            "reason": "required entry missing",
            "targets": [],
        }
        if native_path is None or not Path(native_path).is_file()
        else (
            _native_cleanup_probe_data(Path(native_path).read_bytes())
            if cleanup_only
            else _native_probe_data(Path(native_path).read_bytes())
        )
    )
    details["native"] = native

    # Source-specific cleanup targets are optional. Missing and unrecognized
    # entries are represented internally so apply() can make a safe no-op, but
    # they are deliberately excluded from the public compatibility report.
    dex_path = extracted.get(DEX_ENTRY)
    if dex_path is None or not Path(dex_path).is_file():
        dex, location = (
            {
                "name": DEX_ENTRY,
                "entry": DEX_ENTRY,
                "state": "absent",
            },
            None,
        )
    else:
        dex, location = _dex_probe_data(Path(dex_path).read_bytes())
    details["dex"] = (dex, location)

    data_path = extracted.get(INJECTED_DATA_ENTRY)
    data = (
        {
            "name": INJECTED_DATA_ENTRY,
            "entry": INJECTED_DATA_ENTRY,
            "state": "absent",
        }
        if data_path is None or not Path(data_path).is_file()
        else _data_probe_data(Path(data_path).read_bytes())
    )
    details["data"] = data

    if not cleanup_only:
        targets = list(native.get("targets") or [native])
        return {"state": native["state"], "targets": targets}, details

    # For the private clean-build helper, 4:3 must remain disabled. Cleanup is
    # complete when no uniquely recognized optional target remains original.
    if native["state"] in ("unsupported", "ambiguous"):
        state = native["state"]
    else:
        optional_states = [dex["state"], data["state"]]
        optional_states.extend(
            _native_site_state(Path(native_path).read_bytes(), site)[0]
            for site in _cleanup_sites(_NATIVE_SPEC)
        )
        state = "original" if "original" in optional_states else "patched"
    return {"state": state, "targets": list(native.get("targets") or [native])}, details


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Classify only the required 4:3 renderer targets."""

    report, _details = _analyse(extracted)
    if report["state"] in ("unsupported", "ambiguous"):
        report["detail"] = "the Huntdown 4:3 renderer targets were not recognized uniquely"
    return report


def probe_cleanup(extracted: dict[str, Path]) -> dict[str, Any]:
    """Classify the normal cleaned variant while requiring 4:3 to remain off."""

    report, _details = _analyse(extracted, cleanup_only=True)
    if report["state"] in ("unsupported", "ambiguous"):
        report["detail"] = (
            "the exact Huntdown cleanup-only targets were not all recognized"
        )
    return report


def _destination(output_dir: Path, entry: str) -> Path:
    result = Path(output_dir).joinpath(*entry.split("/"))
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Apply required 4:3 edits plus any uniquely recognized optional cleanup."""

    report, details = _analyse(extracted)
    if report["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"Huntdown targets are {report['state']}")
    replacements: dict[str, Path] = {}
    try:
        native_input = Path(extracted[LIBRARY_ENTRY]).read_bytes()
        native_output = _patch_native_data(native_input)
        if native_output != native_input:
            output = _destination(Path(output_dir), LIBRARY_ENTRY)
            output.write_bytes(native_output)
            replacements[LIBRARY_ENTRY] = output
        # These targets are intentionally opportunistic. Unknown DEX code or
        # launch data is preserved rather than guessed at or replaced.
        if details["dex"][0]["state"] == "original":
            output = _destination(Path(output_dir), DEX_ENTRY)
            output.write_bytes(_patch_dex_data(Path(extracted[DEX_ENTRY]).read_bytes()))
            replacements[DEX_ENTRY] = output
        if details["data"]["state"] == "original":
            output = _destination(Path(output_dir), INJECTED_DATA_ENTRY)
            output.write_bytes(_DATA_SPEC.patched)
            if _data_probe_data(output.read_bytes())["state"] != "patched":
                raise PatchError("injected-data postcondition failed")
            replacements[INJECTED_DATA_ENTRY] = output

        combined = dict(extracted)
        combined.update(replacements)
        after = probe(combined)
        if after["state"] != "patched":
            raise PatchError(f"combined postcondition failed: {after['state']}")
        return replacements
    except Exception:
        for output in replacements.values():
            output.unlink(missing_ok=True)
        raise


def apply_cleanup(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Create the normal cleaned variant without enabling any 4:3 site."""

    report, details = _analyse(extracted, cleanup_only=True)
    if report["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"Huntdown cleanup targets are {report['state']}")
    replacements: dict[str, Path] = {}
    try:
        native_input = Path(extracted[LIBRARY_ENTRY]).read_bytes()
        native_output = _patch_native_cleanup_data(native_input)
        if native_output != native_input:
            output = _destination(Path(output_dir), LIBRARY_ENTRY)
            output.write_bytes(native_output)
            replacements[LIBRARY_ENTRY] = output
        if details["dex"][0]["state"] == "original":
            output = _destination(Path(output_dir), DEX_ENTRY)
            output.write_bytes(_patch_dex_data(Path(extracted[DEX_ENTRY]).read_bytes()))
            replacements[DEX_ENTRY] = output
        if details["data"]["state"] == "original":
            output = _destination(Path(output_dir), INJECTED_DATA_ENTRY)
            output.write_bytes(_DATA_SPEC.patched)
            if _data_probe_data(output.read_bytes())["state"] != "patched":
                raise PatchError("injected-data postcondition failed")
            replacements[INJECTED_DATA_ENTRY] = output

        combined = dict(extracted)
        combined.update(replacements)
        after = probe_cleanup(combined)
        if after["state"] != "patched":
            raise PatchError(
                f"cleanup-only combined postcondition failed: {after['state']}"
            )
        return replacements
    except Exception:
        for output in replacements.values():
            output.unlink(missing_ok=True)
        raise
