from __future__ import annotations

import struct

import pytest

from android4x3.errors import PatchError
from android4x3.manifest import ManifestInfo, parse_manifest


def test_parse_text_manifest(text_manifest) -> None:
    result = parse_manifest(text_manifest("org.example.text", "7.5", 705))

    assert result == ManifestInfo(
        package="org.example.text",
        version_name="7.5",
        version_code=705,
    )


def test_text_manifest_invalid_numeric_version_is_non_blocking() -> None:
    manifest = b'''<?xml version="1.0"?>
    <manifest xmlns:android="http://schemas.android.com/apk/res/android"
      package="org.example.loose" android:versionName="preview"
      android:versionCode="not-a-number" />'''

    assert parse_manifest(manifest) == ManifestInfo(
        package="org.example.loose",
        version_name="preview",
        version_code=None,
    )


def test_parse_binary_manifest(binary_manifest) -> None:
    result = parse_manifest(binary_manifest("org.example.binary", "9.4.1", 941))

    assert result == ManifestInfo(
        package="org.example.binary",
        version_name="9.4.1",
        version_code=941,
    )


@pytest.mark.parametrize(
    "manifest, message",
    [
        (b"<?xml version=\"1.0\"?><manifest />", "no package"),
        (b"\x03\x00", "truncated"),
        (struct.pack("<HHI", 0x0004, 8, 8), "not recognized binary XML"),
    ],
)
def test_manifest_errors_are_explicit(manifest: bytes, message: str) -> None:
    with pytest.raises(PatchError, match=message):
        parse_manifest(manifest)


def test_binary_manifest_rejects_a_truncated_chunk(binary_manifest) -> None:
    manifest = bytearray(binary_manifest())
    struct.pack_into("<I", manifest, 12, len(manifest) + 4096)

    with pytest.raises(PatchError, match="malformed chunk"):
        parse_manifest(bytes(manifest))
