"""FAITH GameMaker patch module."""

from __future__ import annotations

from pathlib import Path

from android4x3.gamemaker import GameMakerPatch


_PATCH = GameMakerPatch(
    game_name="FAITH",
    entry="assets/game.droid",
    module_dir=Path(__file__).resolve().parent,
    temporary_prefix="faith-umt-",
)
REQUIRED_ENTRIES = _PATCH.required_entries


def probe(extracted: dict[str, Path]) -> dict:
    return _PATCH.probe(extracted)


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    return _PATCH.apply(extracted, output_dir)
