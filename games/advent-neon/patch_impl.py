"""Experimental structural 4:3 patch for Advent Neon."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from android4x3.gamemaker import GameMakerPatch
from PIL import Image


_PATCH = GameMakerPatch(
    game_name="Advent Neon",
    entry="assets/game.droid",
    module_dir=Path(__file__).resolve().parent,
    temporary_prefix="advent-neon-umt-",
)
REQUIRED_ENTRIES = _PATCH.required_entries

_SPLASHES = {
    "assets/splash.png": (
        "6d8340c5fa35ee7947defc9e3f2e28167c842baab8814ea23991506ede2dce7a",
        (1024, 768),
        "RGB",
    ),
    "assets/portrait_splash.png": (
        "41d4675db796874e38dadf1be9f038ce3c3742cc5abcfdc891a966ba08aa32ca",
        (768, 1024),
        "RGBA",
    ),
}


def probe(extracted: dict[str, Path]) -> dict:
    return _PATCH.probe(extracted)


def _neutralized_splash(
    source: Path, expected: tuple[str, tuple[int, int], str]
) -> bytes | None:
    data = source.read_bytes()
    expected_hash, expected_size, expected_mode = expected
    if hashlib.sha256(data).hexdigest() != expected_hash:
        return None
    with Image.open(BytesIO(data)) as image:
        image.load()
        if image.size != expected_size or image.mode != expected_mode:
            return None
    color = (0, 0, 0, 255) if expected_mode == "RGBA" else (0, 0, 0)
    output = BytesIO()
    Image.new(expected_mode, expected_size, color).save(output, format="PNG")
    return output.getvalue()


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    replacements = _PATCH.apply(extracted, output_dir)
    for entry, expected in _SPLASHES.items():
        source = extracted.get(entry)
        if source is None or not Path(source).is_file():
            continue
        neutralized = _neutralized_splash(Path(source), expected)
        if neutralized is None:
            continue
        destination = Path(output_dir) / Path(entry).name
        destination.write_bytes(neutralized)
        replacements[entry] = destination
    return replacements
