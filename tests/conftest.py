"""Proprietary-free fixtures for the patching framework tests."""

from __future__ import annotations

import json
import struct
import sys
import zipfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


ANDROID_NAMESPACE = "http://schemas.android.com/apk/res/android"


def _text_manifest(
    package: str = "example.synthetic.game",
    version_name: str = "1.2.3",
    version_code: int = 123,
) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<manifest xmlns:android="{ANDROID_NAMESPACE}" '
        f'package="{package}" android:versionName="{version_name}" '
        f'android:versionCode="{version_code}" />'
    ).encode("utf-8")


def _short_u8_length(value: int) -> bytes:
    if not 0 <= value < 0x80:
        raise ValueError("test string is too long for the compact fixture encoder")
    return bytes((value,))


def _binary_manifest(
    package: str = "example.synthetic.game",
    version_name: str = "1.2.3",
    version_code: int = 123,
) -> bytes:
    """Build the smallest binary Android XML manifest accepted by the reader."""

    strings = [
        "manifest",
        "package",
        package,
        "versionName",
        version_name,
        "versionCode",
        ANDROID_NAMESPACE,
    ]
    encoded = bytearray()
    offsets: list[int] = []
    for value in strings:
        raw = value.encode("utf-8")
        offsets.append(len(encoded))
        encoded.extend(_short_u8_length(len(value)))
        encoded.extend(_short_u8_length(len(raw)))
        encoded.extend(raw)
        encoded.append(0)
    while len(encoded) % 4:
        encoded.append(0)

    pool_header_size = 28
    strings_start = pool_header_size + len(offsets) * 4
    pool_size = strings_start + len(encoded)
    pool = bytearray(
        struct.pack("<HHI", 0x0001, pool_header_size, pool_size)
        + struct.pack("<IIIII", len(offsets), 0, 0x100, strings_start, 0)
    )
    pool.extend(struct.pack(f"<{len(offsets)}I", *offsets))
    pool.extend(encoded)

    def attribute(name_index: int, raw_index: int, value_type: int, data: int) -> bytes:
        return struct.pack(
            "<IIIHBBI",
            0xFFFFFFFF,
            name_index,
            raw_index,
            8,
            0,
            value_type,
            data,
        )

    attributes = b"".join(
        (
            attribute(1, 2, 0x03, 2),
            attribute(3, 4, 0x03, 4),
            attribute(5, 0xFFFFFFFF, 0x10, version_code),
        )
    )
    start_size = 36 + len(attributes)
    start = bytearray(struct.pack("<HHI", 0x0102, 36, start_size))
    start.extend(struct.pack("<II", 1, 0xFFFFFFFF))
    start.extend(struct.pack("<II", 0xFFFFFFFF, 0))
    start.extend(struct.pack("<HHHHHH", 20, 20, 3, 0, 0, 0))
    start.extend(attributes)

    root_size = 8 + len(pool) + len(start)
    return struct.pack("<HHI", 0x0003, 8, root_size) + bytes(pool) + bytes(start)


def _make_apk(
    path: Path,
    *,
    manifest: bytes | None = None,
    entries: list[tuple[str, bytes, int]] | None = None,
    comment: bytes = b"",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.comment = comment
        archive.writestr(
            "AndroidManifest.xml",
            manifest if manifest is not None else _text_manifest(),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        for name, data, compression in entries or []:
            archive.writestr(name, data, compress_type=compression)
    return path


SYNTHETIC_MODULE = '''\
from pathlib import Path

ENTRY = "assets/patch state.bin"
REQUIRED_ENTRIES = (ENTRY,)

def _state(data):
    if data == b"ORIGINAL":
        return "original"
    if data == b"PATCHED":
        return "patched"
    if data == b"ORIGINAL|PATCHED":
        return "ambiguous"
    return "unsupported"

def probe(extracted):
    path = extracted.get(ENTRY)
    if path is None:
        return {"state": "unsupported", "targets": [{"name": ENTRY, "state": "unsupported"}]}
    state = _state(Path(path).read_bytes())
    return {"state": state, "targets": [{"name": "synthetic marker", "state": state}]}

def apply(extracted, output_dir):
    state = probe(extracted)["state"]
    if state == "patched":
        return {}
    if state != "original":
        raise RuntimeError("synthetic target is not uniquely patchable")
    destination = Path(output_dir) / "replacement with spaces.bin"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"PATCHED")
    return {ENTRY: destination}
'''


def _make_synthetic_game(
    repo: Path,
    *,
    game_id: str = "synthetic-game",
    display_name: str = "Synthetic Game",
    package: str = "example.synthetic.game",
    status: str = "verified",
) -> Path:
    game = repo / "games" / game_id
    game.mkdir(parents=True, exist_ok=True)
    config = {
        "id": game_id,
        "display_name": display_name,
        "package_names": [package],
        "engine": "Synthetic",
        "status": status,
        "output_name": f"{game_id}-4x3.apk",
        "tested_versions": ["test-only"],
        "entry_globs": [],
    }
    (game / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (game / "patch_impl.py").write_text(SYNTHETIC_MODULE, encoding="utf-8")
    return game


@pytest.fixture
def text_manifest():
    return _text_manifest


@pytest.fixture
def binary_manifest():
    return _binary_manifest


@pytest.fixture
def make_apk():
    return _make_apk


@pytest.fixture
def make_synthetic_game():
    return _make_synthetic_game
