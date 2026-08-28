# AM2R

- Package: `com.lojical.AM2R`
- Engine: GameMaker Studio YYC
- Tested build: `1.5.2` (version code `1005012`)
- Status: experimental; structural verification complete, visual verification pending

AM2R already contains a native 320x240 rendering path. The tested Android
build normally enables a compiled 426x240 widescreen expansion; this patch
keeps that option off so intros, menus, and gameplay use the game's true 4:3
path without stretching or cropping.

## Changes

- Forces the saved `Widescreen` setting to load as false.
- Prevents the display-menu toggle from enabling the 426x240 path again.
- Applies the equivalent guarded edit to every supported `libyoyo.so` ABI
  included in the supplied APK.

The module does not remove billing, saves, controllers, online services, or
other unrelated game behavior.

## Usage

Check the APK without creating an output:

```sh
./patch.sh --check --allow-experimental "/path/to/AM2R-v1-5-2.apk"
```

Create, align, sign, and verify the patched APK:

```sh
./patch.sh --allow-experimental "/path/to/AM2R-v1-5-2.apk"
```

The default output name is `AM2R-v1-5-2-4x3.apk`. See the
[step-by-step guide](../../PATCHING_GUIDE.md) for Windows commands,
installation, and troubleshooting.

## Compatibility and safety checks

This module supports the audited `armeabi`, `armeabi-v7a`, `mips`, and `x86`
GameMaker libraries from AM2R 1.5.2. An APK may contain any nonempty subset of
those ABIs; every `lib/<abi>/libyoyo.so` that is present must be recognized and
is patched independently.

Because these targets are compiled YYC native code, this is deliberately an
exact-build patch rather than a loose byte search. Each present library must
match all of the following:

- its audited ABI, size, and complete original or patched SHA-256 identity;
- the expected 32-bit little-endian ELF type and machine;
- the expected file-offset-to-virtual-address mapping inside an executable
  load segment; and
- the exact original or patched instructions at every setting-load and menu
  target.

The whole APK, filename, signing certificate, and reported version are not
compatibility gates. However, a rebuilt or revised `libyoyo.so` needs a new
audit even if its visible version is still 1.5.2. Unknown ABIs, mixed hash and
instruction states, changed ELF mappings, and missing targets fail safely.
Already-patched recognized libraries are accepted without another rewrite.

## Signing

Rebuilding invalidates the developer signature. By default, the patcher
generates and reuses a private local signing identity outside the repository,
then verifies the final APK's alignment and signature. Android may require an
installed copy signed by a different key to be removed before installation;
back up any saves you care about first.

## Verification status and limitations

Proprietary-free tests cover ABI-subset discovery, original-to-patched
transformation, already-patched idempotence, ELF mapping validation, exact
hash/instruction agreement, and refusal of unknown native builds. Development
outputs have also passed structural patched-state recognition. Complete intro,
menu, and gameplay inspection on a physical device is still pending, so
`--allow-experimental` is required.

- Only the four audited 32-bit ABI implementations from the tested build are
  supported; an ARM64 or otherwise rebuilt GameMaker library is refused.
- This patch restores AM2R's existing 4:3 path. It does not redesign content
  that may independently assume widescreen placement.
