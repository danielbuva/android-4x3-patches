"""Synthetic binary fixtures and projection regression checks; no game assets."""
import struct
from pathlib import Path

import pytest

from android4x3.errors import PatchError
from android4x3.registry import Registry

ROOT = Path(__file__).resolve().parents[1]


def module():
    r = Registry(ROOT / "games")
    return r.module(r.by_id["skate-3"])


def native_fixture():
    data = bytearray(0x300)
    data[:16] = b"\x7fELF\x02\x01\x01" + b"\0" * 9
    struct.pack_into("<HHIQQQIHHHHHH", data, 16, 3, 183, 1, 0, 64, 0, 0, 64, 56, 1, 64, 0, 0)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0x100, 0x100, 0x100, 0x200, 0x200, 4)
    data[0x180:0x188] = bytes.fromhex("20008052c0035fd6")  # mov w0,1; ret
    return data


def native_spec():
    return [{"name": "synthetic function", "symbol": None,
             "before": "20008052c0035fd6", "after": "40008052c0035fd6"}]


def keyboard_fixture(m, monkeypatch):
    from types import SimpleNamespace
    data = native_fixture()
    struct.pack_into("<H", data, 56, 2)
    struct.pack_into("<IIQQQQQQ", data, 120, 4, 4, 0x110, 0x110, 0x110, 16, 16, 4)
    data[0x180:0x190] = m.KEYBOARD_PREFIX
    previous = m._helper().ElfImage.dynamic_symbol_info
    monkeypatch.setattr(m._helper().ElfImage, "dynamic_symbol_info", lambda self, name:
                        SimpleNamespace(value=0x180, size=16) if name == m.KEYBOARD_SYMBOL else
                        SimpleNamespace(value=0x220, size=4) if name == m.POSITION_SYMBOL else previous(self, name))
    return bytes(data)



def runtime_fixture(m, monkeypatch):
    from types import SimpleNamespace
    data=bytearray(keyboard_fixture(m,monkeypatch))+bytes(0x200)
    struct.pack_into("<H",data,56,3)
    data[176:232]=data[120:176]
    struct.pack_into("<IIQQQQQQ",data,120,1,6,0x400,0x400,0x400,0x100,0x100,4)
    struct.pack_into("<6I",data,0x200,0x1e602018,0x9e660009,0x90000008,0x9a9fc129,0xf9020509,0xd65f03c0)
    struct.pack_into("<3I",data,0x228,0x90000008,0xfd420500,0xd65f03c0)
    previous=m._helper().ElfImage.dynamic_symbol_info
    monkeypatch.setattr(m._helper().ElfImage,"dynamic_symbol_info",lambda self,name:
                        SimpleNamespace(value=0x200,size=24) if name==m.ASPECT_SETTER else
                        SimpleNamespace(value=0x228,size=12) if name==m.ASPECT_GETTER else previous(self,name))
    return bytes(data)


def test_runtime_aspect_survives_settings_and_validates_shared_storage(monkeypatch):
    m=module(); original=runtime_fixture(m,monkeypatch)
    targets,edits=m._runtime(original)
    assert all(t["state"]=="original" for t in targets)
    patched=edits[0][2]
    assert all(t["state"]=="patched" for t in m._runtime(patched)[0])
    assert m._runtime(patched)[1]==[]
    assert patched[0x200:0x208]==bytes.fromhex("e9f300b2a9fee7f2")
    assert patched[0x208:0x20c]==original[0x208:0x20c]
    assert patched[0x210:0x218]==original[0x210:0x218]
    broken=bytearray(original); broken[0x22c]^=4
    with pytest.raises(PatchError,match="getter/storage"):
        m._runtime_aspect(bytes(broken))


