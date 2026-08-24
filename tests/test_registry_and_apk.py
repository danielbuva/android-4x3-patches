from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from android4x3.apk import extract_entries, inspect_apk, resolve_entries
from android4x3.errors import PatchError
from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_publishable_registry_loads_every_declared_game_module() -> None:
    registry = Registry(REPO_ROOT / "games")

    assert {game.id for game in registry.games} == {
        "baba-is-you",
        "blasphemous",
        "faith",
        "hollow-knight",
        "hotline-miami",
        "sea-of-stars",
        "shin-chan",
        "silksong",
        "skul",
        "vampire-survivors",
    }
    for game in registry.games:
        module = registry.module(game)
        assert isinstance(module.REQUIRED_ENTRIES, tuple)
        assert callable(module.probe)
        assert callable(module.apply)


def test_registry_loads_config_and_module_states(tmp_path: Path, make_synthetic_game) -> None:
    repo = tmp_path / "synthetic repository"
    make_synthetic_game(repo)
    registry = Registry(repo / "games")

    config = registry.by_package["example.synthetic.game"]
    assert config.id == "synthetic-game"
    assert config.display_name == "Synthetic Game"
    assert config.tested_versions == ("test-only",)
    assert config.experimental is False

    module = registry.module(config)
    state_file = tmp_path / "state with spaces.bin"
    extracted = {module.ENTRY: state_file}

    state_file.write_bytes(b"ORIGINAL")
    assert module.probe(extracted)["state"] == "original"
    replacements = module.apply(extracted, tmp_path / "patched files")
    assert replacements[module.ENTRY].read_bytes() == b"PATCHED"
    assert module.probe({module.ENTRY: replacements[module.ENTRY]})["state"] == "patched"

    state_file.write_bytes(b"ORIGINAL|PATCHED")
    assert module.probe(extracted)["state"] == "ambiguous"

    state_file.write_bytes(b"UNKNOWN")
    assert module.probe(extracted)["state"] == "unsupported"


def test_registry_rejects_duplicate_packages(tmp_path: Path, make_synthetic_game) -> None:
    repo = tmp_path / "repo"
    make_synthetic_game(repo, game_id="first", package="org.example.duplicate")
    make_synthetic_game(repo, game_id="second", package="org.example.duplicate")

    with pytest.raises(PatchError, match="duplicate package registration"):
        Registry(repo / "games")


def test_registry_rejects_module_missing_required_exports(tmp_path: Path) -> None:
    game = tmp_path / "games" / "incomplete"
    game.mkdir(parents=True)
    (game / "config.json").write_text(
        json.dumps(
            {
                "id": "incomplete",
                "display_name": "Incomplete",
                "package_names": ["org.example.incomplete"],
            }
        ),
        encoding="utf-8",
    )
    (game / "patch_impl.py").write_text("REQUIRED_ENTRIES = ()\n", encoding="utf-8")
    registry = Registry(tmp_path / "games")

    with pytest.raises(PatchError, match="missing required export probe"):
        registry.module(registry.by_id["incomplete"])


def test_registry_registers_dynamic_module_before_dataclass_execution(tmp_path: Path) -> None:
    game = tmp_path / "games" / "dataclass-game"
    game.mkdir(parents=True)
    (game / "config.json").write_text(
        json.dumps(
            {
                "id": "dataclass-game",
                "display_name": "Dataclass Game",
                "package_names": ["org.example.dataclass"],
            }
        ),
        encoding="utf-8",
    )
    (game / "patch_impl.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Target:\n"
        "    state: str\n"
        "REQUIRED_ENTRIES = ()\n"
        "def probe(extracted): return {'state': Target('patched').state}\n"
        "def apply(extracted, output_dir): return {}\n",
        encoding="utf-8",
    )
    registry = Registry(tmp_path / "games")

    module = registry.module(registry.by_id["dataclass-game"])

    assert module.probe({})["state"] == "patched"


def test_inspect_resolve_and_extract_entries(
    tmp_path: Path, make_apk, binary_manifest
) -> None:
    apk = make_apk(
        tmp_path / "input APKs" / "synthetic game.apk",
        manifest=binary_manifest("org.example.archive", "2.0", 20),
        entries=[
            ("assets/data.bin", b"core", zipfile.ZIP_STORED),
            ("assets/ui/menu.txt", b"menu", zipfile.ZIP_DEFLATED),
            ("assets/ui/hud.txt", b"hud", zipfile.ZIP_DEFLATED),
            ("assets/ignored.txt", b"ignored", zipfile.ZIP_DEFLATED),
        ],
    )

    manifest = inspect_apk(apk)
    assert manifest.package == "org.example.archive"
    assert manifest.version_name == "2.0"
    assert manifest.version_code == 20

    entries = resolve_entries(apk, ("assets/data.bin",), ("assets/ui/*.txt",))
    assert entries == ["assets/data.bin", "assets/ui/hud.txt", "assets/ui/menu.txt"]

    destination = tmp_path / "extracted files with spaces"
    extracted = extract_entries(apk, entries, destination)
    assert extracted["assets/data.bin"].read_bytes() == b"core"
    assert extracted["assets/ui/hud.txt"].read_bytes() == b"hud"
    assert not (destination / "assets/ignored.txt").exists()


def test_resolve_entries_reports_missing_required_entry(tmp_path: Path, make_apk) -> None:
    apk = make_apk(tmp_path / "missing.apk")

    with pytest.raises(PatchError, match="missing required APK entries: assets/data.bin"):
        resolve_entries(apk, ("assets/data.bin",), ())


@pytest.mark.parametrize("entry", ["../outside.bin", "/absolute.bin", "safe/../../outside.bin"])
def test_extract_entries_refuses_path_traversal(
    tmp_path: Path, make_apk, entry: str
) -> None:
    apk = make_apk(
        tmp_path / "malicious.apk",
        entries=[(entry, b"must not escape", zipfile.ZIP_STORED)],
    )
    extraction_root = tmp_path / "safe extraction root"

    with pytest.raises(PatchError, match="unsafe APK entry path"):
        extract_entries(apk, [entry], extraction_root)

    assert not (tmp_path / "outside.bin").exists()
