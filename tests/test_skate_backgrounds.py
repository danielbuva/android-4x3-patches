"""Optional art packer tests use invented archive members and solid textures."""
import importlib.util
import io
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module():
    spec = importlib.util.spec_from_file_location('skate_backgrounds',ROOT/'games/skate-3/backgrounds.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def archive():
    data = bytearray(256)
    data[:4] = b'EB\0\3'
    struct.pack_into('>IHB',data,4,1,0x10,6)
    struct.pack_into('>I',data,12,80)
    data[20:22] = bytes((32,32))
    struct.pack_into('>III',data,48,3,0,4)
    data[82:90] = b'test.bin'
    data[112:119] = b'example'
    data[192:196] = b'test'
    return data


def test_archive_directory_is_named_and_bounds_checked():
    m = module()
    data = archive()
    assert m.entries(data) == [('example/test.bin',48,64,192,0,4)]
    struct.pack_into('>I',data,48,1000)
    with pytest.raises(ValueError,match='outside'):
        m.entries(data)
    with pytest.raises(ValueError,match='version 3'):
        m.entries(b'nope')


def test_refpack_requires_exact_output_and_valid_backreferences():
    m = module()
    assert m.unpack_refpack(b'\x10\xfb\0\0\x04\xe0abcd\xfc',4) == b'abcd'
    with pytest.raises(ValueError,match='Incomplete'):
        m.unpack_refpack(b'\x10\xfb\0\0\x05\xe0abcd\xfc',5)
    with pytest.raises(ValueError,match='back-reference'):
        m.unpack_refpack(b'\x10\xfb\0\0\x03\0\0\xfc',3)


def texture():
    pytest.importorskip('PIL',minversion='12.0')
    from PIL import Image
    image = Image.new('RGBA',(64,64),(24,40,60,255))
    output = io.BytesIO()
    image.save(output,format='DDS',pixel_format='DXT5')
    raw = output.getvalue()[128:]
    raw = bytes(b for j in range(0,len(raw),2) for b in raw[j:j+2][::-1])
    # Linear Xenos textures pad each row to a 128-pixel pitch.
    padded = b''.join(raw[y*256:(y+1)*256]+bytes(256) for y in range(16))
    data = bytearray(0x200+8192)
    data[:16] = b'\x89RW4xb2\0\r\n\x1a\n\x01\x20\x04\0'
    struct.pack_into('>I',data,0x20,2)
    struct.pack_into('>I',data,0x30,0x100)
    struct.pack_into('>I',data,0x44,0x200)
    struct.pack_into('>6I',data,0x100,0,0,8192,4096,2,0x10031)
    struct.pack_into('>6I',data,0x118,0x140,0,52,4,6,0x200e8)
    struct.pack_into('>6I',data,0x140+28,0x01000002,0x54,63|(63<<13),0xd10,0,0x200)
    data[0x200:] = padded
    return bytes(data)


def test_art_replacement_changes_only_texture_payload_and_fetch():
    from PIL import Image
    m = module()
    original = texture()
    art = Image.new('RGB',(1280,960),(40,60,80))
    changed = m.replace_art(original,art,False)
    assert len(changed) == len(original)
    assert changed[:0x15c] == original[:0x15c]
    record, = m.texture_records(changed)
    assert record[4].size == (128,128)
    assert record[3][1]&63 == 18
    assert m.replace_art(changed,art,False) == changed
    with pytest.raises(ValueError,match='tile'):
        m.replace_art(original,art,True)


def test_build_refuses_missing_resources_without_changing_input():
    m = module()
    original = archive()
    snapshot = bytes(original)
    with pytest.raises(ValueError,match='missing'):
        m.build(original,None,None)
    assert bytes(original) == snapshot
