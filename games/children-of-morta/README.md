# Children of Morta

- Package: `com.playdigious.childrenofmorta`
- Engine: Unity IL2CPP
- Tested build: `1.1.4` (version code `41`, ARM64)
- Status: experimental; structural verification complete, visual verification pending

This patch enables the game's 4:3 camera path, changes its cinematic aspect
constant to 4:3, and expands the relevant Unity UI reference resolutions. The
Android static splash is center-cropped proportionally rather than stretched.

## Changes

- Forces `CameraHandle.GetAspectRatio` through the constant-aspect path and
  changes that aspect from 2.35:1 to 4:3.
- Changes the recognized 1280x720 CanvasScaler references to 1280x960,
  1920x1080 references to 1920x1440, and 1200x720 references to 1200x900.
- Updates the live menu, HUD, home text, shared double-boss health bar, loading
  indicator, and in-engine splash cohorts while retaining existing 800x600
  components that are already 4:3.
- Converts the 1920x1079 Android splash to 1440x1080 with a uniform cover and
  center crop, preserving pixel proportions.
- Hides the **More Games** cross-promotion and disables the isolated
  `FirebaseAnalytics.LogEvent(string)` implementation.

Firebase application initialization remains intact. Billing, Play Pass,
purchases, cloud features, Play Games, Epic Online Services, and Firebase
Remote Config are deliberately preserved. Optional source-specific branding
cleanup is handled silently by the shared framework and never determines
compatibility.

## Usage

Check the APK without creating an output:

```sh
./patch.sh --check --allow-experimental "/path/to/Children-of-Morta-v1.1.4.apk"
```

Create, align, sign, and verify the patched APK:

```sh
./patch.sh --allow-experimental "/path/to/Children-of-Morta-v1.1.4.apk"
```

The default output name is `Children-of-Morta-4x3.apk`. See the
[step-by-step guide](../../PATCHING_GUIDE.md) for Windows commands,
installation, and troubleshooting.

## Compatibility and safety checks

The APK version and whole-APK hash are informational. Compatibility requires
the tested ARM64 `libil2cpp.so`, Android splash, and four Unity bundle entries.
The module then applies two complementary forms of validation:

- Unity CanvasScaler objects are identified by serialized script identity,
  object structure, expected names where needed, exact cohort counts, and
  recognized original or patched reference resolutions. Unity PathIDs are not
  treated as stable compatibility identifiers.
- The ARM64 library is checked as a 64-bit little-endian AArch64 ELF with the
  audited size and canonical native identity. Every camera, cinematic,
  cross-promotion, and analytics edit must have the expected virtual-address
  mapping and exact original or patched bytes.

The static splash is also constrained by its audited dimensions and original
or patched identity. Required targets may be original, partially patched, or
fully patched, but an absent, changed, extra, or ambiguous target causes the
module to stop instead of guessing. Each modified bundle is saved with its
original UnityFS packing mode, reopened, and checked; the combined output must
finish in the fully patched state.

## Signing

Rebuilding invalidates the developer signature. By default, the patcher
generates and reuses a private local signing identity outside the repository,
then verifies the final APK's alignment and signature. Android may require an
installed copy signed by a different key to be removed before installation;
back up any saves you care about first.

## Verification status and limitations

Proprietary-free tests cover guarded AArch64 transformation, partial and
already-patched states, semantic CanvasScaler discovery and mutation, neutral
4:3 objects, exact cover-crop behavior, and refusal after unrelated native
changes. Development outputs have also passed structural patched-state
recognition. Complete splash, menu, HUD, cinematic, and gameplay inspection on
a physical device is still pending, so `--allow-experimental` is required.

- The native portion currently supports only the audited ARM64 1.1.4 library.
- A revised Unity object cohort, native library, or Android splash requires a
  fresh compatibility audit even when the package and visible version match.
- The splash intentionally crops its left and right edges to fill 4:3; it is
  not an expanded gameplay view.
