from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from android4x3 import cli
from android4x3.errors import PatchError
from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_ENTRY = "assets/patch state.bin"


def _simple_repack(
    _repo: Path,
    input_apk: Path,
    output_apk: Path,
    replacements: dict[str, Path],
) -> None:
    output_apk.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(input_apk, "r") as source, zipfile.ZipFile(output_apk, "w") as output:
        output.comment = source.comment
        for info in source.infolist():
            data = replacements[info.filename].read_bytes() if info.filename in replacements else source.read(info)
            output.writestr(info, data)


def _simple_align(unsigned: Path, aligned: Path) -> None:
    shutil.copy2(unsigned, aligned)


def test_cli_handles_paths_with_spaces_end_to_end(
    tmp_path: Path,
    make_synthetic_game,
    make_apk,
    text_manifest,
    monkeypatch,
    capsys,
) -> None:
    repo = tmp_path / "repository with spaces"
    make_synthetic_game(repo)
    input_apk = make_apk(
        tmp_path / "user supplied APKs" / "Synthetic Game original.apk",
        manifest=text_manifest("example.synthetic.game", "1.0 test", 10),
        entries=[(SYNTHETIC_ENTRY, b"ORIGINAL", zipfile.ZIP_STORED)],
    )
    output_apk = tmp_path / "patched output with spaces" / "Synthetic Game 4x3.apk"
    monkeypatch.setattr(cli, "_repo_root", lambda: repo)
    monkeypatch.setattr(cli, "repack_with_optional_branding", _simple_repack)
    monkeypatch.setattr(cli, "align_apk", _simple_align)
    monkeypatch.setattr(cli, "verify_alignment", lambda _apk: None)

    status = cli.run(
        [
            str(input_apk),
            "--output",
            str(output_apk),
            "--unsigned",
        ]
    )

    assert status == 0
    assert output_apk.is_file()
    with zipfile.ZipFile(output_apk) as output:
        assert output.read(SYNTHETIC_ENTRY) == b"PATCHED"
    report = capsys.readouterr().out
    assert "Game detected: Synthetic Game" in report
    assert str(output_apk.resolve()) in report


@pytest.mark.parametrize("state", ["original", "patched", "unsupported", "ambiguous"])
def test_probe_state_convention_accepts_all_public_states(state: str) -> None:
    result = cli._normalize_probe({"state": state})

    assert result == {"state": state, "targets": []}


@pytest.mark.parametrize("result", [None, [], "original", {"state": "partial"}])
def test_probe_state_convention_rejects_invalid_results(result) -> None:
    with pytest.raises(PatchError, match="probe did not return|invalid state"):
        cli._normalize_probe(result)


