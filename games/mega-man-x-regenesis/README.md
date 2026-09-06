# Mega Man X Regenesis

Experimental patch for developer build **1.00.82** (Android manifest version
`1.0.0`, version code `1`, package `com.example.megamanxregenesis`). Supply your
own APK. No extracted game source, artwork, APK, or signing material is included.

## Changes

- Expand the logical viewport from **384×216 to 384×288** with Godot's existing
  proportional `canvas_items` presentation. World zoom and horizontal coverage
  stay unchanged: the camera shows **36 additional units above and below**.
- Retain the original 216-unit camera-zone tracking footprint in both initial
  snapping and continuous following. This prevents inverted vertical bounds in
  short rooms and keeps camera motion consistent with the original game.
- Enlarge health, weapon, ride-armor, and boss HUDs uniformly to **125%**;
  retain the boss bar's right alignment. Center the **110%** pause layers.
- Center and enlarge standalone save/difficulty, input, achievements,
  and touch-remapping menus to **115%**.
- Reflow options across the full 384×288 frame with separated text/value columns,
  16.5-unit row spacing, and labels enlarged uniformly up to **125%**. Longer
  translations fit their column without clipping; language and save-slot values
  remain visible. Keep original selection and settings behavior.
- Enlarge title menu choices to **120%** and input labels to **112%**.
  Center dialogue/warning/timer layers in the taller frame and extend transition
  coverage to the full height. Existing touch controls retain their native anchors.
- Preserve original scripts except for two camera expressions and added layout
  methods on the existing ShaderWarmup autoload. Keep the original warmup logic.
- Update the sparse PCK directory's lengths and MD5 records for all changed
  assets. This is essential: stale lengths truncate compiled scripts at runtime.

The full game still needs physical-device testing. Extra camera coverage may
expose level boundaries or artwork that was outside the developer's intended
frame. Authored menu/cinematic backgrounds are preserved, not stretched or filled
with invented art. In build 1.00.82, the main title background sprite is hidden;
the visible particles already extend beyond the old 16:9 frame. Its large light
bars appear only during the opening animation. No background zoom is applied
because there is no active bounded image to fill. Report affected screens for
targeted follow-up adjustments.

## Build

Install the repository requirements and Android SDK Build Tools as described in
the root README. Also download [GDRE Tools 2.6.4 or later](https://github.com/GDRETools/gdsdecomp/releases)
and set `GDRE_TOOLS` to its executable. On macOS, this is the executable inside
`Godot RE Tools.app/Contents/MacOS/Godot RE Tools`, not the app directory.

### macOS / Linux

```sh
export GDRE_TOOLS="/path/to/Godot RE Tools.app/Contents/MacOS/Godot RE Tools"
./patch.sh --allow-experimental --check "/path/to/developer.apk"
./patch.sh --allow-experimental "/path/to/developer.apk" \
  --output "/path/to/Mega Man X Regenesis-4x3.apk"
```

### Windows PowerShell

Download the **Windows** GDRE archive and extract its whole directory. Point the
variable at the executable supplied in that archive (prefer its console build):

```powershell
$env:GDRE_TOOLS = "C:\Tools\GDRE\gdre_tools.exe"
.\patch.ps1 --allow-experimental --check "C:\APKs\developer.apk"
.\patch.ps1 --allow-experimental "C:\APKs\developer.apk" `
  --output "C:\APKs\Mega Man X Regenesis-4x3.apk"
```

### Windows Command Prompt

```bat
set "GDRE_TOOLS=C:\Tools\GDRE\gdre_tools.exe"
patch.bat --allow-experimental --check "C:\APKs\developer.apk"
patch.bat --allow-experimental "C:\APKs\developer.apk" --output "C:\APKs\Mega Man X Regenesis-4x3.apk"
```

Replace the example executable filename if the release uses a different name.
Paths with spaces and Unicode are supported. The patcher explicitly reads/writes
Godot scripts as UTF-8, independent of the Windows system code page.

Build this revision from the original developer APK, including when updating an
older patch revision. The patcher recognizes original and current patched states, refuses mixed/unknown states,
and validates the rebuilt signed result. It matches project settings and script
structure rather than the APK filename, version code, or whole-APK hash. Bytecode
version 101 is compiled with GDRE's `4.5.0` definition, also used by this Godot 4.7
export. Unknown engine bytecode or changed startup/camera logic requires review.

## Signing and future developer APKs

The normal repository signing flow uses a persistent private key under
`~/.local/share/android-4x3-patches/` on macOS/Linux. Back up that entire directory
securely, including password files. On Windows the corresponding directory is
`%LOCALAPPDATA%\android-4x3-patches\`. To switch build computers while keeping
in-place updates, securely copy the signing files into that directory **before**
the first build; otherwise the new computer generates a different key. Never
commit signing files. No alternate package ID is
needed on a device without the original developer-signed installation.

For updates, supply the new developer APK, run the compatibility check, rebuild
with the **same key and package**, then install with `-r`. Android accepts updates
with an equal version code (this developer currently uses `1`), or a higher code.
Do not uninstall between patched updates: uninstalling deletes app data. A future
unpatched developer-signed APK cannot directly replace the locally signed build;
patch and sign it first. Source revisions that change the UI structure need visual
review even when the camera and bytecode checks pass.

## Adopted-storage installation

Inspect `adb shell sm list-volumes all` for the mounted **private** SD UUID. Stream
the APK directly into an install session pinned to that UUID:

```sh
adb install --streaming --no-incremental --force-uuid SD_PRIVATE_UUID -r \
  "/path/to/Mega Man X Regenesis-4x3.apk"
adb shell pm path com.example.megamanxregenesis
```

The installed path must begin `/mnt/expand/SD_PRIVATE_UUID/`. Do not fall back to
an internal-storage installation or copy a staging APK to `/data/local/tmp`.
Only one package is installed; the streamed install leaves no loose APK on the SD.
Android still retains small package-manager records on internal storage.

## Verification

Synthetic tests cover config preservation, unknown/duplicate targets, both camera
paths, lifecycle conflicts, mixed patch states, and sparse-index length/hash
updates. The repository suite and compile check are required before committing.
See the root verification record for the actual device smoke-test result.
