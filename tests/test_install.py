"""Adopted installation must never silently fall back to internal storage."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from android4x3 import install, cli
from android4x3.errors import PatchError

UUID = "01234567-89ab-cdef-0123-456789abcdef"
PKG = "example.game"


def _setup(monkeypatch, *, devices="serial\tdevice\n", primary=UUID, install_result="Success", data_external=True):
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        if args[-1] == "devices":
            out = "List of devices attached\n" + devices
        elif args[-3:] == ["sm", "list-volumes", "private"]:
            out = f"private mounted null\nprivate:179,2 mounted {UUID}\n"
        elif args[-2:] == ["sm", "get-primary-storage-uuid"]:
            out = primary
        elif "install" in args:
            out = install_result
        elif args[-3:] == ["dumpsys", "package", PKG]:
            root = f"/mnt/expand/{UUID}"
            data = root if data_external else "/data"
            out = f"Packages:\n  Package [{PKG}] (abc):\n    codePath={root}/app/game\n    dataDir={data}/user/0/{PKG}\n    volumeUuid={UUID}\n\nQueries:\n"
        else:
            raise AssertionError(args)
        return SimpleNamespace(returncode=0, stdout=out, stderr="")
    monkeypatch.setattr(install, "_adb", lambda: "adb")
    monkeypatch.setattr(install.subprocess, "run", run)
    return calls


def test_adopted_install_streams_to_selected_device_and_verifies_all_locations(monkeypatch):
    calls = _setup(monkeypatch)
    device = install.prepare_adopted()
    result = install.install_adopted(device, Path("Game with spaces.apk"), PKG)
    assert result["shared_storage"] == "adopted"
    assert result["data_path"].startswith(f"/mnt/expand/{UUID}/")
    assert ["adb", "-s", "serial", "install", "--no-incremental", "--streaming", "-r",
            "--force-uuid", UUID, "Game with spaces.apk"] in calls
    assert not any("uninstall" in c or "clear" in c or "partition" in c for c in calls)


@pytest.mark.parametrize("devices", ["", "serial\tunauthorized\n", "serial\toffline\n", "one\tdevice\ntwo\tdevice\n"])
def test_missing_unauthorized_and_ambiguous_device_refused(monkeypatch, devices):
    calls = _setup(monkeypatch, devices=devices)
    with pytest.raises(PatchError, match="authorize exactly one"):
        install.prepare_adopted()
    assert len(calls) == 1


def test_explicit_device_selects_exactly_one(monkeypatch):
    _setup(monkeypatch, devices="one\tdevice\ntwo\tdevice\n")
    assert install.prepare_adopted("two").serial == "two"


def test_internal_primary_storage_refused_before_install(monkeypatch):
    calls = _setup(monkeypatch, primary="null")
    with pytest.raises(PatchError, match="migrate data"):
        install.prepare_adopted()
    assert not any("install" in c for c in calls)


def test_private_data_on_internal_storage_fails_verification(monkeypatch):
    _setup(monkeypatch, data_external=False)
    with pytest.raises(PatchError, match="both the APK and private"):
        install.install_adopted(install.prepare_adopted(), Path("game.apk"), PKG)


def test_signature_conflict_never_uninstalls_or_clears_data(monkeypatch):
    calls = _setup(monkeypatch, install_result="Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]")
    with pytest.raises(PatchError, match="never uninstalls"):
        install.install_adopted(install.prepare_adopted(), Path("saved-output.apk"), PKG)
    assert not any("uninstall" in c or "clear" in c for c in calls)


@pytest.mark.parametrize("flag", ["--unsigned", "--check", "--dry-run", "--list-games"])
def test_install_flags_reject_noninstalling_modes(flag):
    with pytest.raises(PatchError, match="requires a signed build"):
        cli.run(["--install-adopted", flag])


def test_device_selection_requires_opt_in():
    with pytest.raises(PatchError, match="requires --install-adopted"):
        cli.run(["--device", "serial"])