def movie_fixture(m, monkeypatch):
    from types import SimpleNamespace
    data = native_fixture() + bytes(0x700)
    struct.pack_into("<H", data, 56, 3)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0x100, 0x100, 0x100, 0x700, 0x700, 4)
    struct.pack_into("<IIQQQQQQ", data, 120, 1, 6, 0x900, 0x900, 0x900, 0x100, 0x200, 4)
    struct.pack_into("<IIQQQQQQ", data, 176, 4, 4, 0x110, 0x110, 0x110, 16, 16, 4)
    struct.pack_into("<5I", data, 0x240, 0xf94443f6, 0xf94447f7, 0xf90487ff, 0xf90483ff, 0xeb1702df)
    data[0x280:0x288] = bytes.fromhex("d6220491df0217eb")
    spec = next(s for s in m.NATIVE_TARGETS if s["name"] == "UI scale Y")
    data[0x300:0x320] = bytes.fromhex(spec["before"]) + m.MOVIE_CONTEXT
    struct.pack_into("<5I", data, 0x400, 0x90000018, 0xaa0003f3, 0x90000019,
                     0x39400308 | (0x901 << 10), 0x36000188)
    struct.pack_into("<4I", data, 0x440, 0x9000001a, 0x39400348 | (0x900 << 10),
                     0x7100051f, 0x54000041)
    data[0x500:0x50c] = bytes.fromhex("fd7bbea9f30b00f9fd030091")
    data[0x50c:0x510] = m._branch(0x50c, 0x700, link=True)
    data[0x54c:0x550] = m._branch(0x54c, 0x700, link=True)
    struct.pack_into("<7I", data, 0x550, 0x7100001f, 0x2a0003f4, 0x90000008,
                     0x1a9f17e9, 0x9000001b, 0x39000109 | (0x902<<10), 0x340000a0)
    struct.pack_into("<3I", data, 0x600, 0x90000000, 0x91000000 | (0x904<<10), 0xd65f03c0)
    struct.pack_into("<I", data, 0x904, 4000)
    data[0x650:0x660] = bytes.fromhex("e913881a2020201e2d0c0054090c0034")
    struct.pack_into("<I", data, 0x90c, 0xffffffff)
    previous = m._helper().ElfImage.dynamic_symbol_info
    monkeypatch.setattr(m._helper().ElfImage, "dynamic_symbol_info", lambda self, name:
                        SimpleNamespace(value=0x90c, size=4) if name == m.FRONTEND_SYMBOL else
                        SimpleNamespace(value=0x400, size=0x80) if name == m.MOVIE_SYMBOL else
                        SimpleNamespace(value=0x500, size=20) if name == m.MENU_CONTEXT_SYMBOL else
                        SimpleNamespace(value=0x600, size=12) if name == m.WATCHDOG_SYMBOL else
                        SimpleNamespace(value=0x903, size=1) if name == m.WARMUP_SYMBOL else previous(self, name))
    return bytes(data)


