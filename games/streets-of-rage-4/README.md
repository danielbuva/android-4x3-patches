# Streets of Rage 4

- Package: `com.playdigious.sor4`
- Engine: Xamarin/.NET MonoGame
- Tested build: `1.4.5` (version code `91`, `arm64-v8a`)
- Status: verified

## Changes

This module converts the game's complete Android presentation path to 4:3:

- Gameplay uses a Vert+ perspective camera. The original horizontal world
  span is retained while the taller viewport reveals additional world above
  and below; the image is not cropped, stretched, or squashed.
- Render targets, preloading output, HUD calculations, camera/culling height,
  and the default GUI canvas are updated for 4:3. The GUI reference becomes
  1920 x 1440.
- The two managed draw calls for the mobile border-filler artwork are
  suppressed. The packaged assets and loading paths remain intact, but the
  artwork can no longer cover the game or menus.
- Two non-interactive backgrounds are found by their named records inside
  `assets/bigfile`: the title screen and main-menu background. Each is scaled
  proportionally and center-cropped to fill 4:3.
- The shared desktop/mobile **Back** and **Select** button legend is moved from
  the old widescreen bottom to the bottom of the 1920x1440 menu canvas. Other
  controls and touch targets retain their existing layout.
- Named pre-game GUI roots are expanded from 1920x1080 to 1920x1440 across the
  title, main menu, difficulty, character/player select, story, cutscene-skip,
  and loading screens. Nested templates and the gameplay HUD remain untouched.
- All 17 bundled intro, logo, boss, and stage videos are proportionally
  center-cropped from 1280 x 720 to 960 x 720. Their audio streams, frame rate,
  frame count, and duration are retained and checked after encoding.

The isolated analytics event sent when opening **More Games** is suppressed
when its recognized managed-code target is present. Firebase initialization,
Remote Config, billing, cloud saves, Play Games, EOS, support features, and the
More Games view itself are preserved. Other optional third-party branding
cleanup is handled silently by the shared framework and is never a 4:3
compatibility requirement.

## Prerequisites and usage

In addition to the repository's normal prerequisites, `ffmpeg` and `ffprobe`
must be available on `PATH`, and FFmpeg must include the `libx264` encoder.

```sh
./patch.sh "/path/to/Streets-of-Rage-4.apk"
```

The default output name is `Streets-of-Rage-4-4x3.apk`. Video conversion makes
this patch take longer than modules that only edit code or configuration.

## Compatibility

The patcher first validates the AArch64 Xamarin assembly store and the audited
`SOR4.dll` image. The managed target is deliberately constrained to the tested
code image, but the complete APK hash, signing certificate, version metadata,
filename, and distribution source are not compatibility gates. Recognized
partially patched managed states are completed, and unfamiliar bytes in the
optional analytics-cleanup range are preserved.

The menu patch does not require a whole-`bigfile` hash. It strictly parses the
raw-DEFLATE archive, requires exactly one named GUI record, validates each
outer root structurally, and requires one exact original-or-patched transform
context for each background and button-legend target. All other records are
preserved. A missing, duplicated, or ambiguous required record is rejected
without guessing.

Each of the 17 required videos must be recognized as either an original H.264
1280 x 720 stream or an already-patched H.264 960 x 720 stream with square
pixels. Mixed original and patched inputs are supported: only work that remains
is performed. Missing videos and unrecognized stream shapes fail safely.

## Verification

The full workflow was reproduced from a clean, unpatched copy of the tested
build: target detection, managed-store rewriting, named-`bigfile` transforms,
all video crops, APK rebuilding, alignment, signing, patched-state detection,
installation, and cold launch.

On a physical 1280 x 960 Android device, gameplay, the **Tap Anywhere** title
screen, and the main menu were visually verified to fill the display at 4:3.
Gameplay retains its original horizontal view and exposes the intended extra
vertical area; the former mobile border artwork no longer covers the rendered
scene.

The later **Back**/**Select** button-legend refinement passed target detection,
rebuilding, patched-state verification, in-place installation, and cold
launch. Its exact bottom placement still awaits a follow-up visual check.

## Known limitations

- A revision with a different managed assembly needs a separately audited code
  pattern even if its package and assets are otherwise compatible.
- Other serialized menu roots or unusual per-stage camera overrides may need
  follow-up if a future build introduces them.
- The 17 videos are re-encoded, so the result is visually equivalent rather
  than byte-identical to the source streams.
- The original developer signature cannot be retained after rebuilding.
