# Huntdown

- Package: `com.coffeestain.huntdown`
- Engine: Unity IL2CPP
- Tested build: `0.1` (version code `200040`, source build `b200040`), ARM64
- Status: experimental; visual review pending

Huntdown already contains a resolution-independent 4:3 renderer. This module
bypasses the optional `force169` override so the game can select its native
320x240 logical view on a 640x480 Android surface. It also changes story-video
presentation from letterboxing to a proportional vertical fit.

## Changes

- Bypasses the `force169` branches in both renderer initialization and view-size
  calculation, covering menus and gameplay.
- Uses the game's native 320x240 logical view on a 640x480 4:3 surface.
- Changes intro and story videos to a proportional vertical fit with a centered
  crop at the left and right edges; videos are not stretched.
- Disables three recognized analytics login/server-send coroutines when their
  complete native signatures are found uniquely.
- Neutralizes a recognized distributor-injected save extractor in
  `classes3.dex` and removes recognized injected player-preference/device data
  from `assets/data0`.

The native analytics targets, `classes3.dex`, and `assets/data0` cleanup are
opportunistic. Missing or unrecognized variants are preserved silently and do
not block the 4:3 renderer patch. Billing, purchases, cloud saves, platform
authentication, achievements, and Play Games are deliberately preserved.

## Usage

This patch is experimental and must be enabled explicitly:

```sh
./patch.sh --allow-experimental "/path/to/Huntdown-v0.1-b200040.apk"
```

The default output is `output/Huntdown-v0.1-b200040-4x3.apk`. Use `--check`
first to inspect the required renderer targets without building an APK.

## Compatibility

The package must be `com.coffeestain.huntdown`, and the required entry is the
ARM64 `libil2cpp.so`. The version, APK filename, signature, and whole-APK hash
are informational rather than compatibility locks.

For the core 4:3 transformation, the patcher requires:

- A valid 64-bit little-endian ARM64 ELF with the audited executable mapping.
- One unique complete instruction context for each of the two `force169`
  branches and the video-fit selector.
- Recognized original or patched instructions at the audited mapped
  locations.

Unrelated native bytes may differ, and a partially patched core is safely
finished. Missing, moved, duplicated, or changed renderer signatures fail
closed. Optional source cleanup follows a separate rule: only a uniquely
recognized analytics, DEX, or data target is changed; unknown data remains
byte-for-byte untouched.

This is looser than requiring the entire audited native library, but a rebuild
that relocates the guarded renderer methods still needs a new compatibility
profile.

## Verification

The module re-probes all required renderer targets after applying replacements.
Proprietary-free automated tests cover unique native signatures, unrelated-byte
tolerance, partial core completion, optional-entry absence, silent preservation
of unknown injected files, ambiguous optional-cleanup handling, DEX method and
instruction validation, DEX checksum repair, and separation of cleanup-only
and 4:3 builds.

The transformation is structurally verified for the tested build, but its
visual output has not yet been reviewed on the target device. Intro videos,
story videos, menus, touch UI, gameplay framing, and controller behavior still
need manual confirmation.

## Known limitations

- Only the audited ARM64 renderer shape is currently supported.
- The target Android surface must actually be 4:3 for the renderer to compute
  the intended 320x240 view and zero offsets.
- Intro and story videos fill 4:3 by cropping their left and right edges.
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
adb install "output/Huntdown-v0.1-b200040-4x3.apk"
```
