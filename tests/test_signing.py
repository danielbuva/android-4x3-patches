from __future__ import annotations

from pathlib import Path
import shutil
import zipfile

import pytest

from android4x3 import signing
from android4x3.apk import verify_zip
from android4x3.errors import PatchError


def test_find_android_tool_prefers_path(tmp_path: Path, monkeypatch) -> None:
    direct = tmp_path / "SDK tools with spaces" / "zipalign"
    direct.parent.mkdir(parents=True)
    direct.write_bytes(b"")
    monkeypatch.setattr(
        signing.shutil,
        "which",
        lambda name: str(direct) if name == "zipalign" else None,
    )

    assert signing.find_android_tool("zipalign") == direct


def test_find_android_tool_uses_newest_sdk_build_tools(
    tmp_path: Path, monkeypatch
) -> None:
    sdk = tmp_path / "Android SDK"
    old = sdk / "build-tools" / "34.0.0" / "apksigner"
    newest = sdk / "build-tools" / "35.0.1" / "apksigner"
    old.parent.mkdir(parents=True)
    newest.parent.mkdir(parents=True)
    old.write_bytes(b"")
    newest.write_bytes(b"")
    monkeypatch.setattr(signing.shutil, "which", lambda _name: None)
    monkeypatch.setattr(signing, "_sdk_roots", lambda: [sdk])

    assert signing.find_android_tool("apksigner") == newest


def test_windows_sdk_uses_zipalign_exe_and_apksigner_bat(
    tmp_path: Path, monkeypatch
) -> None:
    sdk = tmp_path / "Android SDK"
    zipalign = sdk / "build-tools" / "36.0.0" / "zipalign.exe"
    apksigner = sdk / "build-tools" / "36.0.0" / "apksigner.bat"
    zipalign.parent.mkdir(parents=True)
    zipalign.write_bytes(b"")
    apksigner.write_bytes(b"")
    monkeypatch.setattr(signing.shutil, "which", lambda _name: None)
    monkeypatch.setattr(signing, "_sdk_roots", lambda: [sdk])

    assert signing.find_android_tool("zipalign", platform="nt") == zipalign
    assert signing.find_android_tool("apksigner", platform="nt") == apksigner


def test_find_android_tool_failure_is_actionable(monkeypatch) -> None:
    monkeypatch.setattr(signing.shutil, "which", lambda _name: None)
    monkeypatch.setattr(signing, "_sdk_roots", lambda: [])

    with pytest.raises(PatchError, match="Android SDK tool 'zipalign' was not found"):
        signing.find_android_tool("zipalign")


def test_signing_failure_does_not_create_a_false_success(
    tmp_path: Path, monkeypatch
) -> None:
    apksigner = tmp_path / "Android SDK" / "apksigner"
    keystore = tmp_path / "user signing" / "signing.p12"
    password_file = tmp_path / "user signing" / "signing-password.txt"
    aligned = tmp_path / "build with spaces" / "aligned.apk"
    signed = tmp_path / "build with spaces" / "signed.apk"
    calls: list[list[str]] = []

    monkeypatch.setattr(signing, "find_android_tool", lambda name: apksigner)
    monkeypatch.setattr(
        signing,
        "ensure_keystore",
        lambda custom=None: (keystore, "android4x3", password_file, password_file),
    )

    def fail_sign(command: list[str], *, env=None) -> str:
        calls.append(command)
        raise PatchError("mocked apksigner failure")

    monkeypatch.setattr(signing, "_run", fail_sign)

    with pytest.raises(PatchError, match="mocked apksigner failure"):
        signing.sign_apk(aligned, signed)

    assert len(calls) == 1
    assert calls[0][0] == str(apksigner)
    assert str(aligned) in calls[0]
    assert str(signed) in calls[0]
    assert not signed.exists()


