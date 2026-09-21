"""Build the original-aspect companion with the Android border fix."""
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
    if inspect_apk(source).package != "com.aurogon.Afterimage":
        raise PatchError("Expected an Afterimage APK")
    registry = Registry(REPO / "games")
    module = registry.module(registry.by_id["afterimage"])
    output.parent.mkdir(parents=True, exist_ok=True)
    # Staging beside output permits an atomic move, including across Windows drives.
    with tempfile.TemporaryDirectory(prefix="afterimage-", dir=output.parent) as temporary:
        work = Path(temporary)
        entries = extract_entries(source, module.REQUIRED_ENTRIES, work / "input")
        if any(s != "original" for s in module.native_state(entries[module.LIBRARY].read_bytes())):
            raise PatchError("Original-aspect build requires an unmodified camera library")
        _, resources = module.focus_theme(entries[module.RESOURCES].read_bytes())
        replacement = work / "resources.arsc"
        replacement.write_bytes(resources)
        unsigned, aligned, signed = (work / n for n in ("unsigned.apk", "aligned.apk", "signed.apk"))
        repack_with_optional_branding(REPO, source, unsigned, {module.RESOURCES: replacement})
        verify_zip(unsigned, full=True)
        align_apk(unsigned, aligned)
        sign_apk(aligned, signed)
        final = extract_entries(signed, module.REQUIRED_ENTRIES, work / "verified")
        if final[module.LIBRARY].read_bytes() != entries[module.LIBRARY].read_bytes():
            raise PatchError("Original camera library changed during repacking")
        if module.focus_theme(final[module.RESOURCES].read_bytes())[0] != "patched":
            raise PatchError("Theme verification failed")
        os.replace(signed, output)
    print(f"Verified original-aspect APK: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/Afterimage-v1.0.4-original-aspect.apk"))
    args = parser.parse_args()
    try:
        build(args.input, args.output)
    except (PatchError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
