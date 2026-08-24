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
            tested = raw.get("tested_versions") or ([str(raw["version"])] if raw.get("version") else [])
            config = GameConfig(
                id=game_id,
                display_name=str(raw.get("display_name") or game_id),
                package_names=tuple(packages),
                engine=str(raw.get("engine") or "unknown"),
                status=str(raw.get("status") or "verified"),
                output_name=str(raw.get("output_name") or f"{game_id}-4x3.apk"),
                tested_versions=tuple(str(item) for item in tested),
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
        return module