def test_custom_keystore_passwords_are_temporary_and_do_not_replace_defaults(
    tmp_path: Path, monkeypatch
) -> None:
    custom = tmp_path / "custom key with spaces.p12"
    custom.write_bytes(b"synthetic keystore placeholder")
    default_state = tmp_path / "default identity"
    default_state.mkdir()
    default_store = default_state / "signing-password.txt"
    default_key = default_state / "signing-key-password.txt"
    default_store.write_text("default-store\n", encoding="utf-8")
    default_key.write_text("default-key\n", encoding="utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setenv("ANDROID4X3_KEYSTORE_PASSWORD", "custom-store")
    monkeypatch.setenv("ANDROID4X3_KEY_PASSWORD", "custom-key")
    monkeypatch.setattr(signing, "find_android_tool", lambda _name: tmp_path / "apksigner")
    monkeypatch.setattr(signing, "_run", lambda *_args, **_kwargs: "")

    def capture_credentials(
        _tool, _aligned, _signed, keystore, alias, store_file, key_file
    ) -> None:
        captured.update(
            {
                "keystore": keystore,
                "alias": alias,
                "store": store_file.read_text(encoding="utf-8"),
                "key": key_file.read_text(encoding="utf-8"),
                "directory": store_file.parent,
            }
        )

    monkeypatch.setattr(signing, "_sign_with_files", capture_credentials)

    signing.sign_apk(tmp_path / "aligned.apk", tmp_path / "signed.apk", custom)

    assert captured["keystore"] == custom.resolve()
    assert captured["store"] == "custom-store\n"
    assert captured["key"] == "custom-key\n"
    assert not Path(captured["directory"]).exists()
    assert default_store.read_text(encoding="utf-8") == "default-store\n"
    assert default_key.read_text(encoding="utf-8") == "default-key\n"


def test_generated_identity_signs_and_verifies_synthetic_apk(
    tmp_path: Path, monkeypatch, make_apk, binary_manifest
) -> None:
    if shutil.which("keytool") is None:
        pytest.skip("keytool is not installed")
    try:
        signing.find_android_tool("zipalign")
        signing.find_android_tool("apksigner")
    except PatchError:
        pytest.skip("Android SDK Build Tools are not installed")

    unsigned = make_apk(
        tmp_path / "unsigned.apk",
        manifest=binary_manifest("org.example.signed", "1.0", 1),
        entries=[
            ("assets/data.bin", b"synthetic", zipfile.ZIP_STORED),
            (
                "lib/arm64-v8a/libsynthetic.so",
                b"synthetic native library payload",
                zipfile.ZIP_STORED,
            ),
        ],
    )
    aligned = tmp_path / "aligned.apk"
    signed = tmp_path / "signed.apk"
    monkeypatch.setattr(signing, "_state_dir", lambda: tmp_path / "user signing state")

    signing.align_apk(unsigned, aligned)
    signing.sign_apk(aligned, signed)
    signing.verify_alignment(signed)

    verify_zip(signed, full=True, allow_signatures=True)
    assert signed.is_file()
    assert (tmp_path / "user signing state" / "signing.p12").is_file()


def test_sign_command_preserves_zipalign_layout(tmp_path: Path, monkeypatch) -> None:
    captured: list[list[str]] = []
    apksigner = tmp_path / "apksigner"
    credentials = tmp_path / "credentials"
    credentials.mkdir()
    password_file = credentials / "password.txt"
    password_file.write_text("secret\n", encoding="utf-8")

    monkeypatch.setattr(signing, "_run", lambda command, **_kwargs: captured.append(command) or "")

    signing._sign_with_files(
        apksigner,
        tmp_path / "aligned.apk",
        tmp_path / "signed.apk",
        tmp_path / "signing.p12",
        "android4x3",
        password_file,
        password_file,
    )

    assert "--alignment-preserved" in captured[0]
    option = captured[0].index("--alignment-preserved")
    assert captured[0][option + 1] == "true"
