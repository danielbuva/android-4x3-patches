# Death Road to Canada

- Package: `com.noodlecake.drtc`
- Engine: Deathforth / SDL2
- Tested build: `1.8.2` (version code `57`)
- Tested architectures: ARM64 and ARMv7
- Status: experimental; visual review pending

This module changes the game's logical render size from 480x320 to 480x360.
The same taller 4:3 coordinate space is used by the intro, menus, gameplay,
camera, and touch mapping, rather than stretching or squashing the old
logical frame.

## Changes

- Changes the logical renderer height from 320 to 360 in every supported
  `libmain.so` bundled in the APK.
- Converts the audited 2560x1600 Android splash to 1920x1440 with a uniform
  scale and centered cover crop. The artwork is not stretched or squashed.
- Disables the audited Flurry initialization, activity lifecycle tracking,
  user-ID assignment, and central event sink.
- Prevents the audited Flurry manifest provider from starting the SDK while
  still returning a successful provider result.
- Disables the audited **More Games** website action.

Play Games and the game's license checks are deliberately preserved. Shared
third-party branding cleanup is independent of this module and remains a
silent no-op when no recognized addition is present.

## Usage

This patch is experimental and must be enabled explicitly:

```sh
./patch.sh --allow-experimental "/path/to/death-road-to-canada.apk"
```

The default output is `output/Death-Road-to-Canada-4x3.apk`. Use `--check`
first to inspect compatibility without building an APK.

## Compatibility

The package must be `com.noodlecake.drtc`. The tested version number is
informational, but this particular transformation is intentionally strict
about the files it modifies:

- At least one audited ARM64 or ARMv7 `libmain.so` must be present. Each
  supported ABI is inspected and patched independently.
- Every `libmain.so` present in the APK must use an audited ABI/path. An
  unrecognized native variant fails safely instead of being left with a
  different logical resolution.
- Native edits require the expected ELF architecture and mapping, exact
  original-or-patched instructions, and the audited canonical library hash.
- `classes.dex` must contain one copy of every complete class, method, and
  descriptor identity used by the Flurry and **More Games** cleanup, with a
  recognized instruction prefix.
- The Android splash must match either the audited source image or the exact
  deterministic patched result.

There is no whole-APK hash or signing-certificate requirement. Differently
signed or repackaged copies can work when all of the audited target entries
are unchanged, and an already-patched input is accepted. A revision with a
changed native library, cleanup implementation, splash, missing target, or
ambiguous target is reported as unsupported rather than patched by guesswork.

## Verification

The module verifies every replacement after writing it and then rechecks the
combined APK entry state. Proprietary-free automated tests cover independent
ARM64 and ARMv7 operation, already-patched inputs, unknown-ABI rejection,
semantic DEX method matching, and deterministic aspect-preserving splash
conversion.

The 4:3 result is structurally verified against the tested build, but its
intro, menu, gameplay, camera, and touch presentation has not yet completed a
visual review on the target device. Keep `--allow-experimental` enabled only
if you accept that testing status.

## Known limitations

- Other CPU architectures and changed `libmain.so` revisions are not yet
  supported.
- The reported analog menu flicker was compared on the physical device using
  injected analog-axis, D-pad, and idle captures. The selection stayed fixed;
  the same corner/skull color animation continued after D-pad input and while
  idle. No isolated dead-zone or repeat defect was found, so the module does
  not alter normal SDL analog gameplay input.
- A reported 48-pixel black strip was traced to Android temporarily leaving
  its status-bar inset visible. A cold launch restored the full 1280x960
  surface and it remained fullscreen through title-to-gameplay input. This
  module does not alter the renderer to compensate for a transient system bar.
- The audited DEX cleanup and splash are required targets for this module;
  builds that substantially change either entry need a new compatibility
  profile.
- Raw split APK sets must be merged into one installable APK before patching.
- The rebuilt APK cannot retain the original developer signature.

## Signing and installation

By default, the shared patcher generates or reuses a private PKCS12 signing
identity in the current user's operating-system data directory. That identity
and its password are not part of this repository.

Android cannot install the result as an update over a copy signed with a
different key. Back up any saves you care about before uninstalling an
existing installation; uninstalling can erase private app data. Once the
signature situation is understood, install the generated APK with:

```sh
adb install "output/Death-Road-to-Canada-4x3.apk"
```
