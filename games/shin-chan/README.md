# Shin Chan: Shiro & Coal Town

- Package: `com.crunchyroll.gv.shinchanshiroandcoal.game`
- Engine: Unity IL2CPP
- Tested build: Android `1.0.2` (`11`), `arm64-v8a`
- Status: verified on the tested build

## Changes

The gameplay patch disables the fixed 16:9 camera viewport and raises the
vertical field of view to retain the original horizontal view while showing
more above and below. Title and menu canvases use a 1920x1440 reference. The
16:9 title art and opening movies remain proportional and are center-cropped to
fill 4:3; neither is stretched.

Source-specific startup branding is not part of compatibility detection. The
shared cleanup pass removes a recognized instance when possible and otherwise
continues silently.

## Compatibility

The tested version is a reference, not a version lock. Bundle names, APK
signatures, APK hashes, version names, version codes, and Unity PathIDs are not
compatibility requirements. The patcher finds the relevant Addressables
bundles from component type, GameObject name, matching camera relationships,
and neighboring serialized values.

For the tested build, the repository records the four known bundle filenames
as a performance hint so the usual check extracts only the relevant entries.
Those hash-like filenames are accepted as tested-entry locators only when
their semantic targets also match. If they are absent or incomplete,
discovery falls back to the configured Addressables scan and global ambiguity
checks.

If any required layout or camera component is absent, already customized to an
unknown value, or ambiguous, the input is left untouched instead of applying a
best guess.

## Device workflow verification

On 2026-08-24, the complete patching workflow was repeated with a standalone
Android 1.0.2 (version code 11) APK whose informational SHA-256 fingerprint is
`39ca4588cd3467f387de9ceba4dda3fafc117b05696f4217900bd85087592668`.
The source passed a full CRC check, was recognized as original, patched,
aligned, signed, re-recognized as patched, installed on a physical 1280x960
device, and survived a cold launch.

The device stored this source under a hidden `.pending-` filename even though
the archive was complete. The filename was not used as evidence of
compatibility; full archive integrity and semantic target detection were.
Gameplay framing and visual UI review remain separate from this automated
build/install check.

## Known limitations

- Opening movies fill 4:3 by cropping their left and right edges.
- A raw split-APK set must be merged before patching.
- The original developer signature cannot be retained after rebuilding.
