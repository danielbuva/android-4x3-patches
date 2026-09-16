"""Target-verified vertical expansion and proportional UI for Skate 3 Mobile."""
from __future__ import annotations

import importlib.util
import json
import struct
import sys
from pathlib import Path

from android4x3.errors import PatchError

NATIVE = "lib/arm64-v8a/libskate3.so"
DEX = "classes.dex"
RUNTIME = "lib/arm64-v8a/librexruntime.so"
REQUIRED_ENTRIES = (NATIVE, DEX, RUNTIME)
_HELPER = None
NATIVE_TARGETS = json.loads(Path(__file__).with_name("native-targets.json").read_text())
KEYBOARD_SYMBOL = "_ZN3rex6kernel3xam19KeyboardInputDialog6OnDrawER7ImGuiIO"
POSITION_SYMBOL = "_ZN5ImGui16SetNextWindowPosERK6ImVec2iS2_"
KEYBOARD_PREFIX = bytes.fromhex("ff8301d1fd7b02a9f85f03a9f65704a9")
KEYBOARD_MARKER = b"Android4x3:Skate3:Keyboard:1\0"
# Own ARM64 code: preserve arguments/LR, set position to (width/2,height/8)
# with a (1/2,0) pivot, call SetNextWindowPos, replay the displaced prologue.
# The BL at +56 and B at +76 are linked from discovered symbol addresses.
KEYBOARD_STUB = bytes.fromhex(
    "ffc300d1e00700a9fe0b00f92004412d02102c1e0310281e0008221e2108231e"
    "e007032de22300bdff2700b9e063009121008052e283009100000094e00740a9"
    "fe0b40f9ffc30091ff8301d100000014")


