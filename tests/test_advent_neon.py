from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = REPO_ROOT / "games" / "advent-neon"


def test_advent_scripts_are_guarded_and_contain_no_complete_game_routines() -> None:
    patch = (MODULE_DIR / "patch.csx").read_text(encoding="utf-8")
    original = (MODULE_DIR / "original_verify.csx").read_text(encoding="utf-8")
    verified = (MODULE_DIR / "verify.csx").read_text(encoding="utf-8")

    assert "Require(Data.GeneralInfo.Name.Content == \"AdventNEON\"" in patch
    assert "Require(Data.GeneralInfo.BytecodeVersion == 17" in patch
    assert "Require(enabledViews == 66" in patch
    assert "ReplaceOnce" in patch
    assert "ReplaceCount" in patch
    assert "imports.Import()" in patch

    assert "DefaultWindowHeight == 720" in original
    assert "view.ViewY == 0" in original
    assert "DefaultWindowHeight == 960" in verified
    assert "view.ViewY == -120" in verified
    assert "view.ViewHeight == 960" in verified


def test_advent_scripts_cover_camera_gui_and_presentation_postconditions() -> None:
    patch = (MODULE_DIR / "patch.csx").read_text(encoding="utf-8")
    original = (MODULE_DIR / "original_verify.csx").read_text(encoding="utf-8")
    verified = (MODULE_DIR / "verify.csx").read_text(encoding="utf-8")

    for target in (
        "gml_Object_game_system_Create_0",
        "gml_Object_oCamera_Step_0",
        "gml_GlobalScript_ConvertToGUI_Y",
        "gml_Object_game_system_Draw_77",
        "gml_Object_oMenu_Create_0",
        "gml_Object_oStartSplash_Draw_64",
        "gml_Object_game_cutscene_Draw_64",
        "gml_Object_oDialogue_Draw_64",
        "gml_Object_oBossIntro_Draw_64",
        "gml_GlobalScript_drawStageClear3",
    ):
        assert target in verified

    for patched_anchor in (
        "draw_sprite_ext(splashSprite, 0, 640, 500",
        "x = display_get_gui_width()",
        "draw_text(boxEdge + textBuffer, 896, currentText);",
        "sprite_get_width(charSprite) * 0.5)), 864, 0.82,",
        "bgZigXBot, 960 - barWidth,",
        "bgPortraitSprite, 0, 640, 960,",
        "choose(irandom_range(0, 288), irandom_range(672, 960))",
        ", 0, 960, irandom_range(1, 4), 270,",
    ):
        assert patched_anchor in verified

    assert 'new { Id = 100013u, Y = 624' in original
    assert 'matches[0].Y += 120' in patch
    assert 'new { Id = 100013u, Y = 744' in verified
    assert 'new { Id = 100019u, Name = "oEnemyPressStart", X = 320, Y = 208' in original
    assert 'matches[0].Y += 60' in patch
    assert 'new { Id = 100019u, Name = "oEnemyPressStart", X = 320, Y = 268' in verified
    assert '"bgFlavorTopY + 120", 2' in verified
    assert 'spr_joybase' in original
    assert 'ReplaceOnce(mobileDraw, mobileDraw, "exit;"' in patch
    assert 'RequireCode("gml_Object_obj_mobilecontrols_Draw_64", "exit;")' in verified


def test_advent_optional_runner_splash_cleanup_is_exact_and_non_gating(tmp_path: Path) -> None:
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "advent_patch_test", MODULE_DIR / "patch_impl.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    source = tmp_path / "splash.png"
    from PIL import Image

    Image.new("RGB", (1024, 768), (12, 34, 56)).save(source)
    expected = (module._SPLASHES["assets/splash.png"][0], (1024, 768), "RGB")
    assert module._neutralized_splash(source, expected) is None

    data = source.read_bytes()
    recognized = (module.hashlib.sha256(data).hexdigest(), (1024, 768), "RGB")
    output = module._neutralized_splash(source, recognized)
    assert output is not None
    with Image.open(module.BytesIO(output)) as image:
        assert image.size == (1024, 768)
        assert image.getbbox() is None


def test_every_advent_mutation_has_one_named_verifier_postcondition() -> None:
    patch = (MODULE_DIR / "patch.csx").read_text(encoding="utf-8")
    verified = (MODULE_DIR / "verify.csx").read_text(encoding="utf-8")

    mutation_calls = re.findall(
        r"(?m)^\s*[A-Za-z_]\w*\s*=\s*Replace(?:Once|Count)\(", patch
    )
    patch_ids = re.findall(r"(?m)^// PATCH-MUTATION: ([a-z0-9.-]+)$", patch)
    verifier_ids = re.findall(
        r"(?m)^// VERIFIED-MUTATION: ([a-z0-9.-]+)$", verified
    )

    assert len(patch_ids) == len(mutation_calls)
    assert len(patch_ids) == len(set(patch_ids))
    assert len(verifier_ids) == len(set(verifier_ids))
    assert set(verifier_ids) == set(patch_ids)
