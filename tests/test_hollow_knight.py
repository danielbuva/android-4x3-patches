from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "games" / "hollow-knight" / "patch_impl.py"

spec = importlib.util.spec_from_file_location("hollow_knight_patch_test", MODULE_PATH)
assert spec is not None and spec.loader is not None
hk = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hk
spec.loader.exec_module(hk)


def _instruction(
    name: str,
    offset: int,
    operand=None,
    opcode_bytes: bytes = b"\x22",
    operand_bytes: bytes = b"",
):
    return SimpleNamespace(
        opcode=SimpleNamespace(name=name),
        offset=offset,
        operand=operand,
        opcode_bytes=opcode_bytes,
        operand_bytes=operand_bytes,
    )


class _FakeAssembly:
    def __init__(self, methods):
        self._methods = methods

    def methods(self, type_name: str, method_name: str):
        return self._methods.get((type_name, method_name), [])

    def field_name(self, operand):
        return operand


def test_managed_float_target_is_method_scoped_and_length_preserving() -> None:
    source = struct.pack("<f", hk.SOURCE_ASPECT)
    body = SimpleNamespace(
        instructions=[
            _instruction("ldc.r4", 12, hk.SOURCE_ASPECT, b"\x22", source),
            _instruction("ret", 17, None, b"\x2a"),
        ]
    )
    assembly = _FakeAssembly({("Aspect", "Apply"): [(100, body)]})

    target, edits = hk._managed_float_target(
        assembly,
        "Aspect",
        "Apply",
        1,
        1,
        hk.SOURCE_ASPECT,
        hk.TARGET_ASPECT,
        "aspect",
    )

    assert target["state"] == "original"
    assert edits == [(113, source, struct.pack("<f", hk.TARGET_ASPECT))]
    assert len(edits[0][1]) == len(edits[0][2])


def test_managed_float_target_accepts_known_partial_post_state() -> None:
    source = struct.pack("<f", hk.CAMERA_LIMIT_SOURCE)
    patched = struct.pack("<f", hk.CAMERA_LIMIT_TARGET)
    body = SimpleNamespace(
        instructions=[
            _instruction("ldc.r4", 12, hk.CAMERA_LIMIT_SOURCE, b"\x22", source),
            _instruction("ldc.r4", 17, hk.CAMERA_LIMIT_TARGET, b"\x22", patched),
        ]
    )
    assembly = _FakeAssembly({("Camera", "Bounds"): [(40, body)]})

    target, edits = hk._managed_float_target(
        assembly,
        "Camera",
        "Bounds",
        1,
        2,
        hk.CAMERA_LIMIT_SOURCE,
        hk.CAMERA_LIMIT_TARGET,
        "bounds",
    )

    assert target["state"] == "original"
    assert target["original_matches"] == 1
    assert target["patched_matches"] == 1
    assert len(edits) == 1


def test_managed_full_viewport_branch_has_guarded_original_and_patched_states() -> None:
    source_body = SimpleNamespace(
        instructions=[
            _instruction(
                "ldsfld",
                12,
                "ModManagerSettings::BlackBars",
                b"\x7e",
                b"\x01\x00\x00\x04",
            ),
            _instruction("brtrue.s", 17, 30, b"\x2d", b"\x0b"),
            _instruction("ret", 19, None, b"\x2a"),
        ]
    )
    source = _FakeAssembly(
        {("ForceCameraAspect", "AutoScaleViewport"): [(100, source_body)]}
    )
    target, edits = hk._managed_black_bars_target(source)
    assert target["state"] == "original"
    assert edits == [(117, b"\x2d\x0b", b"\x26\x00")]

    patched_body = SimpleNamespace(
        instructions=[
            source_body.instructions[0],
            _instruction("pop", 17, None, b"\x26"),
            _instruction("nop", 18, None, b"\x00"),
        ]
    )
    patched = _FakeAssembly(
        {("ForceCameraAspect", "AutoScaleViewport"): [(100, patched_body)]}
    )
    target, edits = hk._managed_black_bars_target(patched)
    assert target["state"] == "patched"
    assert edits == []


def test_disclaimer_scaler_requires_expand_mode_structure() -> None:
    raw = bytearray(32)
    raw.extend(struct.pack("<iffffif", 1, 100.0, 1.0, 1920.0, 1080.0, 1, 0.0))
    raw.extend(b"synthetic trailing fields")
    assert hk._disclaimer_scaler_state(raw) == ("patched", 32)

    struct.pack_into("<i", raw, 32 + 20, 0)
    assert hk._disclaimer_scaler_state(raw) == ("unsupported", None)


def test_mono_and_il2cpp_runtime_entries_are_both_discoverable() -> None:
    config = (REPO_ROOT / "games" / "hollow-knight" / "config.json").read_text(
        encoding="utf-8"
    )
    assert hk.MONO_ENTRY in config
    assert hk.ARM64_ENTRY in config
    assert hk.ARMV7_ENTRY in config
