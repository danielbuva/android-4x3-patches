"""Opt-in installation on existing adopted Android storage, without formatting."""
from __future__ import annotations

import dataclasses
import re
import shutil
import subprocess
from pathlib import Path

from .errors import PatchError
from .signing import _sdk_roots


@dataclasses.dataclass(frozen=True)
class AdoptedDevice:
    adb: str
    serial: str
    volume: str

    def command(self, *args: str, timeout: int = 120) -> str:
        try:
            result = subprocess.run([self.adb, "-s", self.serial, *args],
                                    capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PatchError(f"Android command failed: {exc}") from exc
        text = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode or re.search(r"(?m)^Failure|^Error:|^Exception", text):
            raise PatchError(f"Android command failed: {text}")
        return text


def _adb() -> str:
    direct = shutil.which("adb")
    if direct:
        return direct
    for root in _sdk_roots():
        for name in ("adb", "adb.exe"):
            candidate = root / "platform-tools" / name
            if candidate.is_file():
                return str(candidate)
    raise PatchError("--install-adopted requires Android SDK Platform Tools (adb)")


def prepare_adopted(serial: str | None = None) -> AdoptedDevice:
    adb = _adb()
    try:
        result = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PatchError(f"Cannot list Android devices: {exc}") from exc
    if result.returncode:
        raise PatchError(f"Cannot list Android devices: {result.stderr.strip()}")
    devices = [m.groups() for m in re.finditer(r"(?m)^(\S+)\s+(device|offline|unauthorized)\s*$", result.stdout)]
    if serial:
        devices = [d for d in devices if d[0] == serial]
    if len(devices) != 1 or devices[0][1] != "device":
        raise PatchError("Connect and authorize exactly one Android device, or select one with --device SERIAL")
    device = AdoptedDevice(adb, devices[0][0], "")
    volumes = device.command("shell", "sm", "list-volumes", "private")
    mounted = {parts[2] for line in volumes.splitlines()
               if len(parts := line.split()) == 3 and parts[0].startswith("private:")
               and parts[1] == "mounted" and re.fullmatch(r"[0-9A-Fa-f-]{8,64}", parts[2])}
    primary = device.command("shell", "sm", "get-primary-storage-uuid").strip()
    if primary not in mounted:
        raise PatchError(
            "--install-adopted requires a mounted adopted SD card selected as primary shared storage. "
            "In Android Storage settings, migrate data to the adopted card first. "
            "The patcher does not format cards or migrate device-wide storage.")
    return dataclasses.replace(device, volume=primary)


def verify_adopted(device: AdoptedDevice, package: str) -> dict[str, str]:
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package):
        raise PatchError("Invalid Android package name")
    dump = device.command("shell", "dumpsys", "package", package)
    # The Packages block is authoritative; do not accept paths from old records
    # or another user's dump section.
    block = re.search(r"(?ms)^Packages:\s*\n(.*?)(?=^\S|\Z)", dump)
    if not block:
        raise PatchError("Android did not report the installed package storage")
    fields = dict(re.findall(r"(?m)^\s+(codePath|dataDir|volumeUuid)=(\S+)\s*$", block[1]))
    root = f"/mnt/expand/{device.volume}/"
    if fields.get("volumeUuid") != device.volume or not all(
        fields.get(key, "").startswith(root) for key in ("codePath", "dataDir")
    ):
        raise PatchError("Android did not place both the APK and private app data on adopted storage")
    if device.command("shell", "sm", "get-primary-storage-uuid").strip() != device.volume:
        raise PatchError("Primary shared storage changed during installation")
    return {"device": device.serial, "volume": device.volume,
            "code_path": fields["codePath"], "data_path": fields["dataDir"],
            "shared_storage": "adopted"}


def install_adopted(device: AdoptedDevice, apk: Path, package: str) -> dict[str, str]:
    # --no-incremental avoids unsupported incremental volumes; streaming avoids
    # copying a second APK into the almost-full internal /data/local/tmp.
    try:
        result = device.command("install", "--no-incremental", "--streaming", "-r",
                                "--force-uuid", device.volume, str(apk), timeout=1800)
        if not re.search(r"(?m)^Success\s*$", result):
            raise PatchError(f"Android did not confirm installation: {result}")
    except PatchError as exc:
        raise PatchError(
            f"Patched APK saved at {apk}, but adopted-storage installation failed: {exc}. "
            "For a signing conflict, back up saves and remove the differently signed app yourself; "
            "the patcher never uninstalls apps or clears their data.") from exc
    return verify_adopted(device, package)
