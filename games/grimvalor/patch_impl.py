"""Exact cleanup and native 4:3 selection for Grimvalor 1.2.13 arm64.

The audited build contains a built-in 4:3 UI path.  Gameplay and cinematic
cameras already consume Unity's live ``Camera.aspect`` value, so the patch
enables that UI path without replacing camera math with a fixed aspect ratio.

Ad and telemetry entry points are disabled narrowly.  Billing, purchases,
cloud saves, authentication, achievements, and Play Games are not targeted.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LIBRARY_ENTRY = "lib/arm64-v8a/libil2cpp.so"
REQUIRED_ENTRIES = (LIBRARY_ENTRY,)

_FALSE = bytes.fromhex("00 00 80 52 c0 03 5f d6")
_TRUE = bytes.fromhex("20 00 80 52 c0 03 5f d6")
_VOID = bytes.fromhex("c0 03 5f d6 1f 20 03 d5")


class PatchError(RuntimeError):
    """The supplied library is not the uniquely audited native build."""


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


def _site(
    name: str,
    scope: str,
    rva: int,
    before: str,
    original: str,
    patched: bytes,
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
        patched=patched,
        after=bytes.fromhex(after),
        signature_sha256=signature_sha256,
    )


_SITES = (
    _site(
        "AdController.Init",
        "ads",
        0x1786128,
        "f44f41a9fe57c2a8c0035fd60e6ef897",
        "fe57bea9f44f01a9",
        _VOID,
        "94f80090f30300aa883a7e3988010037",
        "b300256a82f51062ef495f9b3d1ad420294fd7d2496d3bc190c051069122739b",
    ),
    _site(
        "AdController.ShouldRequestNewInterstitial",
        "ads",
        0x1786264,
        "e1031faae9fa0214fe0f1ff8bf6df897",
        "fe4fbfa9f30300aa",
        _FALSE,
        "0e0000946000003668e2403988000034",
        "d731624e4f29322b12fde9fd9cc67a918c3892a56733bdf5edd1e635ba429468",
    ),
    _site(
        "AdController.ShouldShowAds",
        "ads",
        0x17862A4,
        "753e439420ff073720008052f8ffff17",
        "fe0f1ef8f44f01a9",
        _FALSE,
        "94f8009053e700b0883e7e39738244f9",
        "458258e816ac2fcf0fa8247cf1fa39bf91ca2b81e74e4e7f7bb79f6ca8a7fe37",
    ),
    _site(
        "AdController.RequestInterstitial",
        "ads",
        0x178639C,
        "a0fd073620008052ecffff17716df897",
        "fe0f1df8f65701a9",
        _VOID,
        "f44f02a995f8009054e700b0f30300aa",
        "42c39883a156128862ab136ce623f05ee06f4ca0dea7f8a0b657b027e1badeab",
    ),
    _site(
        "AdController.ShowInterstitial",
        "ads",
        0x1786584,
        "f65741a9fe0743f8c0035fd6f76cf897",
        "fe0f1df8f65701a9",
        _FALSE,
        "f44f02a996f8009055e700b0f403012a",
        "d3e97e9c1b12dfd0bee379241bf530cf3b9d5a6ba76f2f99395c617f1b2a76a1",
    ),
    _site(
        "Analytics.Initialize",
        "analytics",
        0x1786D5C,
        "f44f41a9fe0742f8c0035fd6016bf897",
        "fe0f1df8f65701a9",
        _VOID,
        "f44f02a994f8009053e700d0886e7e39",
        "4b0c04d02cf97c4c4156a160505f3df1026e67ef6ab60fea15661248aa57d426",
    ),
    _site(
        "Analytics.QueueEvent",
        "analytics",
        0x1786F78,
        "f44f46a9fe2b40f9ffc30191c0035fd6",
        "ff0301d1fe0b00f9",
        _VOID,
        "f65702a9f44f03a996f8009055e700d0",
        "7ce8264987061fb864ebd067918626ff569d3147ea2faacbe42b9f4dc26ba0df",
    ),
    _site(
        "Analytics.SendQueuedEvent",
        "analytics",
        0x178711C,
        "f65742a9ff030191c0035fd6116af897",
        "e80f1afcfe0700f9",
        _VOID,
        "fc6f01a9fa6702a9f85f03a9f65704a9",
        "c91bb661d8a34990a855f654d362e2a9114f57e9d0fdc2cfab9ff409475c6234",
    ),
    _site(
        "Analytics.Update",
        "analytics",
        0x17872F4,
        "9e69f897a669f897e1031faa4c69f897",
        "e80f1dfcfe5701a9",
        _VOID,
        "f44f02a973f800f055e700b0687e7e39",
        "d89d5ce8a1e26e04e64627031393a0adc62f590d02f5149b0ea8cded3dc3d4db",
    ),
    _site(
        "UIResolution.get_is4_3",
        "4:3 UI, intro, and menus",
        0x17DD3CC,
        "2018201efe4fc1a8c0035fd66511f797",
        "fe7fbfa9e1330091",
        _TRUE,
        "e223009144040094e103412da881ffd0",
        "cb120c56cd6baae356840adb3bcb86fd3d3a811b63f39819a6b1a3a11be6b2cd",
    ),
)

_NATIVE_SPEC = NativeSpec(
    entry=LIBRARY_ENTRY,
    size=57_192_968,
    original_sha256="4376a6f0fa92e9ddb23b2285de7f79c2ff9d0b412f611378d42791226b1a7d84",
    cleanup_sha256="d606a689702a3667eafd2470a94268f7b3c616c25d3d9e6141a1ea1baa8c4d2b",
    patched_sha256="599e80c40aeeb708abdb7c633ac0d46c625473f833b5c4a0c6ed855f6c70592a",
    sites=_SITES,
)
_CLEANUP_ONLY_SHA256 = _NATIVE_SPEC.cleanup_sha256


def _sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest()


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
    if len(data) != spec.size:
        return f"library size is {len(data)}, expected {spec.size}"
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
    for site in spec.sites:
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


def _site_state(data: bytes | bytearray, site: NativeSite) -> tuple[str, str | None]:
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
        "name": "Grimvalor arm64 cleanup and 4:3 selector",
        "entry": spec.entry,
        "sha256": _sha256(data),
    }
    error = _elf_error(data, spec)
    if error is not None:
        result.update(state="unsupported", reason=error, targets=[])
        return result

    canonical = bytearray(data)
    targets: list[dict[str, Any]] = []
    states: list[str] = []
    for site in spec.sites:
        state, reason = _site_state(data, site)
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
        if state == "patched":
            canonical[site.offset : site.offset + len(site.original)] = site.original

    result["targets"] = targets
    if "ambiguous" in states:
        result.update(state="ambiguous", reason="a native signature is not unique")
        return result
    if "unsupported" in states:
        result.update(state="unsupported", reason="a guarded native signature changed")
        return result
    if _sha256(canonical) != spec.original_sha256:
        result.update(
            state="unsupported",
            reason="canonical native SHA-256 does not match the audited build",
        )
        return result
    state = "patched" if states and set(states) == {"patched"} else "original"
    if state == "patched" and _sha256(data) != spec.patched_sha256:
        result.update(
            state="unsupported",
            reason="patched native SHA-256 postcondition disagrees",
        )
        return result
    result["state"] = state
    return result


def _patch_native_data(data: bytes, spec: NativeSpec | None = None) -> bytes:
    spec = _NATIVE_SPEC if spec is None else spec
    before = _native_probe_data(data, spec)
    if before["state"] not in ("original", "patched"):
        raise PatchError(f"native targets are {before['state']}")
    mutable = bytearray(data)
    for site in spec.sites:
        actual = bytes(mutable[site.offset : site.offset + len(site.original)])
        if actual == site.original:
            mutable[site.offset : site.offset + len(site.original)] = site.patched
        elif actual != site.patched:
            raise PatchError(f"{site.name}: state changed after probing")
    result = bytes(mutable)
    after = _native_probe_data(result, spec)
    if after["state"] != "patched":
        raise PatchError(f"native postcondition failed: {after['state']}")
    return result


def _cleanup_sites(spec: NativeSpec) -> tuple[NativeSite, ...]:
    return tuple(site for site in spec.sites if site.scope in {"ads", "analytics"})


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
    states = {target["name"]: target["state"] for target in result["targets"]}
    if any(states[site.name] != "original" for site in _four_three_sites(spec)):
        result.update(
            state="unsupported",
            reason="cleanup-only input contains a 4:3 native change",
        )
        return result
    cleanup_states = {states[site.name] for site in _cleanup_sites(spec)}
    state = "patched" if cleanup_states == {"patched"} else "original"
    if state == "patched" and _sha256(data) != spec.cleanup_sha256:
        result.update(
            state="unsupported",
            reason="cleanup-only native SHA-256 postcondition disagrees",
        )
        return result
    result["state"] = state
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
        actual = bytes(mutable[site.offset : site.offset + len(site.original)])
        if actual == site.original:
            mutable[site.offset : site.offset + len(site.original)] = site.patched
        elif actual != site.patched:
            raise PatchError(f"{site.name}: state changed after cleanup probing")
    result = bytes(mutable)
    after = _native_cleanup_probe_data(result, spec)
    if after["state"] != "patched":
        raise PatchError(f"cleanup-only native postcondition failed: {after['state']}")
    return result


def probe(extracted: dict[str, Path]) -> dict[str, Any]:
    """Classify the exact arm64 build and every cleanup/4:3 target."""

    source = extracted.get(LIBRARY_ENTRY)
    if source is None or not Path(source).is_file():
        return {
            "state": "unsupported",
            "detail": f"required entry missing: {LIBRARY_ENTRY}",
            "targets": [],
        }
    result = _native_probe_data(Path(source).read_bytes())
    report = {"state": result["state"], "targets": result.get("targets", [])}
    if result["state"] in ("unsupported", "ambiguous"):
        report["detail"] = result.get("reason", "native targets were not recognized")
    return report


def probe_cleanup(extracted: dict[str, Path]) -> dict[str, Any]:
    """Classify the normal cleaned variant while requiring 4:3 to remain off."""

    source = extracted.get(LIBRARY_ENTRY)
    if source is None or not Path(source).is_file():
        return {
            "state": "unsupported",
            "detail": f"required entry missing: {LIBRARY_ENTRY}",
            "targets": [],
        }
    result = _native_cleanup_probe_data(Path(source).read_bytes())
    report = {"state": result["state"], "targets": result.get("targets", [])}
    if result["state"] in ("unsupported", "ambiguous"):
        report["detail"] = result.get("reason", "cleanup targets were not recognized")
    return report


def _destination(output_dir: Path, entry: str) -> Path:
    result = Path(output_dir).joinpath(*entry.split("/"))
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Finish recognized cleanup/4:3 sites and verify the exact final hash."""

    initial = probe(extracted)
    if initial["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"Grimvalor targets are {initial['state']}")
    if initial["state"] == "patched":
        return {}
    source = Path(extracted[LIBRARY_ENTRY])
    output = _destination(Path(output_dir), LIBRARY_ENTRY)
    try:
        output.write_bytes(_patch_native_data(source.read_bytes()))
        combined = dict(extracted)
        combined[LIBRARY_ENTRY] = output
        after = probe(combined)
        if after["state"] != "patched":
            raise PatchError(f"combined postcondition failed: {after['state']}")
        return {LIBRARY_ENTRY: output}
    except Exception:
        output.unlink(missing_ok=True)
        raise


def apply_cleanup(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Create the normal cleaned variant without enabling any 4:3 site."""

    initial = probe_cleanup(extracted)
    if initial["state"] in ("unsupported", "ambiguous"):
        raise PatchError(f"Grimvalor cleanup targets are {initial['state']}")
    if initial["state"] == "patched":
        return {}
    source = Path(extracted[LIBRARY_ENTRY])
    output = _destination(Path(output_dir), LIBRARY_ENTRY)
    try:
        output.write_bytes(_patch_native_cleanup_data(source.read_bytes()))
        combined = dict(extracted)
        combined[LIBRARY_ENTRY] = output
        after = probe_cleanup(combined)
        if after["state"] != "patched":
            raise PatchError(f"cleanup-only combined postcondition failed: {after['state']}")
        return {LIBRARY_ENTRY: output}
    except Exception:
        output.unlink(missing_ok=True)
        raise
