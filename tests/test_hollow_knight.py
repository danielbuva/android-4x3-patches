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


def test_mono_ui_scaler_accepts_only_guarded_1080_and_1440_references() -> None:
    source = bytearray(32)
    source.extend(struct.pack("<iffffif", 1, 100.0, 1.0, 1920.0, 1080.0, 1, 0.0))
    source.extend(b"synthetic trailing fields")
    assert hk._ui_scaler_state(source) == ("original", 48)

    struct.pack_into("<f", source, 48, 1440.0)
    assert hk._ui_scaler_state(source) == ("patched", 48)

    struct.pack_into("<f", source, 48, 1200.0)
    assert hk._ui_scaler_state(source) == ("unsupported", None)


def _hud_trees(camera_size, x, y, scale):
    return (
        {"orthographic size": camera_size},
        {
            "m_LocalPosition": {"x": x, "y": y, "z": 38.1},
            "m_LocalScale": {"x": scale, "y": scale, "z": 1.0},
        },
    )


def test_mono_hud_layout_migrates_original_and_first_release() -> None:
    source = _hud_trees(
        hk.HUD_ORTHO_SOURCE,
        hk.HUD_CANVAS_SOURCE_X,
        hk.HUD_CANVAS_SOURCE_Y,
        hk.MONO_HUD_SCALE_SOURCE,
    )
    first_release = _hud_trees(
        hk.HUD_ORTHO_TARGET,
        hk.HUD_CANVAS_SOURCE_X,
        hk.MONO_HUD_V1_CANVAS_Y,
        hk.MONO_HUD_SCALE_SOURCE,
    )
    final = _hud_trees(
        hk.MONO_HUD_ORTHO_TARGET,
        hk.MONO_HUD_CANVAS_TARGET_X,
        hk.MONO_HUD_CANVAS_TARGET_Y,
        hk.MONO_HUD_SCALE_TARGET,
    )
    enlarged_release = _hud_trees(
        hk.HUD_ORTHO_TARGET,
        hk.MONO_HUD_V2_CANVAS_X,
        hk.MONO_HUD_V2_CANVAS_Y,
        hk.MONO_HUD_SCALE_V2,
    )
    fitted_inventory_release = _hud_trees(
        hk.MONO_HUD_ORTHO_V4,
        hk.MONO_HUD_V4_CANVAS_X,
        hk.MONO_HUD_V4_CANVAS_Y,
        hk.MONO_HUD_SCALE_V4,
    )
    prior_camera_release = _hud_trees(
        hk.HUD_ORTHO_TARGET,
        hk.MONO_HUD_V3_CANVAS_X,
        hk.MONO_HUD_V3_CANVAS_Y,
        hk.MONO_HUD_SCALE_SOURCE,
    )

    assert hk._mono_hud_layout_state(*source) == "original"
    assert hk._mono_hud_layout_state(*first_release) == "original"
    assert hk._mono_hud_layout_state(*enlarged_release) == "original"
    assert hk._mono_hud_layout_state(*prior_camera_release) == "original"
    assert hk._mono_hud_layout_state(*fitted_inventory_release) == "original"
    assert hk._mono_hud_layout_state(*final) == "patched"


def test_mono_hud_layout_rejects_unrecognized_safe_area_values() -> None:
    unknown = _hud_trees(hk.HUD_ORTHO_TARGET, -6.25, 8.0, 1.1)
    assert hk._mono_hud_layout_state(*unknown) == "unsupported"


def test_mono_hud_fsm_scale_is_unique_and_length_preserving() -> None:
    source = hk._hud_fsm_scale_pattern(hk.MONO_HUD_SCALE_SOURCE)
    patched = hk._hud_fsm_scale_pattern(hk.MONO_HUD_SCALE_TARGET)
    prefix = b"Slide Out\0HutongGames.PlayMaker.Actions.iTweenScaleTo\0"

    state, offset = hk._mono_hud_fsm_state(prefix + source)
    assert state == "original"
    assert offset == len(prefix)
    assert len(source) == len(patched)

    assert hk._mono_hud_fsm_state(prefix + patched)[0] == "patched"
    prior_release = hk._hud_fsm_scale_pattern(hk.MONO_HUD_SCALE_V4)
    assert hk._mono_hud_fsm_state(prefix + prior_release)[0] == "original"
    assert hk._mono_hud_fsm_state(prefix + source + source)[0] == "ambiguous"


