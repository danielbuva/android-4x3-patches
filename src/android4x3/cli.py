"""Command-line orchestrator for user-supplied APKs."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from .apk import extract_entries, inspect_apk, repack_with_optional_branding, resolve_entries, verify_zip
from .errors import PatchError, ReportedPatchError
from .registry import GameConfig, Registry
from .signing import align_apk, sign_apk, verify_alignment


VALID_STATES = {"original", "patched", "unsupported", "ambiguous"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="android-4x3-patches",
        description="Apply a target-verified 4:3 patch to a user-supplied Android APK.",
    )
    parser.add_argument("input_apk", nargs="?", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--check", action="store_true", help="inspect compatibility without writing")
    parser.add_argument("--dry-run", action="store_true", help="alias for --check")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--list-games", action="store_true")
    parser.add_argument("--game", help="narrow detection to this game id; package must still match")
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument("--force", action="store_true", help="replace an existing output")
    parser.add_argument("--allow-experimental", action="store_true")
    parser.add_argument("--unsigned", action="store_true", help="produce an aligned unsigned APK")
    parser.add_argument("--keystore", type=Path, help="custom keystore; password comes from ANDROID4X3_KEYSTORE_PASSWORD")
    return parser


def _normalize_probe(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PatchError("game module probe did not return an object")
    state = str(value.get("state", "unsupported"))
    if state not in VALID_STATES:
        raise PatchError(f"game module returned invalid state: {state}")
    result = dict(value)
    result["state"] = state
    result.setdefault("targets", [])
    return result


def _invoke_game(config: GameConfig, action: str, function, *args):
    """Turn module/import failures into stable, user-facing patch errors."""
    try:
        return function(*args)
    except PatchError:
        raise
    except Exception as exc:
        raise PatchError(f"{config.display_name}: {action} failed: {exc}") from exc


def _work_context(keep: bool):
    if not keep:
        return tempfile.TemporaryDirectory(prefix="android-4x3-")
    path = Path(tempfile.mkdtemp(prefix="android-4x3-work-", dir=Path.cwd()))
    return contextlib.nullcontext(str(path))


def _default_output(config: GameConfig) -> Path:
    return Path.cwd() / "output" / config.output_name


def _report_base(config: GameConfig, manifest, input_apk: Path, probe: dict[str, Any]) -> dict[str, Any]:
    return {
        "input": str(input_apk),
        "game": config.display_name,
        "game_id": config.id,
        "package": manifest.package,
        "version_name": manifest.version_name,
        "version_code": manifest.version_code,
        "engine": config.engine,
        "experimental": config.experimental,
        "state": probe["state"],
        "targets": probe.get("targets", []),
    }


def _human(report: dict[str, Any], *, checked: bool) -> str:
    version = report.get("version_name") or "unknown"
    if report.get("version_code") is not None:
        version += f" ({report['version_code']})"
    lines = [
        f"Game detected: {report['game']}",
        f"Package: {report['package']}",
        f"Version: {version}",
        "",
    ]
    state = report["state"]
    if state in ("original", "patched"):
        lines.append("✓ Required 4:3 patch targets found")
    if checked:
        label = "already patched" if state == "patched" else state
        lines.append(f"Compatibility: {label}")
    elif report.get("output"):
        lines.extend(
            [
                "✓ Applied 4:3 modifications" if state == "original" else "✓ 4:3 modifications already present",
                "✓ Rebuilt and verified APK",
                "✓ Signed APK" if report.get("signed") else "✓ Aligned unsigned APK",
                "",
                "Output:",
                str(report["output"]),
            ]
        )
    return "\n".join(lines)


def _list_games(registry: Registry, json_output: bool) -> int:
    games = [
        {
            "id": game.id,
            "name": game.display_name,
            "packages": list(game.package_names),
            "status": game.status,
            "engine": game.engine,
        }
        for game in sorted(registry.games, key=lambda item: item.display_name.casefold())
    ]
    if json_output:
        print(json.dumps(games, indent=2, sort_keys=True))
    else:
        for game in games:
            suffix = " (experimental)" if game["status"] == "experimental" else ""
            print(f"{game['name']}{suffix}: {', '.join(game['packages'])}")
    return 0


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo = _repo_root()
    registry = Registry(repo / "games")
    if args.list_games:
        return _list_games(registry, args.json)
    if args.input_apk is None:
        raise PatchError("an input APK is required")
    input_apk = args.input_apk.expanduser().resolve()
    if not input_apk.is_file():
        raise PatchError(f"input APK not found: {input_apk}")
    # A target-only probe can succeed even when an unrelated archive member is
    # corrupt. Verify the complete user-supplied APK before doing any work so
    # --check is an honest preflight for the eventual rebuild.
    verify_zip(input_apk, full=True, allow_signatures=True)
    manifest = inspect_apk(input_apk)
    config = registry.by_package.get(manifest.package)
    if config is None:
        raise PatchError(f"unsupported package: {manifest.package}")
    if args.game:
        forced = registry.by_id.get(args.game)
        if forced is None:
            raise PatchError(f"unknown game id: {args.game}")
        if forced.id != config.id:
            raise PatchError(
                f"--game {forced.id} does not match APK package {manifest.package}"
            )
    if config.experimental and not args.allow_experimental:
        raise PatchError(
            f"{config.display_name} support is experimental and has known rendering defects; "
            "rerun with --allow-experimental to continue"
        )

    module = _invoke_game(config, "module loading", registry.module, config)
    required = tuple(str(value) for value in module.REQUIRED_ENTRIES)
    # Known target-entry names are a performance hint, not a compatibility
    # gate. Unknown builds fall back to exhaustively scanning configured globs.
    entries = resolve_entries(input_apk, required, config.preferred_entries)
    with _work_context(args.keep_work) as work_name:
        work = Path(work_name)
        extracted = extract_entries(input_apk, entries, work / "extracted")
        probe = _normalize_probe(
            _invoke_game(config, "compatibility probe", module.probe, extracted)
        )
        if probe["state"] == "unsupported" and config.entry_globs:
            fallback_entries = resolve_entries(input_apk, required, config.entry_globs)
            additional = [entry for entry in fallback_entries if entry not in extracted]
            if additional:
                extracted.update(
                    extract_entries(input_apk, additional, work / "extracted")
                )
                probe = _normalize_probe(
                    _invoke_game(config, "compatibility probe", module.probe, extracted)
                )
        report = _report_base(config, manifest, input_apk, probe)
        if probe["state"] in ("unsupported", "ambiguous"):
            detail = probe.get("detail") or probe.get("message") or "required targets were not recognized uniquely"
            message = f"{config.display_name}: {probe['state']}: {detail}"
            report["error"] = message
            raise ReportedPatchError(message, report)

        checked = args.check or args.dry_run
        if checked:
            print(json.dumps(report, indent=2, sort_keys=True) if args.json else _human(report, checked=True))
            return 0

        output = (args.output or _default_output(config)).expanduser().resolve()
        if output == input_apk:
            raise PatchError("input and output APK paths must differ")
        if output.exists() and not args.force:
            raise PatchError(f"output exists; use --force to replace it: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)

        replacements: dict[str, Path] = {}
        if probe["state"] == "original":
            applied = _invoke_game(
                config, "patch application", module.apply, extracted, work / "patched"
            )
            if not isinstance(applied, dict):
                raise PatchError("game module apply did not return entry replacements")
            replacements = {str(entry): Path(path) for entry, path in applied.items()}
            if not replacements:
                raise PatchError("game module reported original targets but produced no replacements")

        unsigned = work / "rebuilt-unsigned.apk"
        aligned = work / "rebuilt-aligned.apk"
        signed = work / "rebuilt-signed.apk"
        repack_with_optional_branding(repo, input_apk, unsigned, replacements)
        verify_zip(unsigned)
        align_apk(unsigned, aligned)
        if args.unsigned:
            final_source = aligned
        else:
            sign_apk(aligned, signed, args.keystore)
            final_source = signed
        verify_alignment(final_source)
        verify_zip(final_source, full=True, allow_signatures=not args.unsigned)
        final_manifest = inspect_apk(final_source)
        if final_manifest != manifest:
            raise PatchError("final APK manifest identity/version changed during rebuilding")

        # Verify the core patch against the rebuilt entries before publishing.
        # Recheck the exact target entries chosen during compatibility probing;
        # do not repeat an exhaustive fallback scan after rebuilding.
        final_entries = resolve_entries(final_source, tuple(extracted), ())
        final_extracted = extract_entries(final_source, final_entries, work / "verify")
        final_probe = _normalize_probe(
            _invoke_game(config, "post-patch verification", module.probe, final_extracted)
        )
        if final_probe["state"] != "patched":
            raise PatchError(
                f"post-patch verification failed: expected patched, got {final_probe['state']}"
            )
        temporary_output = output.with_name(f".{output.name}.tmp")
        shutil.copy2(final_source, temporary_output)
        os.replace(temporary_output, output)
        report.update(
            {
                "state": probe["state"],
                "post_state": "patched",
                "output": str(output),
                "signed": not args.unsigned,
            }
        )
        print(json.dumps(report, indent=2, sort_keys=True) if args.json else _human(report, checked=False))
        if args.keep_work:
            print(f"Work directory: {work}", file=sys.stderr)
        return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except (PatchError, OSError, ValueError) as exc:
        if "--json" in sys.argv[1:]:
            report = dict(getattr(exc, "report", {}))
            report.setdefault("status", "error")
            report.setdefault("error", str(exc))
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
