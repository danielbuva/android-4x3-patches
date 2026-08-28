from __future__ import annotations

import struct
import subprocess
from pathlib import Path

import pytest

from android4x3 import gamemaker
from android4x3.registry import Registry
from tools import apkvision_neutralize as branding


REPO_ROOT = Path(__file__).resolve().parents[1]


def _game_module(game_id: str):
    registry = Registry(REPO_ROOT / "games")
    return registry.module(registry.by_id[game_id])


def test_unity_serialized_field_matchers_recognize_original_patched_and_ambiguous() -> None:
    skul = _game_module("skul")
    camera = bytearray(24)
    struct.pack_into("<iiiiii", camera, 0, 32, 640, 360, 0, 0, 0)
    canvas = bytearray(24)
    struct.pack_into("<i", canvas, 0, 1)
    struct.pack_into("<ff", canvas, 12, 1920.0, 1080.0)
    struct.pack_into("<i", canvas, 20, 1)

    assert skul._camera_pattern(camera) == ("original", 8)
    assert skul._canvas_pattern(canvas) == ("original", 16)
    struct.pack_into("<i", camera, 8, 480)
    struct.pack_into("<f", canvas, 16, 1440.0)
    assert skul._camera_pattern(camera) == ("patched", 8)
    assert skul._canvas_pattern(canvas) == ("patched", 16)
    assert skul._camera_pattern(bytes(camera) + bytes(camera)) == ("ambiguous", -1)


def test_contextual_native_matcher_has_unique_original_and_patched_states() -> None:
    silksong = _game_module("silksong")
    method = bytearray(64)
    words = {
        0: 0x90000008,
        4: 0x90000009,
        8: 0x910023E0,
        12: 0xAA1F03E1,
        16: silksong._ORIGINAL_WORDS[16],
        20: silksong._ORIGINAL_WORDS[20],
        24: 0xBD400100,
        28: 0xBD400121,
        32: 0x94000000,
        36: 0x1E204120,
    }
    for offset, word in words.items():
        struct.pack_into("<I", method, offset, word)
    method[40 : 40 + len(silksong._NATIVE_CONTEXT)] = silksong._NATIVE_CONTEXT

    assert silksong._native_candidates(method) == [{"offset": 0, "state": "original"}]
    for offset, word in silksong._PATCHED_WORDS.items():
        struct.pack_into("<I", method, offset, word)
    assert silksong._native_candidates(method) == [{"offset": 0, "state": "patched"}]


def test_silksong_probe_never_inspects_optional_watermark(monkeypatch) -> None:
    silksong = _game_module("silksong")

    class Bundle:
        files = {"level0": object()}

    monkeypatch.setattr(silksong, "_load_bundle", lambda _path: (object(), Bundle()))
    monkeypatch.setattr(
        silksong,
        "_find_loading",
        lambda _level: {"state": "patched", "path_id": 1, "y": -465.0},
    )
    monkeypatch.setattr(
        silksong,
        "_find_watermark",
        lambda _level: (_ for _ in ()).throw(AssertionError("branding was probed")),
    )

    result = silksong._probe_ui(Path("synthetic.unity3d"))

    assert result == {
        "state": "patched",
        "targets": {
            "loading_label": {"state": "patched", "path_id": 1, "y": -465.0}
        },
    }


@pytest.mark.parametrize(
    ("patched_code", "original_code", "expected"),
    [(1, 0, "original"), (0, 1, "patched"), (0, 0, "ambiguous"), (1, 1, "unsupported")],
)
@pytest.mark.parametrize("game_id", ["advent-neon", "faith"])
def test_gamemaker_orchestration_classifies_structural_script_results(
    tmp_path: Path,
    monkeypatch,
    patched_code: int,
    original_code: int,
    expected: str,
    game_id: str,
) -> None:
    game = _game_module(game_id)
    archive = tmp_path / "game.droid"
    archive.write_bytes(b"synthetic GameMaker fixture")
    monkeypatch.setattr(
        gamemaker,
        "find_undertale_mod_cli",
        lambda: tmp_path / "UndertaleModCli",
    )

    def run(_umt, _archive, script: Path, output=None):
        code = patched_code if script.name == "verify.csx" else original_code
        return subprocess.CompletedProcess([], code, stdout="", stderr="")

    monkeypatch.setattr(gamemaker, "run_undertale_script", run)

    assert game.probe({game.REQUIRED_ENTRIES[0]: archive})["state"] == expected


def test_dex_overlay_matcher_and_in_place_void_method_patch() -> None:
    data = bytearray(0x90)
    data[:8] = b"dex\n035\0"
    struct.pack_into("<I", data, 0x20, len(data))
    struct.pack_into("<I", data, 0x24, branding.DexImage.HEADER_SIZE)
    struct.pack_into("<I", data, 0x28, 0x12345678)
    code_offset = 0x70
    struct.pack_into("<I", data, code_offset + 12, 4)
    data[code_offset + 16 : code_offset + 24] = b"\x12\x00\x0f\x00\x01\x00\x00\x00"
    method = branding._DexMethod(
        "Lapkvision/Overlay;", "krjUyALI", "(Landroid/app/Activity;)V", code_offset
    )
    dex = branding.DexImage(data)

    assert branding._is_dex_overlay_method(method)
    changed, instruction_offset = dex.replace_void_method(method)
    output = dex.finish()

    assert changed is True
    assert instruction_offset == code_offset + 16
    assert output[instruction_offset : instruction_offset + 8] == b"\x0e\x00" + b"\x00" * 6
