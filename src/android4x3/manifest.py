"""Small, strict reader for package/version metadata in Android binary XML."""

from __future__ import annotations

import dataclasses
import struct
from typing import Iterator

from .errors import PatchError


RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
RES_XML_START_ELEMENT_TYPE = 0x0102
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10


@dataclasses.dataclass(frozen=True)
class ManifestInfo:
    package: str
    version_name: str | None = None
    version_code: int | None = None


def _u8_length(data: bytes, offset: int, limit: int) -> tuple[int, int]:
    if offset >= limit:
        raise PatchError("truncated UTF-8 string length in AndroidManifest.xml")
    first = data[offset]
    if first & 0x80:
        if offset + 1 >= limit:
            raise PatchError("truncated UTF-8 string length in AndroidManifest.xml")
        return ((first & 0x7F) << 8) | data[offset + 1], offset + 2
    return first, offset + 1


def _u16_length(data: bytes, offset: int, limit: int) -> tuple[int, int]:
    if offset + 2 > limit:
        raise PatchError("truncated UTF-16 string length in AndroidManifest.xml")
    first = struct.unpack_from("<H", data, offset)[0]
    if first & 0x8000:
        if offset + 4 > limit:
            raise PatchError("truncated UTF-16 string length in AndroidManifest.xml")
        second = struct.unpack_from("<H", data, offset + 2)[0]
        return ((first & 0x7FFF) << 16) | second, offset + 4
    return first, offset + 2


def _chunks(data: bytes, start: int, end: int) -> Iterator[tuple[int, int, int]]:
    offset = start
    while offset + 8 <= end:
        chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", data, offset)
        if header_size < 8 or chunk_size < header_size or offset + chunk_size > end:
            raise PatchError("malformed chunk in AndroidManifest.xml")
        yield chunk_type, offset, chunk_size
        offset += chunk_size
    if offset != end:
        raise PatchError("trailing bytes in AndroidManifest.xml")


def _string_pool(data: bytes, offset: int, chunk_size: int) -> list[str]:
    if offset + 28 > len(data):
        raise PatchError("truncated Android string pool")
    _, header_size, _ = struct.unpack_from("<HHI", data, offset)
    if header_size < 28:
        raise PatchError("invalid Android string-pool header")
    count, style_count, flags, strings_start, _styles_start = struct.unpack_from(
        "<IIIII", data, offset + 8
    )
    offsets_start = offset + header_size
    offsets_end = offsets_start + count * 4
    if offsets_end + style_count * 4 > offset + chunk_size:
        raise PatchError("invalid Android string-pool offsets")
    base = offset + strings_start
    limit = offset + chunk_size
    is_utf8 = bool(flags & 0x100)
    result: list[str] = []
    for index in range(count):
        relative = struct.unpack_from("<I", data, offsets_start + index * 4)[0]
        cursor = base + relative
        if cursor >= limit:
            raise PatchError("Android string-pool entry points outside its chunk")
        if is_utf8:
            _characters, cursor = _u8_length(data, cursor, limit)
            byte_count, cursor = _u8_length(data, cursor, limit)
            if cursor + byte_count > limit:
                raise PatchError("truncated UTF-8 Android string")
            result.append(data[cursor : cursor + byte_count].decode("utf-8", "strict"))
        else:
            characters, cursor = _u16_length(data, cursor, limit)
            byte_count = characters * 2
            if cursor + byte_count > limit:
                raise PatchError("truncated UTF-16 Android string")
            result.append(data[cursor : cursor + byte_count].decode("utf-16le", "strict"))
    return result


def _string(strings: list[str], index: int) -> str | None:
    if index == 0xFFFFFFFF:
        return None
    if not 0 <= index < len(strings):
        raise PatchError("AndroidManifest.xml references an invalid string index")
    return strings[index]


def parse_manifest(data: bytes) -> ManifestInfo:
    if data.startswith(b"<?xml"):
        # Plain-text manifests are uncommon in APKs but useful for tests and custom builds.
        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise PatchError(f"invalid text AndroidManifest.xml: {exc}") from exc
        package = root.attrib.get("package")
        if not package:
            raise PatchError("AndroidManifest.xml has no package attribute")
        android = "{http://schemas.android.com/apk/res/android}"
        raw_code = root.attrib.get(android + "versionCode")
        try:
            code = int(raw_code) if raw_code is not None else None
        except ValueError:
            code = None
        return ManifestInfo(package, root.attrib.get(android + "versionName"), code)

    if len(data) < 8:
        raise PatchError("AndroidManifest.xml is truncated")
    root_type, header_size, root_size = struct.unpack_from("<HHI", data, 0)
    if root_type != RES_XML_TYPE or header_size != 8 or root_size > len(data):
        raise PatchError("AndroidManifest.xml is not recognized binary XML")

    chunks = list(_chunks(data, 8, root_size))
    pools = [chunk for chunk in chunks if chunk[0] == RES_STRING_POOL_TYPE]
    if len(pools) != 1:
        raise PatchError("AndroidManifest.xml must contain one string pool")
    _, pool_offset, pool_size = pools[0]
    strings = _string_pool(data, pool_offset, pool_size)

    for chunk_type, offset, chunk_size in chunks:
        if chunk_type != RES_XML_START_ELEMENT_TYPE:
            continue
        if chunk_size < 36:
            raise PatchError("truncated start element in AndroidManifest.xml")
        name_index = struct.unpack_from("<I", data, offset + 20)[0]
        if _string(strings, name_index) != "manifest":
            continue
        attribute_start, attribute_size, attribute_count = struct.unpack_from(
            "<HHH", data, offset + 24
        )
        if attribute_size < 20:
            raise PatchError("invalid manifest attribute size")
        first = offset + 16 + attribute_start
        attributes: dict[str, str | int] = {}
        for index in range(attribute_count):
            attr = first + index * attribute_size
            if attr + 20 > offset + chunk_size:
                raise PatchError("truncated manifest attribute")
            _namespace, attr_name, raw_value = struct.unpack_from("<III", data, attr)
            value_size, _zero, value_type, value_data = struct.unpack_from("<HBBI", data, attr + 12)
            if value_size != 8:
                raise PatchError("invalid typed value in AndroidManifest.xml")
            name = _string(strings, attr_name)
            if name is None:
                continue
            raw = _string(strings, raw_value)
            if raw is not None:
                attributes[name] = raw
            elif value_type == TYPE_STRING:
                value = _string(strings, value_data)
                if value is not None:
                    attributes[name] = value
            elif value_type == TYPE_INT_DEC:
                attributes[name] = value_data
        package = attributes.get("package")
        if not isinstance(package, str) or not package:
            raise PatchError("AndroidManifest.xml has no package attribute")
        version_name = attributes.get("versionName")
        version_code = attributes.get("versionCode")
        return ManifestInfo(
            package=package,
            version_name=version_name if isinstance(version_name, str) else None,
            version_code=version_code if isinstance(version_code, int) else None,
        )
    raise PatchError("AndroidManifest.xml has no manifest start element")
