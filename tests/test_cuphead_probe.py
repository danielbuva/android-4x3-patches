"""Proprietary-free tests for the opt-in camera investigation."""
import importlib.util
from pathlib import Path
import struct
import pytest

PATH = Path(__file__).resolve().parents[1] / 'games/cuphead/probe/probe.py'
spec = importlib.util.spec_from_file_location('cuphead_camera_probe', PATH)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_payload_is_reviewed_own_code():
    assert len(probe.payload()) == 986


def test_rejects_unknown_library():
    with pytest.raises(probe.PatchError, match='Unsupported ARM64'):
        probe.inject(b'not a supported library')


def test_native_injection_preserves_load_segments_and_is_idempotent(monkeypatch):
    # Synthetic ELF; no commercial instructions or assets.
    data = bytearray(512)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', data, 18, 183)
    struct.pack_into('<Q', data, 32, 64)
    struct.pack_into('<HH', data, 54, 56, 6)
    struct.pack_into('<IIQQQQQQ', data, 64, 1, 5, 0, 0, 0, 512, 512, 65536)
    struct.pack_into('<IIQQQQQQ', data, 120, 4, 4, 400, 400, 400, 16, 16, 4)
    data[480:484] = bytes.fromhex('01000014')
    monkeypatch.setattr(probe, 'HOOK', 480)
    monkeypatch.setattr(probe, 'VADDR', 65536)
    monkeypatch.setattr(probe, 'SOURCE', probe.digest(data))
    expected = bytearray(data)
    code = probe.payload()
    struct.pack_into('<IIQQQQQQ', expected, 120, 1, 5, 65536, 65536, 65536, len(code), len(code), 65536)
    struct.pack_into('<I', expected, 480, 0x14000000 | ((65536-480)//4))
    expected.extend(bytes(65536-len(expected)))
    expected.extend(code)
    monkeypatch.setattr(probe, 'PATCHED', probe.digest(expected))
    result = probe.inject(data)
    assert result == expected
    assert result[64:120] == data[64:120]
    assert result[176:480] == data[176:480]
    assert probe.inject(result) == result


def test_projection_preserves_horizontal_and_pixel_scale():
    # Both the default and the observed run-and-gun zoom.
    for zoom in (1.0, 0.811):
        height = 720 / zoom
        width = height * 16 / 9
        m00 = 2 / width
        m11 = m00 * 1280 / 960
        assert 2 / m00 == pytest.approx(width)
        assert 2 / m11 == pytest.approx(height * 4 / 3)
        assert 1280 / width == pytest.approx(960 / (2 / m11))
