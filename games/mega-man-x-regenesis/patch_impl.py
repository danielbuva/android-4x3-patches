"""Semantic Godot config/GDScript transformations; no game source is distributed."""
from __future__ import annotations

import os
import hashlib
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

CONFIG = "assets/project.binary"
CAMERA = "assets/scripts/Player/camera.gdc"
WARMUP = "assets/scripts/shader_warmup.gdc"
INDEX = "assets/assets.sparsepck"
REQUIRED_ENTRIES = (CONFIG, CAMERA, WARMUP, INDEX)
CAMERA_OLD = "get_viewport_rect().size * 0.5 / zoom"
CAMERA_NEW = "Vector2(get_viewport_rect().size.x, 216.0) * 0.5 / zoom"
LAYOUT = Path(__file__).with_name("layout.gd")


def settings(data: bytes) -> dict[str, tuple[int, bytes]]:
    if data[:4] != b"ECFG" or len(data) < 8:
        raise ValueError("not a Godot binary project config")
    count = struct.unpack_from("<I", data, 4)[0]
    result = {}
    pos = 8
    for _ in range(count):
        size = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        key = data[pos:pos + size].decode("utf-8")
        pos += size
        size = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        if key in result or pos + size > len(data):
            raise ValueError("duplicate or truncated config entry")
        result[key] = (pos, data[pos:pos + size])
        pos += size
    if pos != len(data):
        raise ValueError("unexpected config trailing bytes")
    return result


def config_state(data: bytes) -> str:
    entries = settings(data)
    def integer(key):
        value = entries["display/window/" + key][1]
        if len(value) != 8 or value[:4] != struct.pack("<I", 2):
            raise ValueError("expected 32-bit integer setting")
        return struct.unpack_from("<i", value, 4)[0]
    if integer("size/viewport_width") != 384:
        raise ValueError("unknown logical width")
    mode = entries["display/window/stretch/mode"][1]
    if mode != struct.pack("<II", 4, 12) + b"canvas_items":
        raise ValueError("unknown canvas stretch mode")
    aspect = entries.get("display/window/stretch/aspect")
    if aspect is not None and aspect[1] != struct.pack("<II", 4, 4) + b"keep":
        raise ValueError("unsupported stretch aspect override")
    height = integer("size/viewport_height")
    if height not in (216, 288):
        raise ValueError("unknown logical height")
    return "original" if height == 216 else "patched"


def patch_config(data: bytes) -> bytes:
    if config_state(data) == "patched":
        return data
    pos, _ = settings(data)["display/window/size/viewport_height"]
    return data[:pos + 4] + struct.pack("<i", 288) + data[pos + 8:]


def sparse_records(data: bytes) -> dict[str, int]:
    if len(data) < 108 or data[:8] != b"GDPC\x04\0\0\0":
        raise ValueError("expected sparse PCK version 4")
    if struct.unpack_from("<I", data, 20)[0] != 6:
        raise ValueError("unsupported sparse PCK flags")
    pos = struct.unpack_from("<Q", data, 32)[0]
    count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    records = {}
    for _ in range(count):
        length = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        name = data[pos:pos + length].rstrip(b"\0").decode()
        pos += length
        if name in records or pos + 36 > len(data):
            raise ValueError("duplicate or truncated sparse entry")
        records[name] = pos
        pos += 36
    if pos != len(data):
        raise ValueError("unexpected sparse directory trailer")
    return records


def verify_sparse(index: bytes, payloads: dict[str, bytes]) -> None:
    records = sparse_records(index)
    for entry, payload in payloads.items():
        pos = records[entry.removeprefix("assets/")]
        offset, size = struct.unpack_from("<QQ", index, pos)
        flags = struct.unpack_from("<I", index, pos + 32)[0]
        if offset or flags or size != len(payload) or index[pos + 16:pos + 32] != hashlib.md5(payload).digest():
            raise ValueError("sparse index does not match " + entry)


def patch_sparse(index: bytes, payloads: dict[str, bytes]) -> bytes:
    records = sparse_records(index)
    result = bytearray(index)
    for entry, payload in payloads.items():
        pos = records[entry.removeprefix("assets/")]
        if struct.unpack_from("<Q", index, pos)[0] or struct.unpack_from("<I", index, pos + 32)[0]:
            raise ValueError("unsupported packed or encrypted sparse entry")
        struct.pack_into("<Q", result, pos + 8, len(payload))
        result[pos + 16:pos + 32] = hashlib.md5(payload).digest()
    return bytes(result)