def test_cli_refuses_ambiguous_targets(
    tmp_path: Path,
    make_synthetic_game,
    make_apk,
    text_manifest,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    make_synthetic_game(repo)
    apk = make_apk(
        tmp_path / "ambiguous.apk",
        manifest=text_manifest("example.synthetic.game"),
        entries=[(SYNTHETIC_ENTRY, b"ORIGINAL|PATCHED", zipfile.ZIP_STORED)],
    )
    monkeypatch.setattr(cli, "_repo_root", lambda: repo)

    with pytest.raises(PatchError, match="Synthetic Game: ambiguous") as failure:
        cli.run([str(apk), "--check"])

    assert failure.value.report["state"] == "ambiguous"
    assert failure.value.report["targets"][0]["state"] == "ambiguous"


def test_baba_is_you_requires_experimental_opt_in(
    tmp_path: Path,
    make_apk,
    text_manifest,
) -> None:
    registry = Registry(REPO_ROOT / "games")
    baba = registry.by_id["baba-is-you"]
    assert baba.experimental is True
    assert baba.output_name == "Baba-Is-You-experimental-4x3.apk"

    apk = make_apk(
        tmp_path / "Baba Is You.apk",
        manifest=text_manifest("org.hempuli.baba", "617.0", 617),
        entries=[
            ("lib/arm64-v8a/libChowdren.so", b"synthetic-not-game-code", zipfile.ZIP_STORED)
        ],
    )

    with pytest.raises(PatchError, match="support is experimental.*--allow-experimental"):
        cli.run([str(apk), "--check"])


def test_game_module_runtime_errors_become_stable_patch_errors(
    tmp_path: Path, make_synthetic_game
) -> None:
    repo = tmp_path / "repo"
    make_synthetic_game(repo)
    config = Registry(repo / "games").by_id["synthetic-game"]

    def fail() -> None:
        raise RuntimeError("synthetic module failure")

    with pytest.raises(
        PatchError,
        match="Synthetic Game: patch application failed: synthetic module failure",
    ):
        cli._invoke_game(config, "patch application", fail)


def test_missing_preferred_entry_falls_back_to_semantic_glob_scan(
    tmp_path: Path, make_apk, text_manifest, monkeypatch, capsys
) -> None:
    repo = tmp_path / "repo"
    game = repo / "games" / "fallback-game"
    game.mkdir(parents=True)
    (game / "config.json").write_text(
        json.dumps(
            {
                "id": "fallback-game",
                "display_name": "Fallback Game",
                "package_names": ["org.example.fallback"],
                "status": "verified",
                "required_entries": ["assets/core.bin"],
                "preferred_entries": ["assets/bundles/tested-name.bin"],
                "entry_globs": ["assets/bundles/*.bin"],
            }
        ),
        encoding="utf-8",
    )
    (game / "patch_impl.py").write_text(
        "from pathlib import Path\n"
        "REQUIRED_ENTRIES = ('assets/core.bin',)\n"
        "TARGET = 'assets/bundles/revision-name.bin'\n"
        "def probe(extracted):\n"
        "    target = extracted.get(TARGET)\n"
        "    if target is None: return {'state': 'unsupported'}\n"
        "    return {'state': Path(target).read_text(), 'targets': [TARGET]}\n"
        "def apply(extracted, output_dir): return {}\n",
        encoding="utf-8",
    )
    apk = make_apk(
        tmp_path / "fallback.apk",
        manifest=text_manifest("org.example.fallback"),
        entries=[
            ("assets/core.bin", b"core", zipfile.ZIP_STORED),
            ("assets/bundles/revision-name.bin", b"patched", zipfile.ZIP_STORED),
        ],
    )
    monkeypatch.setattr(cli, "_repo_root", lambda: repo)

    assert cli.run(["--check", "--json", str(apk)]) == 0

    assert json.loads(capsys.readouterr().out)["state"] == "patched"


def test_main_emits_machine_readable_json_for_failures(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    missing = tmp_path / "missing.apk"
    monkeypatch.setattr(cli.sys, "argv", ["patch.py", "--json", str(missing)])

    with pytest.raises(SystemExit) as stopped:
        cli.main()

    assert stopped.value.code == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["status"] == "error"
    assert "input APK not found" in payload["error"]


def test_check_rejects_corrupt_unrelated_apk_entry(
    tmp_path: Path, make_apk, text_manifest
) -> None:
    apk = make_apk(
        tmp_path / "corrupt.apk",
        manifest=text_manifest("unsupported.package"),
        entries=[("assets/unrelated.bin", b"uncorrupted", zipfile.ZIP_STORED)],
    )
    data = bytearray(apk.read_bytes())
    marker = data.index(b"uncorrupted")
    data[marker] ^= 0x01
    apk.write_bytes(data)

    with pytest.raises(PatchError, match="CRC verification failed"):
        cli.run(["--check", str(apk)])


@pytest.fixture
def game_data_case(tmp_path, make_synthetic_game, make_apk, text_manifest, monkeypatch):
    repo = tmp_path/'repo'
    game = make_synthetic_game(repo)
    source = game/'patch_impl.py'
    source.write_text(source.read_text()+'''

def probe_game_data(data):
    return {"state": _state(data)}

def patch_game_data(data):
    return b"PATCHED"
''')
    apk = make_apk(tmp_path/'original.apk',manifest=text_manifest('example.synthetic.game'),
                   entries=[(SYNTHETIC_ENTRY,b'ORIGINAL',zipfile.ZIP_STORED)])
    data = tmp_path/'fedynamic.big'
    data.write_bytes(b'ORIGINAL')
    output = tmp_path/'result.apk'
    monkeypatch.setattr(cli,'_repo_root',lambda:repo)
    monkeypatch.setattr(cli,'repack_with_optional_branding',_simple_repack)
    monkeypatch.setattr(cli,'align_apk',_simple_align)
    monkeypatch.setattr(cli,'verify_alignment',lambda _:None)
    return apk,data,output,source


def test_cli_game_data_check_and_build_preserve_inputs(game_data_case,capsys):
    apk,data,output,_ = game_data_case
    args = [str(apk),'--game-data',str(data),'--output',str(output),'--json']
    assert cli.run([*args,'--check']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['game_data']['state'] == 'original'
    assert not output.exists()
    assert cli.run([*args,'--unsigned']) == 0
    report = json.loads(capsys.readouterr().out)
    artifact = Path(report['game_data']['output'])
    assert artifact == output.with_name('result-fedynamic.big')
    assert artifact.read_bytes() == b'PATCHED'
    assert data.read_bytes() == b'ORIGINAL'
    assert report['game_data']['post_state'] == 'patched'
    with zipfile.ZipFile(apk) as original:
        assert original.read(SYNTHETIC_ENTRY) == b'ORIGINAL'


@pytest.mark.parametrize('destination',['source','apk','output'])
def test_cli_game_data_rejects_colliding_paths_even_with_force(game_data_case,destination):
    apk,data,output,_ = game_data_case
    collision = {'source':data,'apk':apk,'output':output}[destination]
    with pytest.raises(PatchError,match='paths must all differ'):
        cli.run([str(apk),'--game-data',str(data),'--game-data-output',str(collision),
                 '--output',str(output),'--force','--unsigned'])
    assert data.read_bytes() == b'ORIGINAL'
    assert not output.exists()


def test_cli_game_data_unknown_input_or_failed_post_check_publishes_nothing(game_data_case):
    apk,data,output,source = game_data_case
    args = [str(apk),'--game-data',str(data),'--output',str(output),'--unsigned']
    data.write_bytes(b'unknown')
    with pytest.raises(PatchError,match='not recognized'):
        cli.run(args)
    data.write_bytes(b'ORIGINAL')
    source.write_text(source.read_text().replace('return b"PATCHED"','return b"broken"'))
    with pytest.raises(PatchError,match='post-patch verification'):
        cli.run(args)
    assert not output.exists()
    assert not output.with_name('result-fedynamic.big').exists()


def test_cli_game_data_refuses_existing_archive_output(game_data_case):
    apk,data,output,_ = game_data_case
    archive = output.with_name('result-fedynamic.big')
    archive.write_bytes(b'keep me')
    with pytest.raises(PatchError,match='game-data output exists'):
        cli.run([str(apk),'--game-data',str(data),'--output',str(output),'--unsigned'])
    assert archive.read_bytes() == b'keep me'
    assert not output.exists()