def test_movie_hook_resolves_lifecycle_and_preserves_other_movies(monkeypatch):
    m = module()
    data = movie_fixture(m, monkeypatch)
    elf = m._helper().ElfImage(data)
    assert m._movie_flags(elf, data) == 0x900
    assert m._menu_flag(elf, data) == 0x902
    assert m._hud_end(elf, data) == 0x7dc
    patched, original, state = m._movie(data)
    assert state == "original" and original == data
    assert m._movie(patched) == (patched, data, "patched")
    segment = m._helper().ElfImage(patched).program_headers[-1]
    assert segment.flags == 5 and segment.vaddr >= 0xb00
    # The classifier uses frontend screen identity and a guarded immutable
    # snapshot. Every branch exits past the obsolete per-batch safe-area code.
    words = struct.unpack_from("<" + "I" * (len(m.MOVIE_STUB)//4), patched, segment.offset)
    assert words[0] & 0xff00001f == 0xb500001a  # video uses screen-aware classifier
    assert m._scene_stack(elf, data, 0x300) == 0x880
    assert 0x912403e9 in words  # add x9,sp,#0x900
    def destination(word, pc):
        imm = word & 0x3ffffff
        if imm & 0x2000000:
            imm -= 0x4000000
        return pc + imm * 4
    off = m.MOVIE_LINKS["ea_return"]
    assert destination(words[off//4], segment.vaddr + off) == 0x7dc  # cover skips HUD movement
    off = m.MOVIE_LINKS["normal_return"]
    assert destination(words[off//4], segment.vaddr + off) == 0x7dc  # classification replaces per-batch HUD translation
    broken = bytearray(patched)
    broken[segment.offset + 28] ^= 4
    with pytest.raises(PatchError, match="postcondition"):
        m._movie(bytes(broken))
    broken = bytearray(data)
    broken[0x40c] ^= 1
    with pytest.raises(PatchError, match="lifecycle"):
        m._movie(bytes(broken))
    broken = bytearray(data)
    broken[0x300:0x320] = bytes(32)
    with pytest.raises(PatchError, match="projection site"):
        m._movie(bytes(broken))


def test_native_keyboard_hook_preserves_original_elf_and_recognizes_post_state(monkeypatch):
    m = module()
    original = keyboard_fixture(m, monkeypatch)
    state, edits = m._keyboard(original)
    assert state[0]["state"] == "original"
    patched = edits[0][2]
    assert m._keyboard(patched)[0][0]["state"] == "patched"
    assert m._keyboard(patched)[1] == []
    assert patched[0x184:0x190] == original[0x184:0x190]
    assert patched[0x110:0x120] == original[0x110:0x120]  # retained note data
    elf = m._helper().ElfImage(patched)
    new = elf.program_headers[-1]
    assert new.p_type == 1 and new.flags == 5  # RX, never writable/executable
    assert new.vaddr >= 0x300 and new.offset % 0x4000 == 0
    assert new.memsz == new.filesz
    broken = bytearray(patched)
    broken[new.offset + 56] ^= 4  # incorrect linked call
    with pytest.raises(PatchError, match="postcondition"):
        m._keyboard(bytes(broken))
    broken = bytearray(original)
    broken[0x184] ^= 1
    with pytest.raises(PatchError, match="Unrecognized"):
        m._keyboard(bytes(broken))


def test_native_unique_executable_original_patched_and_ambiguous(monkeypatch):
    m = module()
    monkeypatch.setattr(m, "NATIVE_TARGETS", native_spec())
    data = native_fixture()
    assert m._overall(m._native(data)[0]) == "original"
    data[0x180:0x188] = bytes.fromhex(native_spec()[0]["after"])
    assert m._overall(m._native(data)[0]) == "patched"
    data[0x200:0x208] = data[0x180:0x188]
    assert m._overall(m._native(data)[0]) == "ambiguous"
    struct.pack_into("<I", data, 68, 4)  # non-executable PT_LOAD
    assert m._overall(m._native(data)[0]) == "unsupported"


def test_native_target_relocation_accepted_unknown_bytes_refused(monkeypatch):
    m = module()
    monkeypatch.setattr(m, "NATIVE_TARGETS", native_spec())
    data = native_fixture()
    data[0x220:0x228], data[0x180:0x188] = data[0x180:0x188], bytes(8)
    assert m._native(data)[1][0][0] == 0x220
    data[0x220] ^= 1
    assert m._overall(m._native(data)[0]) == "unsupported"


def test_native_symbol_gate_and_architecture(monkeypatch):
    m = module()
    spec = native_spec()
    spec[0]["symbol"] = "missing_export"
    monkeypatch.setattr(m, "NATIVE_TARGETS", spec)
    data = native_fixture()
    assert m._overall(m._native(data)[0]) == "unsupported"
    struct.pack_into("<H", data, 18, 62)
    with pytest.raises(PatchError, match="ARM64"):
        m._native(data)


def dex_fixture(m, monkeypatch, *, patched=False, tail=True, class_name="Lchat/buku/skate3/Skate3Activity;"):
    # Real DEX code item with synthetic method metadata provided independently.
    # Indices deliberately differ from the audited game's DEX.
    helper = m._helper()
    data = bytearray(0xc0)
    data[:8] = b"dex\n035\0"
    struct.pack_into("<III", data, 0x20, len(data), 0x70, 0x12345678)
    struct.pack_into("<I", data, 0x58, 3)
    struct.pack_into("<II", data, 0x50, 1, 0xb0)
    struct.pack_into("<HHI", data, 0xb0, 0, 1, 0)
    monkeypatch.setattr(helper.DexImage, "types", property(lambda self: [
        "Lchat/buku/skate3/Skate3Activity;", "Lchat/buku/skate3/TouchControllerView;",
        "Landroid/view/ViewGroup$LayoutParams;"]))
    monkeypatch.setattr(helper.DexImage, "strings", property(lambda self: ["touchController"]))
    instructions = bytes.fromhex("542200002200020012f17030010010016e30000023000e00")
    if patched:
        instructions = instructions[:-8] + bytes(6) + instructions[-2:]
    if not tail:
        instructions += b"\0\0"
    struct.pack_into("<HHHHII", data, 0x70, 4, 2, 3, 0, 0, len(instructions)//2)
    data[0x80:0x80+len(instructions)] = instructions
    identities = [("Landroid/view/ViewGroup;", "addView", "(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V"),
                  ("Landroid/view/ViewGroup$LayoutParams;", "<init>", "(II)V"),
                  (class_name, "onCreate", "(Landroid/os/Bundle;)V")]
    monkeypatch.setattr(helper.DexImage, "_method_identity", lambda self, i: identities[i])
    monkeypatch.setattr(helper.DexImage, "methods", lambda self: iter([
        helper._DexMethod(class_name, "onCreate", "(Landroid/os/Bundle;)V", 0x70)]))
    return helper.DexImage(data).finish()


def test_touch_attachment_uses_method_identity_and_constructor_context(monkeypatch):
    m = module()
    data = dex_fixture(m, monkeypatch)
    assert m._dex(data)[0][0]["state"] == "original"
    off, before, after = m._dex(data)[1][0]
    patched = data[:off] + after + data[off+len(before):]
    assert m._dex(patched)[0][0]["state"] == "patched"
    damaged = bytearray(data)
    damaged[off - 1] ^= 1
    assert m._dex(damaged)[0][0]["state"] == "unsupported"
    wrong_view = bytearray(data)
    struct.pack_into("<H", wrong_view, 0xb2, 2)  # field is not TouchControllerView
    assert m._dex(wrong_view)[0][0]["state"] == "unsupported"
    assert m._dex(dex_fixture(m, monkeypatch, tail=False))[0][0]["state"] == "unsupported"
    assert m._dex(dex_fixture(m, monkeypatch, class_name="Lexample/Other;"))[0][0]["state"] == "unsupported"


def test_combined_application_and_idempotence(monkeypatch, tmp_path):
    m = module()
    ui = next(s for s in m.NATIVE_TARGETS if s["name"] == "UI scale Y")
    monkeypatch.setattr(m, "NATIVE_TARGETS", native_spec() + [ui])
    native, dex, runtime = tmp_path/"native", tmp_path/"dex", tmp_path/"runtime"
    original_native = movie_fixture(m, monkeypatch)
    native.write_bytes(original_native)
    dex.write_bytes(dex_fixture(m, monkeypatch))
    runtime.write_bytes(runtime_fixture(m, monkeypatch))
    extracted = {m.NATIVE: native, m.DEX: dex, m.RUNTIME: runtime}
    output = m.apply(extracted, tmp_path/"out")
    assert m.probe(output)["state"] == "patched"
    assert m.apply(output, tmp_path/"again") == {}
    assert native.read_bytes() == original_native
    assert m.probe({**output, "lib/x86_64/libskate3.so": native})["state"] == "unsupported"
    with pytest.raises(PatchError):
        m.apply({m.NATIVE: native}, tmp_path/"bad")


def _run_scalar_matrix_code(code, memory, scale, scale_register, initial=None):
    """Execute the actual patch's scalar ARM64 loads/multiplies/stores."""
    registers = {scale_register: scale, **(initial or {})}
    for (word,) in struct.iter_unpack("<I", code):
        rd, rn, rm = word & 31, (word >> 5) & 31, (word >> 16) & 31
        if word & 0xffc00000 == 0xbd400000:
            registers[rd] = memory[((word >> 10) & 4095) * 4]
        elif word & 0xffc00000 == 0xbd000000:
            memory[((word >> 10) & 4095) * 4] = registers[rd]
        elif word & 0xffe0fc00 == 0x1e200800:
            registers[rd] = registers[rn] * registers[rm]
        elif word & 0xffe0fc00 == 0x1e201800:
            registers[rd] = registers[rn] / registers[rm]
        elif word & 0xffe0fc00 == 0x1e203800:
            registers[rd] = registers[rn] - registers[rm]
        else:
            raise AssertionError(f"unexpected instruction {word:08x}")
    return memory


@pytest.mark.parametrize("name,bases,scale_register", [
    ("camera Y column", (0x54, 0x8), 0),
    ("frame camera Y column", (0x16f4, 0x16a8), 11),
])
def test_actual_matrix_instructions_preserve_x_and_expand_y(name, bases, scale_register):
    specs = module().NATIVE_TARGETS
    code = bytes.fromhex(next(s["after"] for s in specs if s["name"] == name))
    original = {base + i*4: float(i+1) for base in bases for i in range(16)}
    after = _run_scalar_matrix_code(code, dict(original), .75, scale_register)
    for base in bases:
        for i in range(16):
            assert after[base+i*4] == pytest.approx(original[base+i*4] * (.75 if i%4 == 1 else 1))
    # Same width and proportional geometry: the visible vertical interval is
    # 4/3 as tall, adding 1/6 of the old height above and below.
    assert 960 * .75 == 720
    assert (1/.75 - 1)/2 == pytest.approx(1/6)


def test_culling_targets_preserve_pair_layout_and_select_vertical_planes():
    specs = {s["name"]: s for s in module().NATIVE_TARGETS}
    pair = specs["culling top and bottom planes"]
    offsets = []
    for (before,), (after,) in zip(struct.iter_unpack("<I", bytes.fromhex(pair["before"])),
                                  struct.iter_unpack("<I", bytes.fromhex(pair["after"]))):
        if before == after:
            continue
        # Each changed instruction must be MOVZ Wn, imm16, retaining its
        # destination register and selecting the next two four-float planes.
        assert before & 0xffe00000 == after & 0xffe00000 == 0x52800000
        assert before & 31 == after & 31
        old, new = (before >> 5) & 65535, (after >> 5) & 65535
        assert new == old + 32
        offsets.append(new)
    assert sorted(offsets) == list(range(5184, 5216, 4))
    # Verify the branch destinations in the injected gate/factor sequence:
    # the first skips only the ultrawide preference, retaining the native
    # renderer guard; the second enters the original cached plane expansion.
    gate = bytes.fromhex(specs["culling native renderer gate"]["after"])
    factor = bytes.fromhex(specs["culling vertical expansion factor"]["after"])
    assert struct.unpack_from("<I", gate)[0] == 0x14000005  # PC + 20
    assert struct.unpack_from("<I", factor, 8)[0] == 0x14000036  # PC + 216
    assert struct.unpack_from("<I", factor)[0] == 0x1e2d1008  # fmov s8, .75


def test_full_canvas_overlay_classifier_rejects_text_small_panels_and_invalid_geometry(tmp_path):
    import ctypes
    import shutil
    import subprocess
    compiler = shutil.which("cc")
    if not compiler:
        pytest.skip("C compiler unavailable for own-code overlay classifier")
    output = tmp_path / "classifier.so"
    subprocess.run([compiler, "-shared", "-fPIC", "-O2", "-ffp-contract=off",
                    str(ROOT/"games/skate-3/overlay_classifier.c"), "-o", str(output)], check=True)
    classify = ctypes.CDLL(str(output)).full_canvas_overlay
    classify.argtypes = [ctypes.c_void_p] + [ctypes.c_uint]*5 + [ctypes.c_void_p]*2
    classify.restype = ctypes.c_int
    def trial(points, stride=16, rgb=(0, 0, 0), world=None, truncate=False,
              title=0, screen=0xffffffff, warmup=0, menu=0, video=0, texture=(1,1,20)):
        vertices = ctypes.create_string_buffer(b"".join(struct.pack("<7f", x,y,0,1,0,0,0) for x,y in points))
        draw = ctypes.create_string_buffer(0x108)
        struct.pack_into("<I", draw, 4, len(points))
        struct.pack_into("<I", draw, 12, stride)
        tw,th,fmt=texture
        struct.pack_into("<2I", draw, 0x1c, fmt, (tw-1)|((th-1)<<13))
        identity = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
        projection = [2/1280,0,0,-1, 0,-2/720,0,1, 0,0,1,0, 0,0,0,1]
        struct.pack_into("<36f", draw, 0x60, *(projection + (world or identity) + list(rgb) + [.5]))
        address = ctypes.addressof(vertices)
        struct.pack_into("<QQ", draw, 0xf0, address, address + (4 if truncate else len(points)*28))
        return classify(draw, title, screen, warmup, menu, video, None, None)
    quad = [(0,0),(1280,0),(1280,720),(0,720)]
    assert trial(quad) == 1
    assert trial([(-8,-5),(1288,-5),(1288,725),(-8,725)]) == 1
    assert trial([(-8,50),(1288,50),(1288,725),(-8,725)]) == 0
    assert trial([quad[i] for i in (0,1,2,0,2,3)], rgb=(1,1,1)) == 1  # white fade
    assert trial(quad, stride=24) == 1  # texture tinted black
    assert trial(quad, stride=24, rgb=(1,1,1), texture=(512,512,20)) == 0  # artwork
    assert trial([(100,100),(400,100),(400,600),(100,600)]) == 0
    assert trial([(0,0),(1280,0),(1280,360),(0,360)]) == 0
    assert trial([(0,0),(1280,0),(1280,720),(640,360)]) == 0  # not a rectangle
    assert trial([(float("nan"),0),*quad[1:]]) == 0
    assert trial(quad, truncate=True) == 0
    for x,y,w,h in [(0,0,1024,512),(1024,0,256,512),(0,512,1024,256),(1024,512,256,256)]:
        tile=[(x,y),(x+w,y),(x+w,y+h),(x,y+h)]
        assert trial(tile,24,(1,1,1),title=1,warmup=1,texture=(w,h,20))==2
        assert trial(tile,24,(1,1,1),title=1,warmup=1,texture=(w,h,18))==1
        assert trial(tile,24,(1,1,1),title=1,warmup=0,texture=(w,h,20))==0
    panel=[(360,200),(920,200),(920,580),(360,580)]
    assert trial(panel,24,(1,1,1),screen=9,warmup=1)==5
    assert trial(panel,24,(1,1,1),screen=9,warmup=1,video=1)==5
    assert trial(quad,24,(1,1,1),screen=9,warmup=1,texture=(64,64,20))==1
    assert trial(quad,24,(1,1,1),screen=9,warmup=1,texture=(128,128,18))==1
    assert trial([(150,80),(580,80),(580,220),(150,220)],24,(1,1,1),title=1,warmup=1)==3
    spinner=[(1110,600),(1170,600),(1170,660),(1110,660)]
    assert trial(spinner,24,(1,1,1),menu=1)==4
    assert trial(spinner,24,(1,1,1))==0
    world = [2,0,0,0, 0,2,0,0, 0,0,1,0, 0,0,0,1]
    assert trial([(x/2,y/2) for x,y in quad], world=world) == 1


def test_movie_timeout_uses_symbol_resolved_default_and_keeps_a_recovery_limit(monkeypatch):
    m = module()
    data = movie_fixture(m, monkeypatch)
    targets, edits = m._watchdog(data)
    assert targets[0]["state"] == "original"
    off, old, new = edits[0]
    assert struct.unpack("<I", old) == (4000,)
    assert struct.unpack("<I", new) == (60000,)
    updated = bytearray(data)
    updated[off:off+4] = new
    assert m._watchdog(bytes(updated))[0][0]["state"] == "patched"
    updated[off:off+4] = bytes(4)
    with pytest.raises(PatchError, match="timer default"):
        m._watchdog(bytes(updated))
    updated = bytearray(data)
    updated[0x54c] ^= 4
    with pytest.raises(PatchError, match="menu flag"):
        m._menu_flag(m._helper().ElfImage(updated), bytes(updated))


def test_ui_groups_tiled_overlays_and_movie_screen_identity(tmp_path):
    import ctypes
    import shutil
    import subprocess
    compiler = shutil.which("cc")
    if not compiler:
        pytest.skip("C compiler unavailable")
    output = tmp_path / "groups.so"
    subprocess.run([compiler, "-shared", "-fPIC", "-O2", "-ffp-contract=off",
                    str(ROOT/"games/skate-3/overlay_classifier.c"), "-o", str(output)], check=True)
    classify = ctypes.CDLL(str(output)).full_canvas_overlay
    classify.argtypes = [ctypes.c_void_p]+[ctypes.c_uint]*5+[ctypes.c_void_p]*2
    vertices=[]
    def frame(rects):
        draws=ctypes.create_string_buffer(264*len(rects))
        for i,(box,texture,stride) in enumerate(rects):
            l,t,r,b=box
            pts=[(l,t),(r,t),(r,b),(l,b)]
            v=ctypes.create_string_buffer(b"".join(struct.pack("<7f",x,y,0,1,0,0,0) for x,y in pts))
            vertices.append(v)
            off=i*264
            struct.pack_into("<5I",draws,off+4,4,28,stride,0,8)
            tw,th,fmt,identity=texture
            struct.pack_into("<2I",draws,off+28,fmt|(identity<<12),(tw-1)|((th-1)<<13))
            projection=[2/1280,0,0,-1,0,-2/720,0,1,0,0,1,0,0,0,0,1]
            world=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
            struct.pack_into("<36f",draws,off+96,*(projection+world+[1,1,1,.4]))
            struct.pack_into("<2Q",draws,off+240,ctypes.addressof(v),ctypes.addressof(v)+len(pts)*28)
        return draws
    def check(draws,index=0,title=0,screen=0xffffffff,warmup=0,menu=0,video=0):
        a=ctypes.addressof(draws)
        return classify(a+index*264,title,screen,warmup,menu,video,a,a+len(draws))
    # The head would independently anchor upward. Its connected body/panel
    # crosses the old 40% boundary, so all three retain the same center anchor.
    coach=frame([((1100,250,1180,315),(128,128,20,1),24),
                 ((1100,315,1180,340),(128,32,20,2),24),
                 ((900,320,1190,410),(512,128,20,3),24),
                 ((100,600,320,650),(512,512,20,4),20)])
    assert [check(coach,i) for i in range(4)]==[0,0,0,4]
    # Neighboring text and glow cross the threshold but follow the whole group.
    top=frame([((80,210,320,278),(256,128,20,1),24),
               ((100,270,300,303),(512,512,20,2),20)])
    assert [check(top,i) for i in range(2)]==[3,3]
    # Large tutorial panel joins every fragment: no stretched header/body/footer.
    dialog=frame([((96,54,498,667),(512,512,20,1),24),
                  ((110,70,450,100),(512,512,20,2),20),
                  ((290,635,480,659),(512,512,20,3),20)])
    assert [check(dialog,i) for i in range(3)]==[0,0,0]
    # Repeating grain covers 1280x768, with padding outside the 720px canvas.
    grain=frame([((x,y,x+128,y+128),(128,128,20,9),24)
                 for y in range(0,768,128) for x in range(0,1280,128)])
    assert all(check(grain,i,title=1,warmup=1)==1 for i in range(60))
    partial=frame([((x,0,x+128,128),(128,128,20,9),24) for x in range(0,1280,128)])
    assert check(partial,title=1,warmup=1)==0
    glow=frame([((79.8,38,282.8,250),(32,32,20,1),24)])
    assert check(glow,title=1,warmup=1)==3
    for fmt, expected in ((20,2),(18,0)):
        title_art=frame([((0,0,1024,512),(1024,512,fmt,1),24),
                         ((1024,0,1280,512),(256,512,fmt,2),24),
                         ((0,512,1024,768),(1024,256,fmt,3),24),
                         ((1024,512,1280,768),(256,256,fmt,4),24),
                         ((658,76,914,332),(256,256,20,5),24)])
        assert check(title_art,4,title=257,warmup=1)==expected
    # Only the EA screen crops. Camera previews keep the dialog enlargement.
    movie=frame([((400,240,600,400),(256,128,6,1),24)])
    assert check(movie,title=1,warmup=1,video=1)==2
    assert check(movie,title=1,warmup=1,video=1,screen=9)==5
    assert check(movie,title=1,warmup=1,video=1,screen=24)==0
    assert check(movie,title=257,warmup=1,video=1)==0  # later attract movie


def test_movie_skip_mask_matches_big_endian_guest_buttons():
    target = next(t for t in module().NATIVE_TARGETS if "reserve movie skipping" in t["name"])
    instruction = struct.unpack_from("<I", bytes.fromhex(target["after"]), 4)[0]
    mask = (instruction >> 5) & 0xffff
    # X_INPUT_GAMEPAD.buttons is big-endian, read by a little-endian LDRH.
    for buttons, expected in ((0, False), (0x1000, False), (0x0010, True), (0x1010, True)):
        loaded = int.from_bytes(buttons.to_bytes(2, "big"), "little")
        assert bool(loaded & mask) is expected
