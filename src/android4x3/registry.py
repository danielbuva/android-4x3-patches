"""Discovery and loading of data-driven game modules."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from .errors import PatchError


@dataclasses.dataclass(frozen=True)
class GameConfig:
    id: str
    display_name: str
    package_names: tuple[str, ...]
    engine: str
    status: str
    output_name: str
    required_entries: tuple[str, ...]
    tested_versions: tuple[str, ...]
    preferred_entries: tuple[str, ...]
    entry_globs: tuple[str, ...]
    directory: Path

    @property
    def experimental(self) -> bool:
        return self.status == "experimental"


class Registry:
    def __init__(self, games_dir: Path):
        self.games_dir = games_dir
        self.games: list[GameConfig] = []
        self.by_package: dict[str, GameConfig] = {}
        self.by_id: dict[str, GameConfig] = {}
        self._load()

    def _coerce_status(self, raw: dict, config_path: Path, game_id: str) -> str:
        status = raw.get("status")
        experimental = raw.get("experimental")

        if status is None:
            if experimental is None:
                return "verified"
            if not isinstance(experimental, bool):
                raise PatchError(
                    f"{config_path}: experimental must be boolean when status is omitted"
                )
            return "experimental" if experimental else "verified"

        if not isinstance(status, str) or not status.strip():
            raise PatchError(f"{config_path}: status must be a non-empty string")
        status = status.strip()
        if status not in {"verified", "experimental"}:
            raise PatchError(
                f"{config_path}: status must be one of verified or experimental"
            )
        if experimental is not None and not isinstance(experimental, bool):
            raise PatchError(
                f"{config_path}: experimental must be boolean"
            )
        if experimental is not None and experimental != (status == "experimental"):
            raise PatchError(
                f"{config_path}: status and experimental are inconsistent for {game_id}"
            )
        return status

    def _coerce_string_list(
        self,
        config_path: Path,
        values,
        label: str,
        *,
        allow_empty: bool = False,
    ) -> tuple[str, ...]:
        if not isinstance(values, list):
            raise PatchError(f"{config_path}: {label} must be a list")
        if not values and not allow_empty:
            raise PatchError(
                f"{config_path}: {label} must be a non-empty list of non-empty strings"
            )
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise PatchError(
                f"{config_path}: {label} must be a non-empty list of non-empty strings"
            )
        normalized = tuple(value.strip() for value in values)
        if not allow_empty and not normalized:
            raise PatchError(
                f"{config_path}: {label} must be a non-empty list of non-empty strings"
            )
        return normalized

    def _coerce_output_name(self, config_path: Path, raw_name: object, game_id: str) -> str:
        output_name = (
            str(raw_name)
            if raw_name is not None
            else f"{game_id}-4x3.apk"
        )
        output_name = output_name.strip()
        if not output_name:
            raise PatchError(f"{config_path}: output_name must be non-empty")
        if (
            output_name in {".", ".."}
            or "/" in output_name
            or "\\" in output_name
            or ":" in output_name
            or Path(output_name).is_absolute()
            or Path(output_name).name != output_name
        ):
            raise PatchError(
                f"{config_path}: output_name must be a plain filename"
            )
        lower_name = output_name.lower()
        if not lower_name.endswith(".apk"):
            raise PatchError(
                f"{config_path}: output_name must end with .apk"
            )
        return output_name

    def _load(self) -> None:
        for config_path in sorted(self.games_dir.glob("*/config.json")):
            try:
                raw = json.loads(config_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise PatchError(f"cannot load {config_path}: {exc}") from exc
            game_id = str(raw.get("id") or raw.get("name") or config_path.parent.name)
            packages = raw.get("package_names")
            if packages is None and raw.get("package"):
                packages = [raw["package"]]
            if not isinstance(packages, list) or not packages or not all(isinstance(p, str) for p in packages):
                raise PatchError(f"{config_path}: package_names must be a non-empty string list")
            tested = raw.get("tested_versions")
            if tested is None and raw.get("version") is not None:
                tested = [str(raw["version"])]
            if tested is None:
                tested = ["unknown"]
            status = self._coerce_status(raw, config_path, game_id)
            output_name = self._coerce_output_name(config_path, raw.get("output_name"), game_id)
            config = GameConfig(
                id=game_id,
                display_name=str(raw.get("display_name") or game_id),
                package_names=tuple(packages),
                engine=str(raw.get("engine") or "unknown"),
                status=status,
                output_name=output_name,
                required_entries=self._coerce_string_list(
                    config_path,
                    raw.get("required_entries", []),
                    "required_entries",
                    allow_empty=True,
                ),
                tested_versions=self._coerce_string_list(
                    config_path, tested, "tested_versions"
                ),
                preferred_entries=tuple(str(item) for item in raw.get("preferred_entries", [])),
                entry_globs=tuple(str(item) for item in raw.get("entry_globs", [])),
                directory=config_path.parent,
            )
            if game_id in self.by_id:
                raise PatchError(f"duplicate game id: {game_id}")
            for package in config.package_names:
                if package in self.by_package:
                    raise PatchError(f"duplicate package registration: {package}")
                self.by_package[package] = config
            self.by_id[game_id] = config
            self.games.append(config)

    def module(self, config: GameConfig) -> ModuleType:
        path = config.directory / "patch_impl.py"
        if not path.is_file():
            raise PatchError(f"{config.display_name}: missing patch_impl.py")
        name = "android4x3_game_" + config.id.replace("-", "_")
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise PatchError(f"cannot load game module: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(name, None)
            raise
        for required in ("REQUIRED_ENTRIES", "probe", "apply"):
            if not hasattr(module, required):
                raise PatchError(f"{path}: missing required export {required}")
        module_entries = tuple(str(value) for value in module.REQUIRED_ENTRIES)
        if module_entries != config.required_entries:
            raise PatchError(
                f"{path}: REQUIRED_ENTRIES does not match config.json required_entries"
            )
        return module
