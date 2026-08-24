from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import pytest

from android4x3 import apk as apk_module
from android4x3.apk import repack_with_optional_branding, verify_zip
from android4x3.errors import PatchError


REPO_ROOT = Path(__file__).resolve().parents[1]
LIBRARY = "lib/arm64-v8a/libsynthetic.so"
SIGNATURES = {
    "META-INF/MANIFEST.MF",
    "META-INF/TEST.SF",
    "META-INF/TEST.RSA",
}


def _local_data_offset(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> int:
    assert archive.fp is not None
    archive.fp.seek(info.header_offset)
    header = archive.fp.read(30)
    signature, *_middle, name_size, extra_size = struct.unpack("<IHHHHHIIIHH", header)
    assert signature == 0x04034B50
    return info.header_offset + 30 + name_size + extra_size


def _info(
    name: str,
    compression: int,
    *,
    extra: bytes = b"",
) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2024, 5, 6, 7, 8, 10))
    info.compress_type = compression
    info.create_system = 3
    info.external_attr = 0o100640 << 16
    info.comment = b"entry metadata"
    info.extra = extra
    return info


def _write_reference_apk(path: Path, manifest: bytes, unsafe_branding: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # The first stored library begins at a 4096-byte boundary. The repacker
    # should retain at least that alignment while preserving this unknown field.
    custom_id = 0xCAFE
    payload_size = (-(30 + len(LIBRARY.encode("ascii")) + 4)) % 4096
    library_extra = struct.pack("<HH", custom_id, payload_size) + b"\0" * payload_size
    small_extra = struct.pack("<HH4s", custom_id, 4, b"test")
    with zipfile.ZipFile(path, "w") as archive:
        archive.comment = b"synthetic archive comment"
        archive.writestr(_info(LIBRARY, zipfile.ZIP_STORED, extra=library_extra), b"ORIGINAL")
        archive.writestr(
            _info("AndroidManifest.xml", zipfile.ZIP_DEFLATED, extra=small_extra),
            manifest,
        )
        archive.writestr(_info("assets/data.bin", zipfile.ZIP_DEFLATED), b"unchanged")
        if unsafe_branding:
            archive.writestr(
                _info("assets/AVConfig.json", zipfile.ZIP_DEFLATED),
                b"unrecognized user-owned payload",
            )
        for name in sorted(SIGNATURES):
            archive.writestr(_info(name, zipfile.ZIP_DEFLATED), b"stale signature")
        archive.writestr(
            _info("META-INF/NOTICE.TXT", zipfile.ZIP_DEFLATED),
            b"not a signature",
        )


@pytest.mark.parametrize("unsafe_branding", [False, True])
def test_repack_is_structure_preserving_and_optional_branding_is_silent(
    tmp_path: Path,
    text_manifest,
    capsys,
    unsafe_branding: bool,
) -> None:
    input_apk = tmp_path / "source APKs with spaces" / "Synthetic Game.apk"
    output_apk = tmp_path / "patched APKs with spaces" / "Synthetic Game-4x3.apk"
    replacement = tmp_path / "replacement files" / "lib synthetic replacement.so"
    replacement.parent.mkdir(parents=True)
    replacement.write_bytes(b"PATCHED-LIBRARY")
    _write_reference_apk(input_apk, text_manifest(), unsafe_branding)

    with zipfile.ZipFile(input_apk) as source:
        source_infos = {info.filename: info for info in source.infolist()}
        source_order = [info.filename for info in source.infolist()]
        assert _local_data_offset(source, source_infos[LIBRARY]) % 4096 == 0

    repack_with_optional_branding(
        REPO_ROOT,
        input_apk,
        output_apk,
        {LIBRARY: replacement},
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    verify_zip(output_apk, full=True)

    with zipfile.ZipFile(output_apk) as output:
        output_infos = {info.filename: info for info in output.infolist()}
        expected_order = [name for name in source_order if name not in SIGNATURES]
        assert output.namelist() == expected_order
        assert output.comment == b"synthetic archive comment"
        assert output.read(LIBRARY) == b"PATCHED-LIBRARY"
        assert output.read("assets/data.bin") == b"unchanged"
        assert output.read("META-INF/NOTICE.TXT") == b"not a signature"
        assert not SIGNATURES.intersection(output.namelist())
        assert _local_data_offset(output, output_infos[LIBRARY]) % 4096 == 0

        for name in expected_order:
            before = source_infos[name]
            after = output_infos[name]
            assert after.compress_type == before.compress_type
            assert after.date_time == before.date_time
            assert after.external_attr == before.external_attr
            assert after.comment == before.comment

        assert struct.pack("<H", 0xCAFE) in output_infos[LIBRARY].extra
        assert output_infos["AndroidManifest.xml"].extra.startswith(
            struct.pack("<HH4s", 0xCAFE, 4, b"test")
        )
        if unsafe_branding:
            assert output.read("assets/AVConfig.json") == b"unrecognized user-owned payload"


def test_repack_with_no_core_replacements_still_removes_stale_signatures(
    tmp_path: Path, text_manifest, capsys
) -> None:
    input_apk = tmp_path / "already patched.apk"
    output_apk = tmp_path / "rebuilt.apk"
    _write_reference_apk(input_apk, text_manifest(), unsafe_branding=False)

    repack_with_optional_branding(REPO_ROOT, input_apk, output_apk, {})

    assert capsys.readouterr() == ("", "")
    with zipfile.ZipFile(output_apk) as output:
        assert output.read(LIBRARY) == b"ORIGINAL"
        assert not SIGNATURES.intersection(output.namelist())


def test_branding_write_failure_falls_back_silently_to_core_repack(
    tmp_path: Path, text_manifest, monkeypatch, capsys
) -> None:
    input_apk = tmp_path / "source.apk"
    output_apk = tmp_path / "output.apk"
    replacement = tmp_path / "replacement.so"
    replacement.write_bytes(b"PATCHED")
    _write_reference_apk(input_apk, text_manifest(), unsafe_branding=True)
    backend = apk_module._branding_backend(REPO_ROOT)
    real_write = backend._write_apk
    calls = 0

    def fail_branding_plan_once(plan, *, force: bool, full_verify: bool) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic optional-branding write failure")
        real_write(plan, force=force, full_verify=full_verify)

    monkeypatch.setattr(backend, "_write_apk", fail_branding_plan_once)
    monkeypatch.setattr(apk_module, "_branding_backend", lambda _repo: backend)

    repack_with_optional_branding(REPO_ROOT, input_apk, output_apk, {LIBRARY: replacement})

    assert calls == 2
    assert capsys.readouterr() == ("", "")
    with zipfile.ZipFile(output_apk) as output:
        assert output.read(LIBRARY) == b"PATCHED"
        assert output.read("assets/AVConfig.json") == b"unrecognized user-owned payload"


def test_branding_backend_load_failure_falls_back_silently_to_core_repack(
    tmp_path: Path, text_manifest, monkeypatch, capsys
) -> None:
    input_apk = tmp_path / "source.apk"
    output_apk = tmp_path / "output.apk"
    replacement = tmp_path / "replacement.so"
    replacement.write_bytes(b"PATCHED")
    _write_reference_apk(input_apk, text_manifest(), unsafe_branding=True)

    def fail_to_load(_repo: Path):
        raise ImportError("synthetic optional-branding backend failure")

    monkeypatch.setattr(apk_module, "_branding_backend", fail_to_load)

    repack_with_optional_branding(REPO_ROOT, input_apk, output_apk, {LIBRARY: replacement})

    assert capsys.readouterr() == ("", "")
    verify_zip(output_apk, full=True)
    with zipfile.ZipFile(output_apk) as output:
        assert output.read(LIBRARY) == b"PATCHED"
        assert output.read("assets/AVConfig.json") == b"unrecognized user-owned payload"
        assert not SIGNATURES.intersection(output.namelist())


def test_core_target_remains_strict_when_branding_backend_cannot_load(
    tmp_path: Path, text_manifest, monkeypatch, capsys
) -> None:
    input_apk = tmp_path / "source.apk"
    output_apk = tmp_path / "output.apk"
    replacement = tmp_path / "replacement.so"
    replacement.write_bytes(b"PATCHED")
    _write_reference_apk(input_apk, text_manifest(), unsafe_branding=False)

    monkeypatch.setattr(
        apk_module,
        "_branding_backend",
        lambda _repo: (_ for _ in ()).throw(ImportError("synthetic failure")),
    )

    with pytest.raises(PatchError, match="replacement target disappeared"):
        repack_with_optional_branding(
            REPO_ROOT,
            input_apk,
            output_apk,
            {"lib/arm64-v8a/missing.so": replacement},
        )

    assert capsys.readouterr() == ("", "")
    assert not output_apk.exists()
