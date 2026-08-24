"""Android SDK tool discovery plus local, user-owned APK signing."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from .errors import PatchError


def _version_key(path: Path) -> tuple[int, ...]:
    values: list[int] = []
    for piece in path.name.replace("-", ".").split("."):
        try:
            values.append(int(piece))
        except ValueError:
            values.append(-1)
    return tuple(values)


def _sdk_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(key):
            roots.append(Path(os.environ[key]).expanduser())
    roots.extend(
        [
            Path.home() / "Library/Android/sdk",
            Path.home() / "Android/Sdk",
            Path.home() / "AppData/Local/Android/Sdk",
            Path("/opt/homebrew/share/android-commandlinetools"),
            Path("/usr/local/share/android-commandlinetools"),
        ]
    )
    sdkmanager = shutil.which("sdkmanager")
    if sdkmanager:
        resolved = Path(sdkmanager).resolve()
        # <sdk>/cmdline-tools/<version>/bin/sdkmanager
        if len(resolved.parents) >= 4:
            roots.append(resolved.parents[3])
    return list(dict.fromkeys(path.resolve() for path in roots if path.exists()))


def _executable_names(name: str, platform: str | None = None) -> tuple[str, ...]:
    if (platform or os.name) != "nt":
        return (name,)
    if name == "zipalign":
        return ("zipalign.exe", "zipalign")
    if name == "apksigner":
        return ("apksigner.bat", "apksigner")
    return (f"{name}.exe", f"{name}.bat", name)


def find_android_tool(name: str, *, platform: str | None = None) -> Path:
    executables = _executable_names(name, platform)
    for executable in executables:
        direct = shutil.which(executable)
        if direct:
            return Path(direct)
    candidates: list[Path] = []
    for root in _sdk_roots():
        build_tools = root / "build-tools"
        if build_tools.is_dir():
            for version in build_tools.iterdir():
                for executable in executables:
                    candidate = version / executable
                    if candidate.is_file():
                        candidates.append(candidate)
    if candidates:
        return sorted(candidates, key=lambda item: _version_key(item.parent), reverse=True)[0]
    raise PatchError(
        f"Android SDK tool '{name}' was not found. Install Android SDK Build Tools "
        "and set ANDROID_HOME/ANDROID_SDK_ROOT or add the tool to PATH."
    )


def _state_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "android-4x3-patches"


def _secure_write(path: Path, text: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
    finally:
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass


def _run(command: list[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        check=False,
    )
    if completed.returncode:
        safe = ["<secret>" if "ANDROID4X3" in part else part for part in command]
        detail = completed.stdout.strip()
        raise PatchError(f"command failed: {' '.join(safe)}\n{detail}")
    return completed.stdout


def ensure_keystore(custom: Path | None = None) -> tuple[Path, str, Path, Path]:
    """Return keystore, alias, and separate password files; generate defaults once."""
    if custom is not None:
        raise PatchError("custom keystores are handled by sign_apk")
    state = _state_dir()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(state, 0o700)
    except OSError:
        pass
    password_file = state / "signing-password.txt"
    key_password_file = state / "signing-key-password.txt"
    metadata_file = state / "signing.json"
    keystore = state / "signing.p12"
    alias = "android4x3"

    if not password_file.exists():
        _secure_write(password_file, secrets.token_urlsafe(32) + "\n")
    if not key_password_file.exists():
        _secure_write(key_password_file, password_file.read_text(encoding="utf-8"))
    if not keystore.exists():
        keytool = shutil.which("keytool")
        if not keytool:
            raise PatchError("keytool was not found; install a JDK (Java 17 or newer recommended)")
        environment = os.environ.copy()
        environment["ANDROID4X3_STOREPASS_FILE"] = str(password_file)
        _run(
            [
                keytool,
                "-genkeypair",
                "-storetype",
                "PKCS12",
                "-keystore",
                str(keystore),
                "-alias",
                alias,
                "-keyalg",
                "RSA",
                "-keysize",
                "3072",
                "-validity",
                "10000",
                "-dname",
                "CN=Android 4x3 Patcher",
                "-storepass:file",
                str(password_file),
                "-keypass:file",
                str(key_password_file),
                "-noprompt",
            ],
            env=environment,
        )
        try:
            os.chmod(keystore, 0o600)
        except OSError:
            pass
        _secure_write(
            metadata_file,
            json.dumps({"alias": alias, "format": "PKCS12"}, indent=2) + "\n",
        )
    return keystore, alias, password_file, key_password_file


def align_apk(unsigned: Path, aligned: Path) -> None:
    zipalign = find_android_tool("zipalign")
    _run([str(zipalign), "-f", "-P", "16", "4", str(unsigned), str(aligned)])
    verify_alignment(aligned)


def verify_alignment(apk: Path) -> None:
    zipalign = find_android_tool("zipalign")
    _run([str(zipalign), "-c", "-P", "16", "4", str(apk)])


def sign_apk(aligned: Path, signed: Path, custom_keystore: Path | None = None) -> None:
    apksigner = find_android_tool("apksigner")
    if custom_keystore is None:
        keystore, alias, password_file, key_password_file = ensure_keystore()
        _sign_with_files(
            apksigner, aligned, signed, keystore, alias, password_file, key_password_file
        )
    else:
        keystore = custom_keystore.expanduser().resolve()
        if not keystore.is_file():
            raise PatchError(f"custom keystore does not exist: {keystore}")
        password = os.environ.get("ANDROID4X3_KEYSTORE_PASSWORD")
        if not password:
            raise PatchError(
                "ANDROID4X3_KEYSTORE_PASSWORD must be set when --keystore is used"
            )
        alias = os.environ.get("ANDROID4X3_KEY_ALIAS", "android4x3")
        key_password = os.environ.get("ANDROID4X3_KEY_PASSWORD", password)
        with tempfile.TemporaryDirectory(prefix="android-4x3-signing-") as temporary:
            password_file = Path(temporary) / "store-password.txt"
            key_password_file = Path(temporary) / "key-password.txt"
            _secure_write(password_file, password + "\n")
            _secure_write(key_password_file, key_password + "\n")
            _sign_with_files(
                apksigner,
                aligned,
                signed,
                keystore,
                alias,
                password_file,
                key_password_file,
            )
    _run([str(apksigner), "verify", "--verbose", "--print-certs", str(signed)])


def _sign_with_files(
    apksigner: Path,
    aligned: Path,
    signed: Path,
    keystore: Path,
    alias: str,
    password_file: Path,
    key_password_file: Path,
) -> None:
    _run(
        [
            str(apksigner),
            "sign",
            "--ks",
            str(keystore),
            "--ks-key-alias",
            alias,
            "--ks-pass",
            f"file:{password_file}",
            "--key-pass",
            f"file:{key_password_file}",
            "--alignment-preserved",
            "true",
            "--out",
            str(signed),
            str(aligned),
        ]
    )
