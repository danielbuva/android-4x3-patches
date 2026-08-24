"""Experimental Baba Is You 4:3 native-code transformation.

The original development script addressed one tested libChowdren.so by file
offset and rejected every other complete-library hash. This module keeps the
same instruction changes, but locates each small code region through invariant
surrounding instructions. Offsets below are relative to those unique regions,
not absolute ELF offsets.

The transformation intentionally excludes all later Baba diagnostic, menu,
and touch-selector experiments.
"""

from __future__ import annotations

from pathlib import Path


LIB_ENTRY = "lib/arm64-v8a/libChowdren.so"
REQUIRED_ENTRIES = (LIB_ENTRY,)


# Each region is located by invariant instructions immediately before and
# after its mutable span. A few invariant instructions inside longer spans
# provide additional context so a coincidental byte sequence is never patched.
# Target tuples are: (name, relative offset, original, desired, old aliases).
_REGIONS = (
    {
        "name": "generic-frame-height",
        "before": "fd8300911f040031",
        "span": 8,
        "after": "57d03bd5f303032a",
        "landmarks": (),
        "targets": (
            ("generic-height-480-to-640", 0, "083c8052", "08508052", ("08518052",)),
            ("generic-width-normalization", 4, "c96a8052", "c96a8052", ("096c8052",)),
        ),
    },
    {
        "name": "baba-view-geometry",
        "before": "10102e1e0800381e4418231e",
        "span": 116,
        "after": "9f010b6ba4bc211e4218241e",
        "landmarks": (
            (4, "2001221e"),
            (16, "2101271e"),
            (24, "2501221e"),
            (32, "2601271e"),
            (44, "2118201e"),
            (104, "2c00381e"),
            (108, "2101271e"),
        ),
        "targets": (
            ("baba-height-and-border", 0, "09810711", "09010a11", ("09210a11",)),
            ("old-width-constant-a", 8, "09009052", "09009052", ("09008052",)),
            ("old-width-float-a", 12, "a98aa872", "a98aa872", ("098ba872",)),
            ("old-height-adjustment", 20, "09590d11", "09590d11", ("09810d11",)),
            ("baba-height-float-a", 28, "097ea852", "0984a852", ("4984a852",)),
            ("old-width-constant-b", 36, "09009052", "09009052", ("09008052",)),
            ("old-width-float-b", 40, "a98aa872", "a98aa872", ("098ba872",)),
            ("baba-height-float-b", 112, "097ea852", "0984a852", ("4984a852",)),
        ),
    },
    {
        "name": "fullscreen-game-output",
        "before": "bf0100718b010b4bcc7d0113",
        "span": 88,
        "after": "48fd05b928a5891a",
        "landmarks": (
            (8, "aba58d1a"),
            (12, "1f010071"),
            (20, "6a7d0113"),
            (24, "8901090b"),
            (32, "0ba5881a"),
            (40, "49058b0b"),
            (44, "eb2f0090"),
            (52, "4901094b"),
            (56, "ea2f0090"),
            (80, "eb2f0090"),
        ),
        "targets": (
            ("drawable-right", 0, "4b0000b9", "440000b9", ()),
            ("preserve-touch-left", 4, "6a010a4b", "6e010a4b", ()),
            ("drawable-left", 16, "0a0000b9", "1f0000b9", ()),
            ("drawable-top", 28, "2c0000b9", "3f0000b9", ()),
            ("drawable-bottom", 36, "690000b9", "650000b9", ()),
            ("restore-touch-left", 48, "0a0040b9", "ea030e2a", ()),
            ("retain-touch-top", 84, "280040b9", "e8030c2a", ()),
        ),
    },
    {
        "name": "lua-layout-width",
        "before": "08fc43b30001679ed2910d94",
        "span": 4,
        "after": "d4910d94600e40b9d2910d94",
        "landmarks": (),
        "targets": (
            ("lua-screen-width-854", 0, "600a40b9", "c06a8052", ()),
        ),
    },
    {
        "name": "horizontal-camera-origin",
        "before": "3f04003108184091a0010054",
        "span": 24,
        "after": "4a590d515f01096b49b1891a",
        "landmarks": (
            (8, "0a1040b9"),
            (12, "29c0891a"),
            (16, "0bad47b9"),
        ),
        "targets": (
            ("camera-origin-compare", 0, "3fac0671", "3fe40871", ()),
            ("camera-origin-clamp", 4, "69358052", "29478052", ()),
            ("camera-origin-subtract", 20, "29ad0651", "29e50851", ()),
        ),
    },
)


