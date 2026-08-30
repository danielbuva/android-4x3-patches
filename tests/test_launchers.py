from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_powershell_launcher_forwards_native_argument_array() -> None:
    launcher = (REPO_ROOT / "patch.ps1").read_text(encoding="utf-8")

    assert 'Join-Path $Repository ".venv\\Scripts\\python.exe"' in launcher
    assert '(Join-Path $Repository "patch.py") @args' in launcher
    assert "exit $LASTEXITCODE" in launcher
