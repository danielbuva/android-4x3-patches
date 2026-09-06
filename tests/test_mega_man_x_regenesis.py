"""Synthetic fixtures only: fail-closed matching and original/patched recognition."""
import struct
from pathlib import Path

import pytest
from android4x3.registry import Registry


def module():
    registry = Registry(Path(__file__).resolve().parents[1] / "games")
    return registry.module(registry.by_id["mega-man-x-regenesis"])


def config(height=216, width=384, extra=()):
    records = [("display/window/size/viewport_width", struct.pack("<Ii", 2, width)),
               ("display/window/size/viewport_height", struct.pack("<Ii", 2, height)),
               ("display/window/stretch/mode", struct.pack("<II", 4, 12) + b"canvas_items"),
               ("unrelated", b"preserve me"), *extra]
    return b"ECFG" + struct.pack("<I", len(records)) + b"".join(
        struct.pack("<I", len(k.encode())) + k.encode() + struct.pack("<I", len(v)) + v
        for k, v in records)


def camera():
    return """extends Camera2D
func update_camera(delta):
    var half_view = get_viewport_rect().size * 0.5 / zoom
func _snap_camera_to_player():
    var world_limits = Rect2()
    var half_size = get_viewport_rect().size * 0.5 / zoom
"""


def test_config_only_changes_height_and_is_idempotent():
    m = module()
    original = config()
    patched = m.patch_config(original)
    assert patched == config(288)
    assert m.config_state(original) == "original"
    assert m.config_state(patched) == "patched"
    assert m.patch_config(patched) == patched


@pytest.mark.parametrize("data", [config(240), config(width=400), config()[:-1],
    config(extra=[("display/window/size/viewport_height", struct.pack("<Ii", 2, 216))]),
    config(extra=[("display/window/stretch/aspect", struct.pack("<II", 4, 6) + b"ignore")])])
def test_unknown_or_ambiguous_settings_fail(data):
    with pytest.raises((ValueError, struct.error)):
        module().patch_config(data)


def test_camera_preserves_original_vertical_tracking_and_both_paths():
    m = module()
    patched = m.patch_camera(camera())
    assert m.camera_state(patched) == "patched"
    assert patched.count(m.CAMERA_NEW) == 2
    assert m.patch_camera(patched) == patched
    with pytest.raises(ValueError):
        m.patch_camera(camera().replace(m.CAMERA_OLD, "Vector2.ZERO", 1))
    with pytest.raises(ValueError):
        m.patch_camera(camera().replace(m.CAMERA_OLD, m.CAMERA_NEW, 1))


def test_existing_autoload_lifecycle_and_partial_layout_fail():
    m = module()
    source = "extends Node\nfunc warm_up_scene(root):\n pass\nfunc _collect_particles(node, list):\n pass\n"
    assert m.warmup_state(source) == "original"
    import re
    patched = source + re.sub(r"(?m)#.*$", "", m.LAYOUT.read_text())
    assert m.warmup_state(patched) == "patched"
    with pytest.raises(ValueError):
        m.warmup_state(source + "func _ready():\n pass")
    with pytest.raises(ValueError):
        m.warmup_state(patched.replace("1.25", "1.5", 1))


def test_probe_rejects_mixed_states(tmp_path, monkeypatch):
    m = module()
    cfg = tmp_path / "project.binary"
    cfg.write_bytes(config(288))
    source = "extends Node\nfunc warm_up_scene(root):\n pass\nfunc _collect_particles(node, list):\n pass\n"
    monkeypatch.setattr(m, "verify_sparse", lambda *args: None)
    monkeypatch.setattr(m, "decompile", lambda p, out: camera() if out.name == "camera" else source)
    result = m.probe({m.CONFIG: cfg, m.INDEX: cfg, m.CAMERA: cfg, m.WARMUP: cfg})
    assert result["state"] == "unsupported"


def sparse(payloads):
    header = bytearray(104)
    header[:8] = b"GDPC\x04\0\0\0"
    struct.pack_into("<I", header, 20, 6)
    struct.pack_into("<Q", header, 32, 104)
    result = bytes(header) + struct.pack("<I", len(payloads))
    import hashlib
    for entry, payload in payloads.items():
        name = entry.removeprefix("assets/").encode()
        name += b"\0" * (-len(name) % 4)
        result += struct.pack("<I", len(name)) + name
        result += struct.pack("<QQ", 0, len(payload)) + hashlib.md5(payload).digest() + struct.pack("<I", 0)
    return result


def test_sparse_index_tracks_changed_lengths_and_hashes():
    m = module()
    original = {m.CAMERA: b"old", m.WARMUP: b"short", m.CONFIG: b"config"}
    updated = {**original, m.WARMUP: b"longer compiled script"}
    index = sparse(original)
    m.verify_sparse(index, original)
    with pytest.raises(ValueError):
        m.verify_sparse(index, updated)
    patched = m.patch_sparse(index, updated)
    assert patched == sparse(updated)
    m.verify_sparse(patched, updated)
    assert m.patch_sparse(patched, updated) == patched


def test_native_regenesis_cli_roundtrip(tmp_path, make_apk, binary_manifest):
    """Real GDRE + zipalign + keytool + signing on each OS; no proprietary input."""
    import os
    import subprocess
    import sys
    import zipfile
    from android4x3 import signing
    m = module()
    try:
        m.gdre()
        signing.find_android_tool("zipalign")
        signing.find_android_tool("apksigner")
    except (ValueError, RuntimeError) as exc:
        if os.environ.get("ANDROID4X3_REQUIRE_NATIVE_TESTS"):
            pytest.fail(str(exc))
        pytest.skip(str(exc))
    work = tmp_path / "Unicode café 日本語 & spaces"
    work.mkdir()
    source_camera = work / "camera.gd"
    source_warmup = work / "shader_warmup.gd"
    source_camera.write_text(camera(), encoding="utf-8")
    source_warmup.write_text(
        'extends Node\nconst GREETING = "café 日本語 ⚡"\n'
        'func warm_up_scene(root):\n pass\nfunc _collect_particles(node, list):\n pass\n',
        encoding="utf-8")
    for script in (source_camera, source_warmup):
        m.run_gdre(f"--compile={script}", "--bytecode=4.5.0", f"--output={work}")
    payloads = {m.CONFIG: config(), m.CAMERA: source_camera.with_suffix(".gdc").read_bytes(),
                m.WARMUP: source_warmup.with_suffix(".gdc").read_bytes()}
    payloads[m.INDEX] = sparse(payloads)
    source = make_apk(work / "Input 日本語.apk",
        manifest=binary_manifest("com.example.megamanxregenesis", "1.0.0", 1),
        entries=[(name, data, zipfile.ZIP_DEFLATED) for name, data in payloads.items()])
    output = work / "Output café-4x3.apk"
    repo = Path(__file__).resolve().parents[1]
    env = {**os.environ, "LOCALAPPDATA": str(work / "signing state"),
           "XDG_DATA_HOME": str(work / "signing state"), "PYTHONIOENCODING": "ascii"}
    result = subprocess.run([sys.executable, str(repo / "patch.py"), "--allow-experimental",
        str(source), "--output", str(output)], env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Rebuilt and verified APK" in result.stdout
    with zipfile.ZipFile(output) as archive:
        check = work / "check.gdc"
        check.write_bytes(archive.read(m.WARMUP))
        assert 'café 日本語 ⚡' in m.decompile(check, work / "decompiled")
        assert m.config_state(archive.read(m.CONFIG)) == "patched"
        m.verify_sparse(archive.read(m.INDEX), {e: archive.read(e) for e in payloads if e != m.INDEX})
