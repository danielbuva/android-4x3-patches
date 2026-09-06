"""Install a pinned native test dependency; never downloads any game assets."""
from pathlib import Path
import os
import platform
import urllib.request
import zipfile


def main():
    system = platform.system()
    suffix = {"Darwin": "macos", "Windows": "windows"}[system]
    root = Path(os.environ["RUNNER_TEMP"]) / "GDRE tools with spaces"
    root.mkdir(parents=True, exist_ok=True)
    archive = root / "gdre.zip"
    url = f"https://github.com/GDRETools/gdsdecomp/releases/download/v2.6.4/GDRE_tools-v2.6.4-{suffix}.zip"
    urllib.request.urlretrieve(url, archive)
    with zipfile.ZipFile(archive) as packed:
        packed.extractall(root)
    if system == "Darwin":
        executable = root / "Godot RE Tools.app/Contents/MacOS/Godot RE Tools"
        executable.chmod(0o755)
    else:
        candidates = sorted(root.rglob("*.exe"))
        # Prefer the console executable if the release supplies one.
        executable = next((p for p in candidates if p.name.endswith("console.exe")),
                          next((p for p in candidates if "gdre" in p.name.lower()), None))
    if executable is None or not executable.is_file():
        raise RuntimeError("GDRE executable not found in release archive")
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as stream:
        stream.write(f"GDRE_TOOLS={executable}\n")
    print(f"Installed native GDRE: {executable}")


if __name__ == "__main__":
    main()