def _backgrounds():
    path = Path(__file__).with_name("backgrounds.py")
    spec = importlib.util.spec_from_file_location("android4x3_skate3_backgrounds", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe_game_data(data):
    return _backgrounds().probe_archive(data)


def patch_game_data(data):
    return _backgrounds().patch_archive(data)


def _helper():
    global _HELPER
    if _HELPER is None:
        path = Path(__file__).resolve().parents[2] / "tools" / "apkvision_neutralize.py"
        name = "android4x3_skate3_binary_helpers"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _HELPER = module
    return _HELPER


def _overall(targets):
    states = {t["state"] for t in targets}
    for state in ("unsupported", "ambiguous", "original"):
        if state in states:
            return state
    return "patched" if states == {"patched"} else "unsupported"


def _matches(data, needle, start, end):
    cursor = start
    while True:
        cursor = data.find(needle, cursor, end)
        if cursor < 0:
            break
        if cursor % 4 == 0:
            yield cursor
        cursor += 1


def _branch(source, destination, link=False):
    distance = destination - source
    if distance % 4 or not -(1 << 27) <= distance < (1 << 27):
        raise PatchError("ARM64 hook branch is out of range")
    return struct.pack("<I", (0x94000000 if link else 0x14000000) | ((distance // 4) & 0x3ffffff))


def _keyboard(data, _restored=False):
    """Add a small RX segment without moving existing code, data, or BSS.

    One optional PT_NOTE descriptor is reused; its note bytes and sections
    remain intact. The original descriptor/length are retained for exact
    post-state reconstruction. No absolute code/data address is embedded.
    """
    elf = _helper().ElfImage(data)
    if not elf.is_64 or elf.machine != elf.EM_AARCH64:
        raise PatchError("Skate 3 keyboard requires little-endian ARM64")
    symbols = [elf.dynamic_symbol_info(name) for name in (KEYBOARD_SYMBOL, POSITION_SYMBOL)]
    if any(s is None for s in symbols):
        raise PatchError("Native keyboard/position symbols missing")
    for symbol in symbols:
        if not any(p.p_type == 1 and p.flags & 1 and
                   p.vaddr <= symbol.value < symbol.value + symbol.size <= p.vaddr + p.filesz
                   for p in elf.program_headers):
            raise PatchError("Native dialog symbol is outside executable code")
    draw, position = symbols
    site = elf.va_to_offset(draw.value)
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phsize, phcount = struct.unpack_from("<HH", data, 54)
    if phsize != 56 or phcount != len(elf.program_headers):
        raise PatchError("Unsupported native program-header layout")
    marked = [(i, p) for i, p in enumerate(elf.program_headers)
              if p.p_type == 1 and p.flags == 5 and
              data[p.offset + p.filesz - len(KEYBOARD_MARKER):p.offset + p.filesz] == KEYBOARD_MARKER]
    target = {"name": "name-entry dialog above Android keyboard", "entry": RUNTIME}
    if marked:
        if _restored or len(marked) != 1:
            raise PatchError("Ambiguous native keyboard segment")
        index, segment = marked[0]
        size = len(KEYBOARD_STUB) + 64 + len(KEYBOARD_MARKER)
        if segment.filesz != size or segment.memsz != size or segment.offset + size != len(data):
            raise PatchError("Malformed native keyboard segment")
        record = segment.offset + len(KEYBOARD_STUB)
        old_header = data[record:record + 56]
        old_size = struct.unpack_from("<Q", data, record + 56)[0]
        if not phoff + phcount * phsize <= old_size <= segment.offset:
            raise PatchError("Malformed native keyboard original length")
        if segment.offset != ((old_size + 0x3fff) & ~0x3fff) or any(data[old_size:segment.offset]):
            raise PatchError("Malformed native keyboard alignment")
        original = bytearray(data[:old_size])
        original[phoff + index * 56:phoff + (index + 1) * 56] = old_header
        original[site:site + 4] = KEYBOARD_PREFIX[:4]
        _, expected = _keyboard(bytes(original), _restored=True)
        if not expected or expected[0][2] != data:
            raise PatchError("Native keyboard postcondition mismatch")
        return [{**target, "state": "patched"}], []
    if data[site:site + len(KEYBOARD_PREFIX)] != KEYBOARD_PREFIX:
        raise PatchError("Unrecognized native keyboard entry")
    notes = [(i, p) for i, p in enumerate(elf.program_headers) if p.p_type == 4 and p.flags == 4]
    if len(notes) != 1:
        raise PatchError("A unique optional ELF note descriptor is required")
    index, note = notes[0]
    if not any(p.p_type == 1 and p.offset <= note.offset and
               note.offset + note.filesz <= p.offset + p.filesz for p in elf.program_headers):
        raise PatchError("ELF note data is not retained in a load segment")
    align = 0x4000
    offset = (len(data) + align - 1) & ~(align - 1)
    address = (max(p.vaddr + p.memsz for p in elf.program_headers if p.p_type == 1)
               + align - 1) & ~(align - 1)
    stub = bytearray(KEYBOARD_STUB)
    stub[56:60] = _branch(address + 56, position.value, link=True)
    stub[76:80] = _branch(address + 76, draw.value + 4)
    header_offset = phoff + index * 56
    payload = (bytes(stub) + data[header_offset:header_offset + 56]
               + struct.pack("<Q", len(data)) + KEYBOARD_MARKER)
    result = bytearray(data)
    result[site:site + 4] = _branch(draw.value, address)
    struct.pack_into("<IIQQQQQQ", result, header_offset, 1, 5, offset, address,
                     address, len(payload), len(payload), align)
    result.extend(bytes(offset - len(result)))
    result.extend(payload)
    return [{**target, "state": "original"}], [(0, data, bytes(result))]


ASPECT_SETTER = "_ZN3rex8graphics26SetNativeGuestOutputAspectEd"
ASPECT_GETTER = "_ZN3rex8graphics26GetNativeGuestOutputAspectEv"


def _runtime_aspect(data):
    elf = _helper().ElfImage(data)
    setter = elf.dynamic_symbol_info(ASPECT_SETTER)
    getter = elf.dynamic_symbol_info(ASPECT_GETTER)
    if setter is None or getter is None or setter.size != 24 or getter.size != 12:
        raise PatchError("Runtime native-aspect accessor is missing or changed")
    for symbol in (setter, getter):
        if not any(p.p_type == 1 and p.flags & 1 and
                   p.vaddr <= symbol.value < symbol.value+symbol.size <= p.vaddr+p.filesz
                   for p in elf.program_headers):
            raise PatchError("Runtime aspect accessor is not executable")
    off = elf.va_to_offset(setter.value)
    a,b,page,select,store,ret = struct.unpack_from("<6I",data,off)
    old = (0x1e602018, 0x9e660009, 0x9a9fc129)
    new = (0xb200f3e9, 0xf2e7fea9, 0xd503201f)  # x9 = IEEE double 4/3
    if (a,b,select) not in (old,new) or page & 0x9f00001f != 0x90000008 or store & 0xffc003ff != 0xf9000109 or ret != 0xd65f03c0:
        raise PatchError("Unrecognized runtime aspect setter")
    target = _adrp_page(page,setter.value+8)+((store>>10)&4095)*8
    gpage,load,gret = struct.unpack_from("<3I",data,elf.va_to_offset(getter.value))
    if (gpage & 0x9f00001f != 0x90000008 or load & 0xffc003ff != 0xfd400100 or
        gret != 0xd65f03c0 or _adrp_page(gpage,getter.value)+((load>>10)&4095)*8 != target or
        not any(p.p_type == 1 and p.flags & 2 and p.vaddr<=target<=p.vaddr+p.memsz-8 for p in elf.program_headers)):
        raise PatchError("Runtime aspect getter/storage does not match setter")
    before = struct.pack("<6I",old[0],old[1],page,old[2],store,ret)
    after = struct.pack("<6I",new[0],new[1],page,new[2],store,ret)
    return [{"name":"retain 4:3 output when native settings are applied", "entry":RUNTIME,
             "state":"original" if (a,b,select)==old else "patched"}], [(off,before,after)]


def _runtime(data):
    targets, edits = _runtime_aspect(data)
    result = bytearray(data)
    for off, before, after in edits:
        result[off:off+len(before)] = after
    keyboard_targets, keyboard_edits = _keyboard(bytes(result))
    targets.extend(keyboard_targets)
    for off,before,after in keyboard_edits:
        result[off:off+len(before)] = after
    return targets, [(0,data,bytes(result))] if result!=data else []


MOVIE_SYMBOL = "_ZN6skate39demo_path29ShouldForceIntroMovieCompleteEv"
MOVIE_MARKER = b"Android4x3:Skate3:EAIntroAndOverlays:1\0"
# Own ARM64 code. Only a YUV draw while the first boot movie is active uses
# reciprocal X scaling. Full-canvas dark/solid overlays bypass Y expansion;
# other draws resume the normal Y transform. Preserve all live registers across
# the classifier, including x8 (ortho flag) and v1 (normal scale).
DISPLAY_HOOK = json.loads(Path(__file__).with_name("display-hook.json").read_text())
MOVIE_STUB = bytes.fromhex(DISPLAY_HOOK["code"])
MOVIE_LINKS = DISPLAY_HOOK["links"]
MOVIE_CONTEXT = bytes.fromhex("c9f588525f0300f129f0a7722001271e")


def _offset_va(elf, offset):
    return next(p.vaddr + offset - p.offset for p in elf.program_headers
                if p.p_type == 1 and p.offset <= offset < p.offset + p.filesz)


def _adrp_page(word, address):
    value = ((word >> 5) & 0x7ffff) * 4 + ((word >> 29) & 3)
    if value & (1 << 20):
        value -= 1 << 21
    return (address & ~0xfff) + value * 4096


def _movie_flags(elf, data):
    """Resolve the existing first-movie lifecycle flags from their load sites.

    The recognized TBZ must lead to the started test. Both byte addresses must
    be adjacent in writable memory. No game filename, global offset, or process
    address is hardcoded, and neither flag nor the watchdog is modified.
    """
    symbol = elf.dynamic_symbol_info(MOVIE_SYMBOL)
    if symbol is None or not any(p.p_type == 1 and p.flags & 1 and
            p.vaddr <= symbol.value < symbol.value + symbol.size <= p.vaddr + p.filesz
            for p in elf.program_headers):
        raise PatchError("Boot movie lifecycle symbol missing or not executable")
    start = elf.va_to_offset(symbol.value)
    found = []
    for off in range(start, start + symbol.size - 19, 4):
        a, move, b, load, branch = struct.unpack_from("<5I", data, off)
        if not (a & 0x9f00001f == 0x90000018 and move == 0xaa0003f3 and
                b & 0x9f00001f == 0x90000019 and load & 0xffc003ff == 0x39400308 and
                branch & 0xfff8001f == 0x36000008):
            continue
        displacement = (branch >> 5) & 0x3fff
        if displacement & 0x2000:
            displacement -= 0x4000
        dest = off + 16 + displacement * 4
        if not start <= dest <= start + symbol.size - 16:
            continue
        c, load2, compare, conditional = struct.unpack_from("<4I", data, dest)
        if not (c & 0x9f00001f == 0x9000001a and load2 & 0xffc003ff == 0x39400348 and
                compare == 0x7100051f and conditional & 0xff00001f == 0x54000001):
            continue
        consumed = _adrp_page(a, _offset_va(elf, off)) + ((load >> 10) & 4095)
        started = _adrp_page(c, _offset_va(elf, dest)) + ((load2 >> 10) & 4095)
        if consumed == started + 1 and started % 2 == 0 and any(
                p.p_type == 1 and p.flags & 2 and p.vaddr <= started and
                consumed < p.vaddr + p.memsz for p in elf.program_headers):
            found.append(started)
    if len(found) != 1:
        raise PatchError("Boot movie lifecycle loads are missing or ambiguous")
    return found[0]


def _movie_site(elf, data):
    spec = next(s for s in NATIVE_TARGETS if s["name"] == "UI scale Y")
    # Skip the first instruction, which is replaced by a branch in post-state.
    tails = {bytes.fromhex(spec[k])[4:] + MOVIE_CONTEXT for k in ("before", "after")}
    found = {off - 4 for p in elf.program_headers if p.p_type == 1 and p.flags & 1
             for tail in tails for off in _matches(data, tail, p.offset + 4, p.offset + p.filesz)}
    if len(found) != 1:
        raise PatchError("Movie projection site is missing or ambiguous")
    return found.pop()


MENU_CONTEXT_SYMBOL = "_ZN6skate312native_scene23LoadingOrFrontendActiveEv"
WARMUP_SYMBOL = "_ZN6skate312native_scene14g_warmup_armedE"
WATCHDOG_SYMBOL = "_Z44FLAGS_skate3_boot_movie_watchdog_ms_storage_v"


def _menu_flag(elf, data):
    context = elf.dynamic_symbol_info(MENU_CONTEXT_SYMBOL)
    if context is None:
        raise PatchError("Frontend context symbol missing")
    off = elf.va_to_offset(context.value)
    prefix = bytes.fromhex("fd7bbea9f30b00f9fd030091")
    if data[off:off + 12] != prefix:
        raise PatchError("Unrecognized frontend context function")
    call = struct.unpack_from("<I", data, off + 12)[0]
    if call & 0xfc000000 != 0x94000000:
        raise PatchError("Frontend presence call missing")
    def branch_target(word, address):
        delta = word & 0x3ffffff
        if delta & 0x2000000:
            delta -= 0x4000000
        return address + delta * 4
    presence = branch_target(call, context.value + 12)
    found = []
    for seg in elf.program_headers:
        if seg.p_type != 1 or not seg.flags & 1:
            continue
        for off in _matches(data, bytes.fromhex("1f000071f403002a"), seg.offset + 4, seg.offset + seg.filesz - 24):
            prior = struct.unpack_from("<I", data, off - 4)[0]
            page, eq, page2, store, zero = struct.unpack_from("<5I", data, off + 8)
            if not (prior & 0xfc000000 == 0x94000000 and
                    branch_target(prior, _offset_va(elf, off - 4)) == presence and
                    page & 0x9f00001f == 0x90000008 and eq == 0x1a9f17e9 and
                    page2 & 0x9f00001f == 0x9000001b and store & 0xffc003ff == 0x39000109 and
                    zero & 0xff00001f == 0x34000000):
                continue
            address = _adrp_page(page, _offset_va(elf, off + 8)) + ((store >> 10) & 4095)
            if any(p.p_type == 1 and p.flags & 2 and p.vaddr <= address < p.vaddr + p.memsz
                   for p in elf.program_headers):
                found.append(address)
    if len(found) != 1:
        raise PatchError("Render-thread menu flag is missing or ambiguous")
    return found[0]


def _hud_end(elf, data):
    # Existing safe-area gate; the new grouped classifier bypasses this entire
    # per-draw translation block. Its forward conditional branch names the exit.
    gate = bytes.fromhex("e913881a2020201e2d0c0054090c0034")
    found = [off for p in elf.program_headers if p.p_type == 1 and p.flags & 1
             for off in _matches(data, gate, p.offset, p.offset+p.filesz)]
    if len(found) != 1:
        raise PatchError("HUD gate is missing or ambiguous")
    branch = struct.unpack_from("<I", data, found[0]+8)[0]
    delta = (branch >> 5) & 0x7ffff
    if delta & 0x40000:
        delta -= 0x80000
    return _offset_va(elf, found[0]+8) + delta*4


def _watchdog(data):
    elf = _helper().ElfImage(data)
    symbol = elf.dynamic_symbol_info(WATCHDOG_SYMBOL)
    if symbol is None or symbol.size != 12:
        raise PatchError("Startup movie timer storage symbol missing")
    off = elf.va_to_offset(symbol.value)
    page, add, ret = struct.unpack_from("<3I", data, off)
    if not (page & 0x9f00001f == 0x90000000 and add & 0xffc003ff == 0x91000000 and ret == 0xd65f03c0):
        raise PatchError("Unrecognized startup movie timer storage accessor")
    address = _adrp_page(page, symbol.value) + ((add >> 10) & 4095)
    if not any(p.p_type == 1 and p.flags & 2 and p.vaddr <= address <= p.vaddr+p.filesz-4
               for p in elf.program_headers):
        raise PatchError("Startup movie timer is outside writable file-backed data")
    off = elf.va_to_offset(address)
    old, new = struct.pack("<I", 4000), struct.pack("<I", 60000)
    value = data[off:off+4]
    if value not in (old,new):
        raise PatchError("Unrecognized startup movie timer default")
    return [{"name": "allow full EA intro before 60-second recovery timeout", "entry": NATIVE,
             "state": "original" if value == old else "patched"}], [(off,old,new)]


FRONTEND_SYMBOL = "_ZN6skate312native_scene14g_fe_stack_topE"


def _scene_stack(elf, data, site):
    """Discover the immutable local Draw2d vector from the guarded render loop.

    The loaded iterator/end registers and 264-byte increment tie this stack
    slot to the same draw layout used by the hook. No shared vector is read.
    """
    ranges = [(p.offset, p.offset+p.filesz) for p in elf.program_headers
              if p.p_type == 1 and p.flags & 1 and p.offset <= site < p.offset+p.filesz]
    if len(ranges) != 1:
        raise PatchError("UI frame snapshot is not executable")
    found = []
    start = max(ranges[0][0], site-4096)
    for off in range((start+3)&~3, site-20, 4):
        a,b,c,d,e = struct.unpack_from("<5I",data,off)
        if (a & 0xffc003ff != 0xf94003f6 or b & 0xffc003ff != 0xf94003f7 or
            c & 0xffc003ff != 0xf90003ff or d & 0xffc003ff != 0xf90003ff or e != 0xeb1702df):
            continue
        slot=((a>>10)&4095)*8
        if ((b>>10)&4095)*8 != slot+8 or slot+680>32760:
            continue
        loop=bytes.fromhex("d6220491df0217eb")  # next Draw2d; compare iterator/end
        if len(list(_matches(data,loop,off+20,site))) == 1:
            found.append(slot)
    if len(found) != 1:
        raise PatchError("UI frame snapshot layout is missing or ambiguous")
    return found[0]


def _movie(data, _restored=False):
    elf = _helper().ElfImage(data)
    if not elf.is_64 or elf.machine != elf.EM_AARCH64:
        raise PatchError("EA movie crop requires little-endian ARM64")
    site = _movie_site(elf, data)
    flags = _movie_flags(elf, data)
    menu = _menu_flag(elf, data)
    warmup_symbol = elf.dynamic_symbol_info(WARMUP_SYMBOL)
    if warmup_symbol is None or warmup_symbol.size != 1 or not any(
            p.p_type == 1 and p.flags & 2 and p.vaddr <= warmup_symbol.value < p.vaddr+p.memsz
            for p in elf.program_headers):
        raise PatchError("Native world-readiness flag missing")
    warmup = warmup_symbol.value
    hud_end = _hud_end(elf, data)
    frontend_symbol = elf.dynamic_symbol_info(FRONTEND_SYMBOL)
    if frontend_symbol is None or frontend_symbol.size != 4 or not any(
            p.p_type == 1 and p.flags & 2 and p.vaddr <= frontend_symbol.value <= p.vaddr+p.memsz-4
            for p in elf.program_headers):
        raise PatchError("Frontend screen stack symbol missing")
    frontend = frontend_symbol.value
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phsize, phcount = struct.unpack_from("<HH", data, 54)
    if phsize != 56 or phcount != len(elf.program_headers):
        raise PatchError("Unsupported native program-header layout")
    marked = [(i, p) for i, p in enumerate(elf.program_headers)
              if p.p_type == 1 and p.flags == 5 and
              data[p.offset + p.filesz - len(MOVIE_MARKER):p.offset + p.filesz] == MOVIE_MARKER]
    prefix = bytes.fromhex("e9032491")  # add x9,sp,#0x900
    if marked:
        if _restored or len(marked) != 1:
            raise PatchError("Ambiguous EA movie segment")
        index, segment = marked[0]
        size = len(MOVIE_STUB) + 64 + len(MOVIE_MARKER)
        if segment.filesz != size or segment.memsz != size or segment.offset + size != len(data):
            raise PatchError("Malformed EA movie segment")
        record = segment.offset + len(MOVIE_STUB)
        old_header = data[record:record + 56]
        old_size = struct.unpack_from("<Q", data, record + 56)[0]
        if not phoff + phcount * phsize <= old_size <= segment.offset:
            raise PatchError("Malformed EA movie original length")
        if segment.offset != ((old_size + 0x3fff) & ~0x3fff) or any(data[old_size:segment.offset]):
            raise PatchError("Malformed EA movie alignment")
        original = bytearray(data[:old_size])
        original[phoff + index * 56:phoff + (index + 1) * 56] = old_header
        original[site:site + 4] = prefix
        original = bytes(original)
        expected, _, _ = _movie(original, _restored=True)
        if expected != data:
            raise PatchError("EA movie postcondition mismatch")
        return data, original, "patched"
    if data[site:site + 4] != prefix:
        raise PatchError("Unrecognized movie projection entry")
    notes = [(i, p) for i, p in enumerate(elf.program_headers) if p.p_type == 4 and p.flags == 4]
    if len(notes) != 1:
        raise PatchError("A unique optional ELF note descriptor is required")
    index, note = notes[0]
    if not any(p.p_type == 1 and p.offset <= note.offset and
               note.offset + note.filesz <= p.offset + p.filesz for p in elf.program_headers):
        raise PatchError("ELF note data is not retained in a load segment")
    align = 0x4000
    offset = (len(data) + align - 1) & ~(align - 1)
    address = (max(p.vaddr + p.memsz for p in elf.program_headers if p.p_type == 1)
               + align - 1) & ~(align - 1)
    site_va = _offset_va(elf, site)
    stub = bytearray(MOVIE_STUB)
    for label in ("ea_return", "normal_return", "overlay_return"):
        off = MOVIE_LINKS[label]
        stub[off:off + 4] = _branch(address + off, hud_end)
    scene_stack = _scene_stack(elf, data, site)
    for label, register, target in (("scene_begin_load", 6, scene_stack + 672),
                                    ("scene_end_load", 7, scene_stack + 680)):
        struct.pack_into("<I", stub, MOVIE_LINKS[label], 0xf94003e0 | register | ((target//8)<<10))
    for label, target, register, byte in (("title", flags, 1, 2), ("screen", frontend, 2, False),
                                          ("warmup", warmup, 3, True), ("menu", menu, 4, True)):
        off = MOVIE_LINKS["class_" + label + "_page"]
        delta = ((target & ~0xfff) - ((address + off) & ~0xfff)) // 4096
        if not -(1 << 20) <= delta < (1 << 20) or (not byte and target % 4):
            raise PatchError("Classifier state address is out of range or unaligned")
        struct.pack_into("<I", stub, off, 0x90000009 | ((delta & 3) << 29) | (((delta >> 2) & 0x7ffff) << 5))
        width = 2 if byte == 2 else 1 if byte else 4
        opcode = {1:0x39400120, 2:0x79400120, 4:0xb9400120}[width]
        load = opcode | register | (((target & 4095)//width)<<10)
        struct.pack_into("<I", stub, MOVIE_LINKS["class_" + label + "_load"], load)
    header_offset = phoff + index * 56
    payload = bytes(stub) + data[header_offset:header_offset + 56] + struct.pack("<Q", len(data)) + MOVIE_MARKER
    result = bytearray(data)
    result[site:site + 4] = _branch(site_va, address)
    struct.pack_into("<IIQQQQQQ", result, header_offset, 1, 5, offset, address,
                     address, len(payload), len(payload), align)
    result.extend(bytes(offset - len(result)))
    result.extend(payload)
    return bytes(result), data, "original"


def _main(data):
    _, unwrapped, movie_state = _movie(data)
    targets, edits = _native(unwrapped)
    timer_targets, timer_edits = _watchdog(unwrapped)
    targets.extend(timer_targets)
    edits.extend(timer_edits)
    if _overall(targets) not in ("original", "patched"):
        return targets, []
    updated = bytearray(unwrapped)
    for off, before, after in edits:
        updated[off:off + len(before)] = after
    result, _, _ = _movie(bytes(updated))
    targets.append({"name": "EA startup movie proportional cover crop", "entry": NATIVE, "state": movie_state})
    targets.append({"name": "keep complete HUD and dialog components registered", "entry": NATIVE, "state": movie_state})
    targets.append({"name": "full-canvas dark overlays and transition fills", "entry": NATIVE, "state": movie_state})
    targets.append({"name": "cover title and difficulty artwork while preserving foreground", "entry": NATIVE, "state": movie_state})
    targets.append({"name": "title foreground and loading indicator perimeter positions", "entry": NATIVE, "state": movie_state})
    targets.append({"name": "extend tiled grain and dark overlay layers to the full canvas", "entry": NATIVE, "state": movie_state})
    targets.append({"name": "enlarge startup dialogs and camera previews together", "entry": NATIVE, "state": movie_state})
    return targets, [(0, data, result)] if result != data else []


def _native(data):
    elf = _helper().ElfImage(data)
    if not elf.is_64 or elf.machine != elf.EM_AARCH64:
        raise PatchError("Skate 3 requires the audited little-endian ARM64 ELF")
    targets, edits = [], []
    for spec in NATIVE_TARGETS:
        original, patched = bytes.fromhex(spec["before"]), bytes.fromhex(spec["after"])
        ranges = [(s.offset, s.offset + s.filesz) for s in elf.program_headers
                  if s.p_type == elf.PT_LOAD and s.flags & elf.PF_X]
        if spec.get("symbol"):
            symbol = elf.dynamic_symbol_info(spec["symbol"])
            if symbol is None:
                ranges = []
            else:
                start = elf.va_to_offset(symbol.value)
                end = start + symbol.size
                ranges = [(start, end)] if any(a <= start < end <= b for a, b in ranges) else []
        found = [(off, state) for a, b in ranges
                 for needle, state in ((original, "original"), (patched, "patched"))
                 for off in _matches(data, needle, a, b)]
        state = found[0][1] if len(found) == 1 else "ambiguous" if found else "unsupported"
        targets.append({"name": spec["name"], "entry": NATIVE, "state": state, "matches": len(found)})
        if len(found) == 1:
            edits.append((found[0][0], original, patched))
    return targets, edits


def _dex(data):
    dex = _helper().DexImage(data)
    identity = ("Lchat/buku/skate3/Skate3Activity;", "onCreate", "(Landroid/os/Bundle;)V")
    methods = [m for m in dex.methods() if (m.class_descriptor, m.name, m.descriptor) == identity]
    target = {"name": "detach Android touch overlay", "entry": DEX, "state": "unsupported"}
    if len(methods) != 1:
        if methods:
            target["state"] = "ambiguous"
        return [target], []
    method = methods[0]
    dex._check(method.code_offset, 16)
    registers, incoming, _out, tries = struct.unpack_from("<HHHH", data, method.code_offset)
    start = method.code_offset + 16
    end = start + dex._u32(method.code_offset + 12) * 2
    dex._check(start, end - start)
    if tries or incoming != 2 or registers < 3:
        return [target], []
    # The final addView attaches only TouchControllerView. Require its precise
    # method identity and the preceding LayoutParams(-1, -1) constructor. No
    # method indices, DEX file offsets, package version or whole-file hash gates.
    add = ("Landroid/view/ViewGroup;", "addView", "(Landroid/view/View;Landroid/view/ViewGroup$LayoutParams;)V")
    init = ("Landroid/view/ViewGroup$LayoutParams;", "<init>", "(II)V")
    ids = {dex._method_identity(i): i for i in range(dex.method_ids_size)}
    if add not in ids or init not in ids or registers > 16:
        return [target], []
    fields = []
    for index in range(dex._u32(0x50)):
        offset = dex._u32(0x54) + index * 8
        dex._check(offset, 8)
        owner, kind, name = struct.unpack_from("<HHI", data, offset)
        if (dex.types[owner], dex.types[kind], dex.strings[name]) == (
            identity[0], "Lchat/buku/skate3/TouchControllerView;", "touchController"
        ):
            fields.append(index)
    layout = "Landroid/view/ViewGroup$LayoutParams;"
    if len(fields) != 1 or dex.types.count(layout) != 1:
        return [target], []
    this, state_reg = registers - 2, registers - 1
    original = struct.pack("<HHH", 0x306e, ids[add], state_reg | (this << 4))
    patched = b"\0" * 6
    # Both variants must terminate the method; the code immediately before
    # the invocation constructs full-screen LayoutParams in v0 with v1=-1.
    prefix = (struct.pack("<HH", 0x54 | this << 8 | this << 12, fields[0])
              + struct.pack("<HH", 0x22, dex.types.index(layout))
              + b"\x12\xf1" + struct.pack("<HHH", 0x3070, ids[init], 0x110))
    found = []
    for needle, state in ((original, "original"), (patched, "patched")):
        pattern = prefix + needle + b"\x0e\x00"
        for off in range(start, end - len(pattern) + 1, 2):
            if data[off:off + len(pattern)] == pattern and off + len(pattern) == end:
                found.append((off + len(prefix), state))
    target["state"] = found[0][1] if len(found) == 1 else "ambiguous" if found else "unsupported"
    return [target], [(found[0][0], original, patched)] if len(found) == 1 else []


def probe(extracted):
    targets = []
    for entry, discover in ((NATIVE, _main), (DEX, _dex), (RUNTIME, _runtime)):
        try:
            if entry not in extracted:
                raise PatchError("required entry missing")
            current, _ = discover(Path(extracted[entry]).read_bytes())
            targets.extend(current)
        except Exception as exc:
            targets.append({"name": entry, "entry": entry, "state": "unsupported", "reason": str(exc)})
    for entry in extracted:
        if ((entry.endswith("/libskate3.so") and entry != NATIVE) or
                (entry.endswith("/librexruntime.so") and entry != RUNTIME)):
            targets.append({"name": entry, "state": "unsupported", "reason": "unaudited architecture"})
    return {"state": _overall(targets), "targets": targets}


def apply(extracted, output_dir):
    initial = probe(extracted)
    if initial["state"] not in ("original", "patched"):
        raise PatchError(f"Skate 3 targets are {initial['state']}; refusing to guess")
    replacements = {}
    for entry, discover in ((NATIVE, _main), (DEX, _dex), (RUNTIME, _runtime)):
        original = Path(extracted[entry]).read_bytes()
        targets, edits = discover(original)
        if _overall(targets) not in ("original", "patched"):
            raise PatchError("Skate 3 targets changed during patching")
        data = bytearray(original)
        for off, before, after in edits:
            if data[off:off + len(before)] not in (before, after):
                raise PatchError("Skate 3 target changed during patching")
            data[off:off + len(before)] = after
        result = bytes(data)
        if result == original:
            continue
        if entry == DEX:
            result = _helper().DexImage(result).finish()
        if _overall(discover(result)[0]) != "patched":
            raise PatchError("Skate 3 postcondition failed")
        destination = Path(output_dir) / entry
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(result)
        replacements[entry] = destination
    final = probe({**extracted, **replacements})
    if final["state"] != "patched":
        raise PatchError("Skate 3 combined postcondition failed")
    return replacements
