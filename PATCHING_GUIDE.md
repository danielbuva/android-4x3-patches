# Step-by-step APK patching guide

This guide turns a game APK you already own into a separately signed 4:3 APK. It works on macOS, Linux, and Windows. Your original APK is never changed.

## Before you begin

1. Confirm that your game appears in the [supported-patches table](README.md#supported-patches). Every row labeled **Experimental** requires `--allow-experimental`; this acknowledges its visual-testing status without bypassing compatibility checks.
2. Keep a copy of your original APK somewhere safe. This project does not provide game APKs.
3. Back up any important saves before installing a patched build. A patched APK is signed with your own local key, so Android may require you to uninstall a differently signed existing installation. Uninstalling can erase private app data.

## 1. Install the required tools

Install these before continuing:

- Git, for downloading and updating this repository
- Python 3.11 or newer
- Java/JDK 17 or newer
- A current Android SDK Build Tools release, including `zipalign` and `apksigner` (tested with 36.0.0)
- Android SDK Platform Tools (`adb`) if you want to copy from or install to a USB-connected device

The easiest cross-platform way to obtain the Android tools is Android Studio: open **SDK Manager**, install the current **Android SDK Build-Tools**, and make sure the Android SDK location is available through `ANDROID_SDK_ROOT` or `ANDROID_HOME`. The patcher also searches common SDK locations and your command path.

Advent Neon, FAITH, and Hotline Miami additionally need UndertaleModTool CLI 0.9.1.2 or newer. Advent Neon was tested with 0.9.2.0. Put `UndertaleModCli` on your command path, or set `ANDROID_4X3_UMT` to its executable path.

On macOS or Linux, you can set it for the current terminal like this:

```sh
export ANDROID_4X3_UMT="/path/to/UndertaleModCli"
```

In Windows Command Prompt:

```bat
set "ANDROID_4X3_UMT=C:\path\to\UndertaleModCli.exe"
```

In Windows PowerShell:

```powershell
$env:ANDROID_4X3_UMT = "C:\path\to\UndertaleModCli.exe"
```

Streets of Rage 4 additionally needs `ffmpeg` and `ffprobe` on your command path, with an FFmpeg build that includes the `libx264` encoder.

## 2. Download the patcher

Open a terminal (Terminal on macOS, a shell on Linux, or Command Prompt/PowerShell on Windows) and run the commands for your system.

### macOS or Linux

```sh
git clone https://github.com/danielbuva/android-4x3-patches.git
cd android-4x3-patches
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
git clone https://github.com/danielbuva/android-4x3-patches.git
Set-Location android-4x3-patches
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Windows Command Prompt

```bat
git clone https://github.com/danielbuva/android-4x3-patches.git
cd android-4x3-patches
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

You only need to do this setup once per copy of the repository. Later, open a terminal in this folder and run the patch command below.
When updating an existing checkout, run `git pull` and repeat the dependency
installation command so newly added game support and Python packages stay in
sync.

## 3. Copy the APK from Android, if necessary

Skip this step if the APK is already on the computer. If it is in a connected Android device's Download folder, first list the available files:

```sh
adb shell ls -la /sdcard/Download
```

Then copy the selected file to the current folder:

```sh
adb pull "/sdcard/Download/Your Game.apk" "./Your Game.apk"
```

A filename beginning with `.pending-` may indicate an unfinished download. Wait for the download to finish when possible. The next step reads every APK entry and will reject incomplete or corrupt files with a CRC error.

## 4. Check your APK first

Use `--check` before making an output. Replace the example path with your own APK path; quotation marks allow spaces in filenames.

### macOS or Linux

```sh
./patch.sh --check "/path/to/Your Game.apk"
```

### Windows PowerShell

```powershell
.\patch.ps1 --check "C:\path\to\Your Game.apk"
```

If local PowerShell policy blocks `.ps1` files, use the Command Prompt launcher
from PowerShell as `.\patch.bat --check "C:\path\to\Your Game.apk"`.

### Windows Command Prompt

```bat
patch.bat --check "C:\path\to\Your Game.apk"
```

If the result says `Compatibility: original` or `Compatibility: already patched`, continue. If it says `unsupported` or `ambiguous`, that APK revision is not safely recognizable; do not try to force it. A CRC failure means the APK itself is incomplete or corrupt and should be obtained again from a clean source.

## 5. Create the patched APK

Run the same command without `--check`.

### macOS or Linux

```sh
./patch.sh "/path/to/Your Game.apk"
```

### Windows PowerShell

```powershell
.\patch.ps1 "C:\path\to\Your Game.apk"
```

### Windows Command Prompt

```bat
patch.bat "C:\path\to\Your Game.apk"
```

The patcher reports the output location when it finishes. By default it is placed in the repository's `output` folder and named like `Game-4x3.apk`.

Hollow Knight APKs using the large Mono port can remain quiet for several
minutes while the patcher rewrites their single Unity bundle. Keep the terminal
open and allow several gigabytes of temporary free space. The patcher detects
that port automatically; you use the same command as for the earlier IL2CPP
port.

For any game labeled **Experimental**, add the acknowledgement flag before the input path:

```sh
./patch.sh --allow-experimental "/path/to/Your Game.apk"
```

On Windows PowerShell, the equivalent is:

```powershell
.\patch.ps1 --allow-experimental "C:\path\to\Your Game.apk"
```

In Windows Command Prompt, use:

```bat
patch.bat --allow-experimental "C:\path\to\Your Game.apk"
```

For Advent Neon, acknowledge that device-side visual iteration is still pending:

```sh
./patch.sh --allow-experimental "/path/to/Advent-Neon.apk"
```

For Baba Is You, acknowledge its known right-edge cropping defect explicitly:

```sh
./patch.sh --allow-experimental "/path/to/Baba-Is-You.apk"
```

To choose an output location yourself, add `--output` before the APK path:

```sh
./patch.sh --output "/path/to/output/Game-4x3.apk" "/path/to/Your Game.apk"
```

## 6. Install on your Android device

After connecting a device with USB debugging enabled, install the new file:

```sh
adb install "/path/to/Game-4x3.apk"
```

If a very large APK fails during streamed installation, use Android's
non-streaming transfer mode:

```sh
adb install --no-streaming "/path/to/Game-4x3.apk"
```

Use `-r` only when replacing an installed copy that was signed with the same
locally generated key (or the same custom key):

```sh
adb install -r --no-streaming "/path/to/Game-4x3.apk"
```

The Hollow Knight 1.3.0.0 Mono port is a special case: it extracts its large
Unity bundle into app-specific storage on first run. A replace-install of
another APK with the same version can keep loading that older extracted copy.
On some devices, uninstall alone can also leave its external package folder
behind. Back up any saves you want, open Android's app info page, choose
**Storage & cache → Clear storage while the app is still installed**, then
uninstall it and install the new APK cleanly. This does not apply to the earlier
IL2CPP Hollow Knight port.

If Android reports a signature conflict, do **not** immediately uninstall the old app. First back up any saves you care about. Once that is done, remove the old differently signed installation through Android and install the patched APK again. Whether cloud saves restore depends on the game and the account you use.

## What the patcher does automatically

- Identifies the game from its Android package name.
- Refuses unknown or ambiguous required 4:3 targets instead of guessing.
- Rebuilds, aligns, signs, and verifies the final APK.
- Creates and reuses a random local signing key outside this repository.
- Silently removes known safe source-specific branding only when it is confidently recognized; its absence never blocks the 4:3 patch.

The patcher preserves cloud saves, Play Games, billing, purchases, and unrelated online features.

## Common problems

| What you see | What to do |
|---|---|
| `zipalign` or `apksigner` is missing | Install Android SDK Build Tools and set `ANDROID_SDK_ROOT` or `ANDROID_HOME` if necessary. |
| `apksigner` does not recognize `--alignment-preserved` | Update Android SDK Build Tools to a current release. |
| `CRC verification failed` | The APK is incomplete or corrupt. Obtain a clean copy instead of forcing the patch. |
| `UndertaleModTool` is missing | Install its CLI for Advent Neon, FAITH, or Hotline Miami, then set `ANDROID_4X3_UMT` to it. |
| `unsupported` or `ambiguous` | Your APK build has changed a required target. It is not safe to patch with this release. |
| The same APK is supported on one computer but not another | Update both checkouts with `git pull`, then reinstall `requirements.txt`. Compatibility detection itself is platform-independent. |
| Android rejects installation | The installed app has a different signing key. Back up saves before replacing it. |
| A revised Hollow Knight 1.3.0.0 APK still shows the old HUD or inventory | The Mono port cached its extracted Unity bundle. Back up saves, clear the app's storage from Android app info **before** uninstalling, then install the revised APK cleanly. |
| Baba Is You is still cut off | This is the documented experimental limitation. |
| Advent Neon shows unfinished room edges or framing | Its initial 4:3 pass is structurally verified but still requires device-side visual iteration. |

For machine-readable diagnostics, use `--check --json`. For all commands, see the [main README](README.md#useful-commands).