def _all_occurrences(data: bytes, needle: bytes):
    start = 0
    while True:
        found = data.find(needle, start)
        if found < 0:
            return
        yield found
        start = found + 1


def _locate_region(data: bytes, region: dict) -> list[int]:
    before = bytes.fromhex(region["before"])
    after = bytes.fromhex(region["after"])
    span = region["span"]
    candidates: list[int] = []
    for anchor in _all_occurrences(data, before):
        base = anchor + len(before)
        if data[base + span : base + span + len(after)] != after:
            continue
        if any(
            data[base + relative : base + relative + len(bytes.fromhex(value))]
            != bytes.fromhex(value)
            for relative, value in region["landmarks"]
        ):
            continue
        candidates.append(base)
    return candidates


def _probe_bytes(data: bytes) -> dict:
    targets: list[dict] = []
    has_original = False
    has_unsupported = False
    has_ambiguous = False

    for region in _REGIONS:
        candidates = _locate_region(data, region)
        if len(candidates) != 1:
            state = "ambiguous" if len(candidates) > 1 else "unsupported"
            targets.append(
                {
                    "name": region["name"],
                    "state": state,
                    "matches": len(candidates),
                }
            )
            has_ambiguous |= len(candidates) > 1
            has_unsupported |= not candidates
            continue

        base = candidates[0]
        for name, relative, original_hex, desired_hex, aliases_hex in region["targets"]:
            desired = bytes.fromhex(desired_hex)
            recognized_originals = {bytes.fromhex(original_hex)}
            recognized_originals.update(bytes.fromhex(value) for value in aliases_hex)
            actual = bytes(data[base + relative : base + relative + len(desired)])
            if actual == desired:
                state = "patched"
            elif actual in recognized_originals:
                state = "original"
                has_original = True
            else:
                state = "unsupported"
                has_unsupported = True
            target = {
                "name": name,
                "region": region["name"],
                "state": state,
                "offset": base + relative,
            }
            if state == "unsupported":
                target["found"] = actual.hex()
            targets.append(target)

    if has_ambiguous:
        state = "ambiguous"
    elif has_unsupported:
        state = "unsupported"
    elif has_original:
        state = "original"
    else:
        state = "patched"
    return {"state": state, "targets": targets}


def _source(extracted: dict[str, Path]) -> Path | None:
    value = extracted.get(LIB_ENTRY)
    if value is None:
        return None
    path = Path(value)
    return path if path.is_file() else None


def probe(extracted: dict[str, Path]) -> dict:
    """Classify the required native renderer targets without modifying them."""

    library = _source(extracted)
    if library is None:
        return {
            "state": "unsupported",
            "targets": [
                {
                    "name": LIB_ENTRY,
                    "state": "unsupported",
                    "reason": "required ARM64 library is missing",
                }
            ],
        }
    return _probe_bytes(library.read_bytes())


def apply(extracted: dict[str, Path], output_dir: Path) -> dict[str, Path]:
    """Apply recognized original targets and emit one replacement APK entry."""

    source = _source(extracted)
    if source is None:
        raise RuntimeError(f"missing required entry: {LIB_ENTRY}")
    data = bytearray(source.read_bytes())
    result = _probe_bytes(data)
    if result["state"] == "ambiguous":
        raise RuntimeError("Baba Is You renderer targets are ambiguous; refusing to guess")
    if result["state"] == "unsupported":
        raise RuntimeError("Baba Is You renderer targets are not a supported instruction layout")

    for region in _REGIONS:
        matches = _locate_region(data, region)
        if len(matches) != 1:
            raise RuntimeError(f"Baba Is You target region changed during patching: {region['name']}")
        base = matches[0]
        for _name, relative, _original, desired_hex, _aliases in region["targets"]:
            desired = bytes.fromhex(desired_hex)
            data[base + relative : base + relative + len(desired)] = desired

    verified = _probe_bytes(data)
    if verified["state"] != "patched":
        raise RuntimeError("Baba Is You post-patch verification failed")

    destination = Path(output_dir) / LIB_ENTRY
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return {LIB_ENTRY: destination}
