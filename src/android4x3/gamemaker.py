"""Shared UndertaleModCli orchestration for GameMaker patch modules."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def find_undertale_mod_cli() -> Path | None:
    """Find a user-supplied UndertaleModCli without imposing a version gate."""

    for variable in ("ANDROID_4X3_UMT", "UMT_CLI"):
        value = os.environ.get(variable)
        if value:
            candidate = Path(value).expanduser().resolve()
            if candidate.is_file() and (
                os.name == "nt" or os.access(candidate, os.X_OK)
            ):
                return candidate
    for name in ("UndertaleModCli", "UndertaleModCli.exe"):
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved).resolve()
    return None


def run_undertale_script(
    executable: Path,
    archive: Path,
    script: Path,
    output: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one structural script with all output captured for deterministic CLI use."""

    command = [
        str(executable),
        "load",
        str(archive),
        "--scripts",
        str(script),
    ]
    if output is not None:
        command.extend(("--output", str(output)))
    return subprocess.run(
        command,
        cwd=executable.parent,
        check=False,
        capture_output=True,
        text=True,
    )


def undertale_failure(result: subprocess.CompletedProcess[str]) -> str:
    """Return one useful, stable line from a failed CLI invocation."""

    lines = [
        line.strip()
        for line in (result.stderr + "\n" + result.stdout).splitlines()
        if line.strip()
    ]
    return (
        lines[-1]
        if lines
        else f"UndertaleModCli exited with status {result.returncode}"
    )


@dataclass(frozen=True)
class GameMakerPatch:
    """Structural original/patched detection and verified archive mutation."""

    game_name: str
    entry: str
    module_dir: Path
    temporary_prefix: str

    @property
    def required_entries(self) -> tuple[str, ...]:
        return (self.entry,)

    def _source(self, extracted: dict[str, Path]) -> Path | None:
        value = extracted.get(self.entry)
        if value is None:
            return None
        path = Path(value)
        return path if path.is_file() else None

    def _script(self, name: str) -> Path:
        return self.module_dir / name

    def probe(self, extracted: dict[str, Path]) -> dict:
        archive = self._source(extracted)
        target = {
            "entry": self.entry,
            "kind": "GameMaker archive",
            "state": "unsupported",
        }
        if archive is None:
            return {
                "state": "unsupported",
                "targets": [target],
                "detail": f"missing required entry: {self.entry}",
            }

        executable = find_undertale_mod_cli()
        if executable is None:
            return {
                "state": "unsupported",
                "targets": [target],
                "detail": (
                    "UndertaleModCli is required; set ANDROID_4X3_UMT "
                    "or add it to PATH"
                ),
                "tool_missing": "UndertaleModCli",
            }

        patched = run_undertale_script(
            executable, archive, self._script("verify.csx")
        )
        original = run_undertale_script(
            executable, archive, self._script("original_verify.csx")
        )
        patched_ok = patched.returncode == 0
        original_ok = original.returncode == 0
        if patched_ok and original_ok:
            target["state"] = "ambiguous"
            return {
                "state": "ambiguous",
                "targets": [target],
                "detail": (
                    "archive matches both original and patched structural states"
                ),
            }
        if patched_ok:
            target["state"] = "patched"
            return {"state": "patched", "targets": [target]}
        if original_ok:
            target["state"] = "original"
            return {"state": "original", "targets": [target]}
        return {
            "state": "unsupported",
            "targets": [target],
            "detail": (
                f"required {self.game_name} GameMaker structures were not recognized"
            ),
            "diagnostic": undertale_failure(original),
        }

    def apply(
        self,
        extracted: dict[str, Path],
        output_dir: Path,
    ) -> dict[str, Path]:
        archive = self._source(extracted)
        if archive is None:
            raise RuntimeError(f"missing required entry: {self.entry}")
        executable = find_undertale_mod_cli()
        if executable is None:
            raise RuntimeError(
                "UndertaleModCli is required; set ANDROID_4X3_UMT or add it to PATH"
            )

        state = self.probe(extracted)
        if state["state"] not in {"original", "patched"}:
            raise RuntimeError(
                state.get("detail", f"unsupported {self.game_name} archive")
            )

        destination_dir = Path(output_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / Path(self.entry).name
        with tempfile.TemporaryDirectory(
            prefix=self.temporary_prefix,
            dir=destination_dir,
        ) as temporary:
            staged = Path(temporary) / Path(self.entry).name
            if state["state"] == "patched":
                shutil.copy2(archive, staged)
            else:
                result = run_undertale_script(
                    executable,
                    archive,
                    self._script("patch.csx"),
                    staged,
                )
                if result.returncode != 0 or not staged.is_file():
                    raise RuntimeError(
                        f"{self.game_name} patch failed: {undertale_failure(result)}"
                    )

            verified = run_undertale_script(
                executable, staged, self._script("verify.csx")
            )
            if verified.returncode != 0:
                raise RuntimeError(
                    f"{self.game_name} post-patch verification failed: "
                    f"{undertale_failure(verified)}"
                )
            os.replace(staged, destination)
        return {self.entry: destination}


__all__ = [
    "GameMakerPatch",
    "find_undertale_mod_cli",
    "run_undertale_script",
    "undertale_failure",
]
