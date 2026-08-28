"""Proprietary-free coverage for Dusklight's nested 4:3 recipe."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from android4x3.apk import _branding_backend
from android4x3.registry import Registry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _module():
    registry = Registry(REPO_ROOT / "games")
    return registry.module(registry.by_id["dusklight"])


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_dusklight_nested_probe_apply_and_launch_runtime_guards(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    manifest = b"synthetic guarded Dusklight manifest"
    classes = b"synthetic nativeized launcher"
    launch = b"synthetic launch and extraction runtime"
    overlay_source = b"synthetic branding initializer"
    monkeypatch.setattr(module, "MANIFEST_SHA256", _digest(manifest))
    monkeypatch.setattr(module, "CLASSES_SHA256", _digest(classes))
    monkeypatch.setattr(module, "LAUNCH_RUNTIME_SHA256", _digest(launch))
    monkeypatch.setattr(module, "SOURCE_OVERLAY_SHA256", _digest(overlay_source))

    extracted: dict[str, Path] = {}
    values = {
        module.MANIFEST_ENTRY: manifest,
        module.CLASSES_ENTRY: classes,
        module.LAUNCH_RUNTIME_ENTRY: launch,
        module.OVERLAY_RUNTIME_ENTRY: overlay_source,
    }
    for entry, data in values.items():
        path = tmp_path / "source" / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        extracted[entry] = path
    data1 = tmp_path / "source" / module.DATA1_ENTRY
    data1.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(data1, "w") as archive:
        archive.writestr("files/", b"", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            module.SOURCE_ISO_ENTRY, b"D" * 128, compress_type=zipfile.ZIP_STORED
        )
        archive.writestr(
            module.CONFIG_ENTRY,
            module.json.dumps(module.SOURCE_CONFIG, indent=4).encode(),
        )
    extracted[module.DATA1_ENTRY] = data1

    assert module.probe(extracted)["state"] == "original"
    replacements = module.apply(extracted, tmp_path / "patched")
    extracted[module.DATA1_ENTRY] = replacements[module.DATA1_ENTRY]
    result = module.probe(extracted)
    assert result["state"] == "patched"
    assert extracted[module.LAUNCH_RUNTIME_ENTRY].read_bytes() == launch
    with zipfile.ZipFile(extracted[module.DATA1_ENTRY]) as archive:
        assert module.SOURCE_ISO_ENTRY not in archive.namelist()
        assert archive.getinfo(module.PATCHED_ISO_ENTRY).file_size == 128
        config = module.json.loads(archive.read(module.CONFIG_ENTRY))
        for name, wanted in module.FOUR_THREE_CONFIG.items():
            assert config[name] == wanted


def test_dusklight_optional_artifacts_do_not_block_apply(tmp_path: Path, monkeypatch) -> None:
    module = _module()
    manifest = b"manifest"
    classes = b"classes"
    launch_runtime = b"lowercase-runtime"
    overlay_runtime = b"overlay-runtime"
    monkeypatch.setattr(module, "MANIFEST_SHA256", _digest(manifest))
    monkeypatch.setattr(module, "CLASSES_SHA256", _digest(classes))
    monkeypatch.setattr(
        module, "LAUNCH_RUNTIME_SHA256", _digest(launch_runtime)
    )
    monkeypatch.setattr(
        module, "SOURCE_OVERLAY_SHA256", _digest(overlay_runtime + b"-changed")
    )

    extracted: dict[str, Path] = {}
    for entry, data in {
        module.MANIFEST_ENTRY: manifest,
        module.CLASSES_ENTRY: classes,
        module.LAUNCH_RUNTIME_ENTRY: launch_runtime,
        module.OVERLAY_RUNTIME_ENTRY: overlay_runtime,
    }.items():
        path = tmp_path / "source" / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        extracted[entry] = path
    data1 = tmp_path / "source" / module.DATA1_ENTRY
    data1.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(data1, "w") as archive:
        archive.writestr("files/", b"", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            module.SOURCE_ISO_ENTRY, b"D" * 128, compress_type=zipfile.ZIP_STORED
        )
        archive.writestr(
            module.CONFIG_ENTRY,
            module.json.dumps(module.SOURCE_CONFIG, indent=4).encode(),
        )
    extracted[module.DATA1_ENTRY] = data1

    result = module.probe(extracted)
    assert result["state"] == "original"
    replacements = module.apply(extracted, tmp_path / "patched")
    extracted[module.DATA1_ENTRY] = replacements[module.DATA1_ENTRY]
    assert module.probe(extracted)["state"] == "patched"


def test_shared_branding_repack_preserves_exact_dusklight_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    backend = _branding_backend(REPO_ROOT)
    source = tmp_path / "source.apk"
    output = tmp_path / "output.apk"
    classes = b"synthetic classes2"
    launch = b"synthetic required lowercase runtime"
    overlay = b"synthetic independent uppercase runtime"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("classes2.dex", classes)
        archive.writestr("lib/arm64-v8a/libapkvisionorg.so", launch)
        archive.writestr("lib/arm64-v8a/libAPKVISION.so", overlay)
        archive.writestr("META-INF/CERT.SF", b"stale")

    monkeypatch.setattr(backend, "DUSKLIGHT_V141_CLASSES2_SHA256", _digest(classes))
    monkeypatch.setattr(
        backend, "DUSKLIGHT_V141_LAUNCH_RUNTIME_SHA256", _digest(launch)
    )
    monkeypatch.setattr(
        backend, "DUSKLIGHT_V141_OVERLAY_RUNTIME_SHA256", _digest(overlay)
    )

    def fake_patch(entry_name, data, strong_marker):
        assert Path(entry_name).name not in {"libapkvisionorg.so", "libAPKVISION.so"}
        assert strong_marker
        return data + b"-neutralized", [], 1, 1

    monkeypatch.setattr(backend, "patch_native_entry", fake_patch)
    plan = backend.neutralize_apk(source, output, full_verify=True)
    assert any(change.kind == "preserve-launch-runtime" for change in plan.changes)
    assert plan.runtime_targets == 0
    assert plan.runtime_patches == 0
    assert plan.modified_entries == {}
    with zipfile.ZipFile(output) as archive:
        assert archive.read("lib/arm64-v8a/libapkvisionorg.so") == launch
        assert archive.read("lib/arm64-v8a/libAPKVISION.so") == overlay
    preserved = [change for change in plan.changes if change.kind == "preserve-launch-runtime"]
    assert {Path(change.entry).name for change in preserved} == {
        "libapkvisionorg.so",
        "libAPKVISION.so",
    }


def test_dusklight_missing_optional_artifacts_do_not_block_apply(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    manifest = b"manifest"
    classes = b"classes"
    monkeypatch.setattr(module, "MANIFEST_SHA256", _digest(manifest))
    monkeypatch.setattr(module, "CLASSES_SHA256", _digest(classes))

    extracted: dict[str, Path] = {}
    for entry, data in {
        module.MANIFEST_ENTRY: manifest,
        module.CLASSES_ENTRY: classes,
    }.items():
        path = tmp_path / "source" / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        extracted[entry] = path
    data1 = tmp_path / "source" / module.DATA1_ENTRY
    data1.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(data1, "w") as archive:
        archive.writestr("files/", b"", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            module.SOURCE_ISO_ENTRY, b"D" * 128, compress_type=zipfile.ZIP_STORED
        )
        archive.writestr(
            module.CONFIG_ENTRY,
            module.json.dumps(module.SOURCE_CONFIG, indent=4).encode(),
        )
    extracted[module.DATA1_ENTRY] = data1

    result = module.probe(extracted)
    assert result["state"] == "original"
    replacements = module.apply(extracted, tmp_path / "patched")
    extracted[module.DATA1_ENTRY] = replacements[module.DATA1_ENTRY]
    assert module.probe(extracted)["state"] == "patched"


def _dusklight_optional_report_bases(
    module, tmp_path: Path, manifest: bytes, classes: bytes
):
    data1 = tmp_path / "source" / module.DATA1_ENTRY
    data1.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(data1, "w") as archive:
        archive.writestr("files/", b"", compress_type=zipfile.ZIP_STORED)
        archive.writestr(module.SOURCE_ISO_ENTRY, b"D" * 128, compress_type=zipfile.ZIP_STORED)
        archive.writestr(module.CONFIG_ENTRY, module.json.dumps(module.SOURCE_CONFIG, indent=4).encode())
    extracted: dict[str, Path] = {
        module.MANIFEST_ENTRY: tmp_path / "source" / module.MANIFEST_ENTRY,
        module.CLASSES_ENTRY: tmp_path / "source" / module.CLASSES_ENTRY,
        module.DATA1_ENTRY: data1,
    }
    extracted[module.MANIFEST_ENTRY].parent.mkdir(parents=True, exist_ok=True)
    extracted[module.CLASSES_ENTRY].parent.mkdir(parents=True, exist_ok=True)
    extracted[module.MANIFEST_ENTRY].write_bytes(manifest)
    extracted[module.CLASSES_ENTRY].write_bytes(classes)
    return extracted


def test_dusklight_optional_artifacts_do_not_change_probe_report(tmp_path: Path, monkeypatch) -> None:
    module = _module()
    manifest = b"manifest"
    classes = b"classes"
    known_launch = b"lowercase-runtime"
    known_overlay = b"overlay-runtime"
    unknown_launch = b"other-lowercase-runtime"
    unknown_overlay = b"other-overlay"

    monkeypatch.setattr(module, "MANIFEST_SHA256", _digest(manifest))
    monkeypatch.setattr(module, "CLASSES_SHA256", _digest(classes))
    monkeypatch.setattr(module, "LAUNCH_RUNTIME_SHA256", _digest(known_launch))
    monkeypatch.setattr(module, "SOURCE_OVERLAY_SHA256", _digest(known_overlay))

    base = _dusklight_optional_report_bases(module, tmp_path / "a", manifest, classes)

    present = {
        module.LAUNCH_RUNTIME_ENTRY: tmp_path / "a" / module.LAUNCH_RUNTIME_ENTRY,
        module.OVERLAY_RUNTIME_ENTRY: tmp_path / "a" / module.OVERLAY_RUNTIME_ENTRY,
    }
    for entry, value in {
        module.LAUNCH_RUNTIME_ENTRY: known_launch,
        module.OVERLAY_RUNTIME_ENTRY: known_overlay,
    }.items():
        present[entry].parent.mkdir(parents=True, exist_ok=True)
        present[entry].write_bytes(value)
        base[entry] = present[entry]

    missing = dict(base)
    missing.pop(module.LAUNCH_RUNTIME_ENTRY, None)
    missing.pop(module.OVERLAY_RUNTIME_ENTRY, None)

    unknown = dict(base)
    unknown[module.LAUNCH_RUNTIME_ENTRY] = (
        tmp_path / "a" / f"mystery-{module.LAUNCH_RUNTIME_ENTRY.replace('/', '_')}"
    )
    unknown[module.OVERLAY_RUNTIME_ENTRY] = (
        tmp_path / "a" / f"mystery-{module.OVERLAY_RUNTIME_ENTRY.replace('/', '_')}"
    )
    for entry, value in {
        module.LAUNCH_RUNTIME_ENTRY: unknown_launch,
        module.OVERLAY_RUNTIME_ENTRY: unknown_overlay,
    }.items():
        unknown_path = unknown[entry]
        unknown_path.parent.mkdir(parents=True, exist_ok=True)
        unknown_path.write_bytes(value)
        unknown[entry] = unknown_path
    present_report = module.probe(base)
    missing_report = module.probe(missing)
    unknown_report = module.probe(unknown)
    assert present_report == missing_report == unknown_report
    assert present_report["state"] == "original"
    assert {entry["name"] for entry in present_report["targets"]} == {
        "Aurora viewport fit",
        "GameCube menu scaling",
        "cutscene pillarboxing",
    }


def test_dusklight_rejects_incompatible_required_config_type(
    tmp_path: Path, monkeypatch
) -> None:
    module = _module()
    manifest = b"manifest"
    classes = b"classes"
    lowercase = b"lowercase"
    monkeypatch.setattr(module, "MANIFEST_SHA256", _digest(manifest))
    monkeypatch.setattr(module, "CLASSES_SHA256", _digest(classes))
    monkeypatch.setattr(module, "LAUNCH_RUNTIME_SHA256", _digest(lowercase))
    monkeypatch.setattr(module, "SOURCE_OVERLAY_SHA256", _digest(b"overlay"))
    extracted: dict[str, Path] = {}
    for entry, data in {
        module.MANIFEST_ENTRY: manifest,
        module.CLASSES_ENTRY: classes,
        module.LAUNCH_RUNTIME_ENTRY: lowercase,
    }.items():
        path = tmp_path / "source" / entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        extracted[entry] = path
    data1 = tmp_path / "source" / "data1.apk"
    data1.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(data1, "w") as archive:
        archive.writestr("files/", b"", compress_type=zipfile.ZIP_STORED)
        archive.writestr("files/other.bin", b"X", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            module.CONFIG_ENTRY,
            b'{"unrelated": true, "video.lockAspectRatio": "yes"}',
        )
    extracted[module.DATA1_ENTRY] = data1
    result = module.probe(extracted)
    assert result["state"] == "unsupported"
    assert "video.lockAspectRatio" in result["detail"]


def test_dusklight_cleanup_only_config_and_unrelated_values_are_compatible(
    tmp_path: Path, monkeypatch
) -> None:
    """Model the archived clean APK without including its disc or other assets."""

    module = _module()
    clean_path = module.PATCHED_ISO_PATH
    unrelated = (
        b'\xef\xbb\xbf{\r\n'
        b'\t"backend.isoPath" : "'
        + clean_path.encode("utf-8")
        + b'",\r\n'
        b'\t"backend.isoVerification": 1,\r\n'
        b'\t"extra.nested" : { "array": [1, 2, {"label":"moon"}] },\r\n'
        b'\t"game.enableTouchControls": true\r\n'
        b'}'
    )
    data1 = tmp_path / "clean-data1"
    with zipfile.ZipFile(data1, "w") as archive:
        archive.writestr("files/", b"", compress_type=zipfile.ZIP_STORED)
        archive.writestr(
            module.PATCHED_ISO_ENTRY, b"D" * 128, compress_type=zipfile.ZIP_STORED
        )
        archive.writestr("files/unrelated.bin", b"keep-me")
        archive.writestr(module.CONFIG_ENTRY, unrelated)

    extracted = {module.DATA1_ENTRY: data1}
    assert module.probe(extracted)["state"] == "original"
    replacements = module.apply(extracted, tmp_path / "patched")
    patched_data1 = replacements[module.DATA1_ENTRY]
    assert module._data1_state(patched_data1) == ("patched", None)
    with zipfile.ZipFile(patched_data1) as archive:
        assert archive.read("files/unrelated.bin") == b"keep-me"
        assert module.SOURCE_ISO_ENTRY not in archive.namelist()
        assert module.PATCHED_ISO_ENTRY in archive.namelist()
        config = archive.read(module.CONFIG_ENTRY)
    assert config.startswith(b"\xef\xbb\xbf")
    assert b'\t"extra.nested" : { "array": [1, 2, {"label":"moon"}] },\r\n' in config
    decoded = module.json.loads(config.decode("utf-8-sig"))
    assert decoded["backend.isoPath"] == clean_path
    assert decoded["extra.nested"] == {"array": [1, 2, {"label": "moon"}]}
    for name, wanted in module.FOUR_THREE_CONFIG.items():
        assert decoded[name] == wanted


def test_dusklight_branded_or_unknown_iso_cleanup_is_non_gating(tmp_path: Path) -> None:
    module = _module()
    cases = (
        (
            "branded",
            module.SOURCE_ISO_ENTRY,
            module.SOURCE_CONFIG["backend.isoPath"],
            module.PATCHED_ISO_ENTRY,
            module.PATCHED_ISO_PATH,
        ),
        (
            "unknown",
            "files/user-supplied-disc.iso",
            "/data/user/0/dev.twilitrealm.dusk/files/user-supplied-disc.iso",
            "files/user-supplied-disc.iso",
            "/data/user/0/dev.twilitrealm.dusk/files/user-supplied-disc.iso",
        ),
    )
    for label, source_name, source_path, wanted_name, wanted_path in cases:
        data1 = tmp_path / f"{label}-data1"
        config = module.json.dumps(
            {"backend.isoPath": source_path, "unrelated": {"preserve": True}},
            indent=2,
        ).encode()
        with zipfile.ZipFile(data1, "w") as archive:
            archive.writestr(source_name, b"disc", compress_type=zipfile.ZIP_STORED)
            archive.writestr(module.CONFIG_ENTRY, config)
        assert module._data1_state(data1) == ("original", None)
        output = tmp_path / f"{label}-patched"
        module._build_data1(data1, output)
        with zipfile.ZipFile(output) as archive:
            assert wanted_name in archive.namelist()
            patched = module.json.loads(archive.read(module.CONFIG_ENTRY))
        assert patched["backend.isoPath"] == wanted_path
        assert patched["unrelated"] == {"preserve": True}


def test_dusklight_partial_and_explicit_original_values_patch_in_place() -> None:
    module = _module()
    source = (
        b'{"video.lockAspectRatio" : false, "keep" : [1, {"x": 2}], '
        b'"game.menuScalingMode": 2}'
    )
    assert module._config_analysis(source)[0] == "original"
    patched = module._patch_config(source)
    assert b'"keep" : [1, {"x": 2}]' in patched
    assert module._config_analysis(patched)[0] == "patched"


def test_dusklight_duplicate_required_key_is_ambiguous() -> None:
    module = _module()
    source = b'{"video.lockAspectRatio": false, "video.lockAspectRatio": true}'
    state, detail, _decoded = module._config_analysis(source)
    assert state == "ambiguous"
    assert "duplicate required config keys" in detail


def test_dusklight_registry_entry_is_visual_pending() -> None:
    config = Registry(REPO_ROOT / "games").by_id["dusklight"]
    assert config.package_names == ("dev.twilitrealm.dusk",)
    assert config.experimental
    assert config.output_name == "Dusklight-v1.4.1-4x3.apk"