def gdre() -> str:
    path = os.environ.get("GDRE_TOOLS") or shutil.which("gdre_tools")
    if not path or not Path(path).is_file():
        raise ValueError("Install GDRE Tools 2.6.4+ and set GDRE_TOOLS to its executable")
    return path


def run_gdre(*args: str) -> None:
    result = subprocess.run([gdre(), "--headless", *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    if result.returncode or "ERROR:" in result.stdout:
        raise ValueError("GDRE conversion failed: " + result.stdout[-3000:])


def decompile(source: Path, output: Path) -> str:
    if source.read_bytes()[:8] != b"GDSC\x65\0\0\0":
        raise ValueError("unsupported GDScript bytecode; expected version 101")
    output.mkdir(parents=True, exist_ok=True)
    run_gdre(f"--decompile={source}", "--bytecode=4.5.0", f"--output={output}")
    return (output / (source.stem + ".gd")).read_text()


def compact(source: str) -> str:
    return re.sub(r"\s+", "", source)


def camera_state(source: str) -> str:
    source = compact(source)
    if not all(x in source for x in ("extendsCamera2D", "funcupdate_camera(",
                                      "func_snap_camera_to_player(", "world_limits", "half_view", "half_size")):
        raise ValueError("unrecognized camera structure")
    original, patched = source.count(compact(CAMERA_OLD)), source.count(compact(CAMERA_NEW))
    if (original, patched) == (2, 0):
        return "original"
    if (original, patched) == (0, 2):
        return "patched"
    raise ValueError("camera view expressions changed or mixed states")


def patch_camera(source: str) -> str:
    if camera_state(source) == "patched":
        return source
    pattern = r"get_viewport_rect\(\)\s*\.size\s*\*\s*0\.5\s*/\s*zoom"
    result, count = re.subn(pattern, CAMERA_NEW, source)
    if count != 2:
        raise ValueError("camera expression match was not unique per function")
    return result


def warmup_state(source: str) -> str:
    normalized = compact(source)
    if not all(x in normalized for x in ("extendsNode", "funcwarm_up_scene(", "func_collect_particles(")):
        raise ValueError("unrecognized ShaderWarmup autoload")
    # Comments are discarded by the compiler; use actual method content as the guard.
    layout = compact(re.sub(r"(?m)#.*$", "", LAYOUT.read_text()))
    if "func_a4x3_layout(" in normalized:
        if not normalized.endswith(layout):
            raise ValueError("different or partial layout patch detected")
        return "patched"
    if "func_ready(" in normalized or "_a4x3" in normalized:
        raise ValueError("autoload startup changed; manual review required")
    return "original"


def probe(extracted: dict[str, Path]) -> dict:
    try:
        verify_sparse(extracted[INDEX].read_bytes(), {e: extracted[e].read_bytes() for e in (CONFIG, CAMERA, WARMUP)})
        with tempfile.TemporaryDirectory(prefix="regenesis-probe-") as work:
            root = Path(work)
            states = [config_state(extracted[CONFIG].read_bytes()),
                      camera_state(decompile(extracted[CAMERA], root / "camera")),
                      warmup_state(decompile(extracted[WARMUP], root / "warmup"))]
        state = states[0] if len(set(states)) == 1 else "unsupported"
        return {"state": state, "detail": "384x288 Vert+; original vertical camera tracking; proportional UI",
                "targets": [{"name": n, "state": s} for n, s in zip(
                    ("logical viewport", "camera zone tracking", "UI layout autoload"), states)]}
    except (ValueError, KeyError, OSError, struct.error, subprocess.SubprocessError) as exc:
        return {"state": "unsupported", "detail": str(exc), "targets": []}


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    check = probe(extracted)
    if check["state"] not in ("original", "patched"):
        raise ValueError(check["detail"])
    output_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    target = output_dir / "project.binary"
    target.write_bytes(patch_config(extracted[CONFIG].read_bytes()))
    result[CONFIG] = target
    for entry in (CAMERA, WARMUP):
        source = decompile(extracted[entry], output_dir / (Path(entry).stem + "-source"))
        if entry == CAMERA:
            source = patch_camera(source)
        elif warmup_state(source) == "original":
            source += "\n" + LAYOUT.read_text()
        script = output_dir / (Path(entry).stem + ".gd")
        script.write_text(source)
        run_gdre(f"--compile={script}", "--bytecode=4.5.0", f"--output={output_dir}")
        result[entry] = script.with_suffix(".gdc")
    index = output_dir / "assets.sparsepck"
    index.write_bytes(patch_sparse(extracted[INDEX].read_bytes(), {e: p.read_bytes() for e, p in result.items()}))
    result[INDEX] = index
    return result
