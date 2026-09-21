# Afterimage

- Package: `com.aurogon.Afterimage`
- Audited Android build: **1.0.4 (50), ARM64, Unreal Engine 4.27.2**
- Target: **1280×960 (4:3)**
- Status: **experimental**, pending the owner's broader manual verification

The gameplay camera now uses the full viewport. The camera's location, rotation,
field of view, orthographic width, clipping planes, and game assets are retained.
Projection uses horizontal field of view as its reference, adding vertical world
coverage on a taller display instead of stretching the picture or cropping its
sides. The camera flag change was observed taking effect in opening gameplay.

The supplied build's HUD already anchors to the actual 4:3 screen. Its top-edge
health display, settings control, bottom control, and gameplay prompts are
retained at their existing readable scale. No second UI scaling operation is
applied. The Android theme disables the system focus-highlight rectangle around
the game window; focus, controller navigation, and touch coordinates are retained.

## Build on macOS

Follow the repository's [setup guide](../../PATCHING_GUIDE.md), then run:

```sh
./patch.sh --allow-experimental --check "/path/to/Afterimage.apk"
./patch.sh --allow-experimental --output "output/Afterimage-v1.0.4-4x3.apk" "/path/to/Afterimage.apk"
```

## Build on Windows

After installing the same prerequisites, in PowerShell:

```powershell
.\patch.ps1 --allow-experimental --check "C:\Games\Afterimage.apk"
.\patch.ps1 --allow-experimental --output "output\Afterimage-v1.0.4-4x3.apk" "C:\Games\Afterimage.apk"
```

`patch.bat` accepts the same arguments in Command Prompt. No Unreal SDK,
asset-extraction program, native compiler, or additional Python dependency is
required. Both hosts use the shared alignment and local-signing implementation.

### Original-aspect companion

This alternative applies the Android window-border fix while retaining the
original camera library. Supply the original APK, not a 4:3-patched copy.

```sh
# macOS, from the repository root
.venv/bin/python games/afterimage/original_aspect.py "/path/to/Afterimage.apk" --output "output/Afterimage-v1.0.4-original-aspect.apk"
```

```powershell
# Windows PowerShell, from the repository root
.\.venv\Scripts\python.exe games\afterimage\original_aspect.py "C:\Games\Afterimage.apk" --output "output\Afterimage-v1.0.4-original-aspect.apk"
```

The companion refuses an existing output path or an input with any camera edit.

## Compatibility and reproducibility

Audited whole-source APK SHA-256 (an identification record, not the sole gate):

```text
08b799e85ebf436db5822f0ebd41b53f607587b545ee989d973c6db6a88ced72
```

Original `lib/arm64-v8a/libUE4.so` SHA-256:

```text
4c718bb89b763d080f60284f1675ca73a7ce323e27e4241792c515552de833f9
```

Final camera library SHA-256:

```text
0f70aa2409b5171583a59438f85f7b4a105dd77ab067038c7f0efb104e142d25
```

The patch requires the audited ARM64 ELF mapping, two unique instruction
contexts, and the canonical library hash after normalizing those sites. It
recognizes original, partially patched, and fully patched instruction states.
An unrelated native edit or rebuilt engine is refused, even if its version
label matches. Repackaged or differently signed copies can pass when their
required contents match.

The resource edit finds `UE4BaseTheme` semantically in the game's Android
resource table, requires its expected parent and definition, and inserts one
boolean attribute. It updates the containing table sizes and subsequent entry
offsets, preserves adjacent styles, and recognizes its completed state.
Unfamiliar, ambiguous, sparse, or conflicting theme definitions are rejected.
`--allow-experimental` acknowledges testing limits; it never bypasses these checks.

## Verification and limitations

- macOS: source-to-output patching, original-aspect companion, complete APK CRC,
  signing, alignment, resource decoding, exact native post-state, and synthetic
  compatibility tests were exercised.
- A limited physical-device check established that the original-aspect build
  starts and reaches gameplay, and that clearing the camera constraint replaces
  the gameplay borders with additional world rendering. This is not a full-game
  acceptance test.
- The 4:3 result preserves the existing camera position and horizontal coverage.
  Rooms with finite decorative artwork may still reveal boundaries; no artwork
  is stretched, cropped, or invented to conceal them.
- Fixed-format loading and branding presentations may retain borders. Video and
  image files are unchanged. Every cinematic, subtitle language, menu, boss room,
  touch action, and screen transition has not been visually verified. The owner's
  manual review remains necessary, especially for touch hit targets and artwork
  coverage beyond the old camera frame.
- Only the audited ARM64 build is supported. The native offsets are guarded by
  the library hash and executable mapping; they are not portable to another
  compiled engine revision.
- Windows support uses the shared cross-platform Python and Android Build Tools
  path. Commercial-APK rebuilding on Windows has not been performed; see the
  repository's Mac and Windows CI checks for synthetic-platform results.

## Installation

The shared `--install-adopted` option streams the signed APK onto an already
adopted SD card and verifies APK, private app data, and primary shared-storage
placement. See [adopted storage instructions](../../README.md#optional-adopted-sd-storage).
It does not uninstall an existing differently signed copy or migrate storage.
No device identity or volume path is embedded in the APK or patch.

## Technical references

[Unreal's camera view fields](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MinimalViewInfo?application_version=4.27)
define orthographic width and aspect-constrained borders.
The [Android focus-border report](https://forums.unrealengine.com/t/remove-green-border-around-android-application/269901)
identifies `android:defaultFocusHighlightEnabled` as the game-window decoration
switch; this patch sets it in the game's theme without changing focus behavior.