def test_mono_inventory_root_migrates_prior_scaled_releases() -> None:
    source = {
        "m_LocalPosition": {
            "x": hk.INVENTORY_SOURCE_POSITION[0],
            "y": hk.INVENTORY_SOURCE_POSITION[1],
            "z": 40.4,
        },
        "m_LocalScale": {"x": 1.0, "y": 1.0, "z": 1.0},
    }
    patched = {
        "m_LocalPosition": {
            "x": hk.INVENTORY_TARGET_POSITION[0],
            "y": hk.INVENTORY_TARGET_POSITION[1],
            "z": 40.4,
        },
        "m_LocalScale": {
            "x": hk.INVENTORY_SCALE_TARGET,
            "y": hk.INVENTORY_SCALE_TARGET,
            "z": 1.0,
        },
    }

    assert hk._mono_inventory_layout_state(source) == "original"
    assert hk._mono_inventory_layout_state(patched) == "patched"

    first_release = {
        "m_LocalPosition": {
            "x": hk.INVENTORY_V1_POSITION[0],
            "y": hk.INVENTORY_V1_POSITION[1],
            "z": 40.4,
        },
        "m_LocalScale": {
            "x": hk.INVENTORY_SCALE_V1,
            "y": hk.INVENTORY_SCALE_V1,
            "z": 1.0,
        },
    }
    assert hk._mono_inventory_layout_state(first_release) == "patched"

    second_release = {
        "m_LocalPosition": {
            "x": hk.INVENTORY_V2_POSITION[0],
            "y": hk.INVENTORY_V2_POSITION[1],
            "z": 40.4,
        },
        "m_LocalScale": {
            "x": hk.INVENTORY_SCALE_V2,
            "y": hk.INVENTORY_SCALE_V2,
            "z": 1.0,
        },
    }
    assert hk._mono_inventory_layout_state(second_release) == "original"

def test_mono_inventory_panes_use_uniform_fit_without_stretching() -> None:
    source = {
        "m_LocalScale": {
            "x": hk.INVENTORY_CHILD_SCALE_V1,
            "y": hk.INVENTORY_CHILD_SCALE_V1,
            "z": 1.0,
        }
    }
    patched = {
        "m_LocalScale": {
            "x": hk.INVENTORY_CHILD_SCALE_TARGET,
            "y": hk.INVENTORY_CHILD_SCALE_TARGET,
            "z": 1.0,
        }
    }
    assert hk._mono_inventory_child_state(source) == "original"
    assert hk._mono_inventory_child_state(patched) == "patched"
    assert patched["m_LocalScale"]["x"] == patched["m_LocalScale"]["y"]


def test_mono_runtime_inventory_body_uses_uniform_scale() -> None:
    class FakeAssembly:
        def field_token(self, type_name, field_name):
            return {"gc": 1, "shouldEnablePause": 2, "ih": 3}[field_name]

        def method_token(self, type_name, method_name):
            return {"MoveMenuToHUDCamera": 4, "AllowPause": 5}[method_name]

        def member_token(self, type_name, method_name, signature):
            return {
                "Find": 6,
                "get_transform": 7,
                ".ctor": 8,
                "set_localScale": 9,
                "set_localPosition": 10,
            }[method_name]

        def user_string_token(self, value):
            assert value == "Inventory"
            return 11

    body = hk._managed_inventory_runtime_body(FakeAssembly())
    scale = struct.pack("<f", hk.INVENTORY_RUNTIME_SCALE)
    assert body.count(b"\x22" + scale) == 2
    assert body.count(b"\x22" + struct.pack("<f", 1.0)) == 1
    for value in hk.INVENTORY_RUNTIME_POSITION:
        assert b"\x22" + struct.pack("<f", value) in body


def test_mono_touch_layout_migrates_first_release_to_real_top_edge() -> None:
    def tree(anchor, position):
        return {
            "m_AnchorMin": {"x": 0.5, "y": anchor},
            "m_AnchorMax": {"x": 0.5, "y": anchor},
            "m_AnchoredPosition": {"x": 0.0, "y": position},
        }

    assert hk._mono_touch_layout_state(
        tree(0.5, hk.MONO_TOUCH_SOURCE_POSITION_Y)
    ) == "original"
    assert hk._mono_touch_layout_state(
        tree(1.0, hk.MONO_TOUCH_V1_POSITION_Y)
    ) == "original"
    assert hk._mono_touch_layout_state(
        tree(1.0, hk.MONO_TOUCH_TARGET_POSITION_Y)
    ) == "patched"


def test_mono_and_il2cpp_runtime_entries_are_both_discoverable() -> None:
    config = (REPO_ROOT / "games" / "hollow-knight" / "config.json").read_text(
        encoding="utf-8"
    )
    assert hk.MONO_ENTRY in config
    assert hk.ARM64_ENTRY in config
    assert hk.ARMV7_ENTRY in config
