# Grimvalor

- Package: `com.direlight.grimvalor`
- Engine: Unity IL2CPP
- Tested build: `1.2.13` (version code `76`), ARM64
- Status: experimental; visual review pending

The audited game already contains a 4:3 UI path, while its gameplay and
cinematic cameras consume Unity's live `Camera.aspect`. This patch enables the
built-in 4:3 selector instead of replacing the camera math with a fixed aspect
ratio.

## Changes

- Enables `UIResolution.get_is4_3`, selecting the built-in 4:3 intro, menu,
  and UI layouts.
- Leaves the existing live-aspect gameplay and cinematic camera behavior in
  place so it can respond to the device's real framebuffer.
- Disables the audited interstitial-ad initialization, request, eligibility,
  and display paths.
- Disables the audited game-analytics initialization, queue, send, and update
  paths.

Billing, purchases, cloud saves, authentication, achievements, and Play Games
are outside this patch and are preserved. Optional shared branding cleanup is
not a compatibility requirement.

## Usage

This patch is experimental and must be enabled explicitly:

```sh
./patch.sh --allow-experimental "/path/to/Grimvalor-v1.2.13.apk"
```

The default output is `output/Grimvalor-v1.2.13-4x3.apk`. Use `--check` first
to inspect compatibility without producing a build.

## Compatibility

The package must be `com.direlight.grimvalor`, and the APK must contain the
audited ARM64 `libil2cpp.so`. The APK filename, signing certificate, and
whole-APK hash are not compatibility gates, but the current native patch is
tied to the tested IL2CPP library:

- The library must be the expected 64-bit little-endian ARM64 ELF with the
  audited executable mapping and canonical source hash.
- Every ad, analytics, and 4:3 edit is selected through its complete unique
  instruction context and expected RVA-to-file mapping.
- Each target may be original or already patched. A partially completed
  audited library is normalized and safely finished.
- A missing, moved, duplicated, or changed signature, unrelated native edit,
  or different canonical library is rejected rather than patched at a guessed
  location.

This means differently signed or repackaged APKs can work when they retain the
same audited ARM64 library. A newly compiled game revision will usually need a
new native compatibility profile even if its Android version number is close.

## Verification

The module checks the final library against the exact expected patched hash
after all edits. Proprietary-free automated tests cover ELF mapping, complete
signature uniqueness, original/partial/patched states, exact final-state
verification, rejection of unrelated native changes, and separation of the
cleanup-only and 4:3 paths.

The transformation is structurally verified for the tested build, but its
visual result has not yet been reviewed on the target device. In particular,
testing must confirm the intro, menus, HUD, gameplay camera, cinematics, and
disabled interstitial and analytics flows.

## Known limitations

- Only the audited ARM64 IL2CPP library is supported.
- The patch relies on a real 4:3 Android framebuffer. Enabling the built-in UI
  selector does not create a 4:3 viewport inside a widescreen framebuffer.
- Raw split APK sets must be merged into one installable APK before patching.
- The rebuilt APK cannot retain the original developer signature.

## Signing and installation

By default, the shared patcher generates or reuses a private PKCS12 signing
identity in the current user's operating-system data directory. No private
signing key or password is included in this repository.

Android cannot install the result as an update over a copy signed with a
different key. Back up any saves you care about before uninstalling an
existing installation; uninstalling can erase private app data. Once the
signature situation is understood, install the generated APK with:

```sh
adb install "output/Grimvalor-v1.2.13-4x3.apk"
```
