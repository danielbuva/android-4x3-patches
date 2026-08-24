# Step-by-step APK patching guide

This guide turns a game APK you already own into a separately signed 4:3 APK. It works on macOS, Linux, and Windows. Your original APK is never changed.

## Before you begin

1. Confirm that your game appears in the [supported-patches table](README.md#supported-patches). Baba Is You is experimental and requires the extra command shown below.
2. Keep a copy of your original APK somewhere safe. This project does not provide game APKs.
3. Back up any important saves before installing a patched build. A patched APK is signed with your own local key, so Android may require you to uninstall a differently signed existing installation. Uninstalling can erase private app data.

## 1. Install the required tools

Install these before continuing:

- Python 3.11 or newer
- Java/JDK 17 or newer
- Android SDK Build Tools, including `zipalign` and `apksigner`

The easiest cross-platform way to obtain the Android tools is Android Studio: open **SDK Manager**, install the current **Android SDK Build-Tools**, and make sure the Android SDK location is available through `ANDROID_SDK_ROOT` or `ANDROID_HOME`. The patcher also searches common SDK locations and your command path.

FAITH and Hotline Miami additionally need UndertaleModTool CLI 0.9.1.2 or newer. Put `UndertaleModCli` on your command path, or set `ANDROID_4X3_UMT` to its executable path.

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

### Windows

```bat
git clone https://github.com/danielbuva/android-4x3-patches.git
cd android-4x3-patches
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

You only need to do this setup once per copy of the repository. Later, open a terminal in this folder and run the patch command below.

## 3. Check your APK first

Use `--check` before making an output. Replace the example path with your own APK path; quotation marks allow spaces in filenames.

### macOS or Linux

```sh
./patch.sh --check "/path/to/Your Game.apk"
```

### Windows

```bat
patch.bat --check "C:\path\to\Your Game.apk"
```

If the result says `Compatibility: original` or `Compatibility: already patched`, continue. If it says `unsupported` or `ambiguous`, that APK revision is not safely recognizable; do not try to force it.

## 4. Create the patched APK

Run the same command without `--check`.

### macOS or Linux

```sh
./patch.sh "/path/to/Your Game.apk"
```

### Windows

```bat
patch.bat "C:\path\to\Your Game.apk"
```

The patcher reports the output location when it finishes. By default it is placed in the repository's `output` folder and named like `Game-4x3.apk`.

For Baba Is You, acknowledge its known right-edge cropping defect explicitly:

```sh
./patch.sh --allow-experimental "/path/to/Baba-Is-You.apk"
```

To choose an output location yourself, add `--output` before the APK path:

```sh
./patch.sh --output "/path/to/output/Game-4x3.apk" "/path/to/Your Game.apk"
```

## 5. Install on your Android device

After connecting a device with USB debugging enabled, install the new file:

```sh
adb install "/path/to/Game-4x3.apk"
```

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
| `UndertaleModTool` is missing | Install its CLI for FAITH or Hotline Miami, then set `ANDROID_4X3_UMT` to it. |
| `unsupported` or `ambiguous` | Your APK build has changed a required target. It is not safe to patch with this release. |
| Android rejects installation | The installed app has a different signing key. Back up saves before replacing it. |
| Baba Is You is still cut off | This is the documented experimental limitation. |

For machine-readable diagnostics, use `--check --json`. For all commands, see the [main README](README.md#useful-commands).
