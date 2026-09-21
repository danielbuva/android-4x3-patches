"""Build the original-aspect companion with startup and controller improvements."""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from android4x3.apk import extract_entries, inspect_apk, repack_with_optional_branding, verify_zip
from android4x3.errors import PatchError
from android4x3.registry import Registry
from android4x3.signing import align_apk, sign_apk


def build(source: Path, output: Path) -> None:
    source, output = source.expanduser().resolve(), output.expanduser().resolve()
    if source == output or output.exists():
        raise PatchError("Choose a new output filename; existing files are never overwritten")
    verify_zip(source, full=True, allow_signatures=True)
    if inspect_apk(source).package != "com.abylight.HyperLightDrifter":
        raise PatchError("Expected a Hyper Light Drifter APK")
    registry = Registry(REPO / "games")
    module = registry.module(registry.by_id["hyper-light-drifter"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hld-", dir=output.parent) as temporary:
        work = Path(temporary)
        entries = extract_entries(source, module.REQUIRED_ENTRIES, work / "input")
        if module.state(entries[module.GAME].read_bytes(), "game") != "original":
            raise PatchError("Original-aspect build requires original room data")
        replacement = work / "libyoyo.so"
        replacement.write_bytes(module.patch_native(entries[module.LIBRARY].read_bytes(), original_aspect=True))
        unsigned, aligned, signed = (work / n for n in ("unsigned.apk", "aligned.apk", "signed.apk"))
        repack_with_optional_branding(REPO, source, unsigned, {module.LIBRARY: replacement})
        verify_zip(unsigned, full=True)
        align_apk(unsigned, aligned)
        sign_apk(aligned, signed)
        final = extract_entries(signed, module.REQUIRED_ENTRIES, work / "verified")
        if module.state(final[module.LIBRARY].read_bytes(), "native") != "original_aspect":
            raise PatchError("Native output verification failed")
        if final[module.GAME].read_bytes() != entries[module.GAME].read_bytes():
            raise PatchError("Original room data changed during repacking")
        os.replace(signed, output)
    print(f"Structurally verified original-aspect APK: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/Hyper-Light-Drifter-v1.1.99-original-aspect.apk"))
    args = parser.parse_args()
    try:
        build(args.input, args.output)
    except (PatchError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
