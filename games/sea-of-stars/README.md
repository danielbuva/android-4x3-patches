# Sea of Stars

- Package: `com.playdigious.seaofstars`
- Engine: Unity IL2CPP
- Tested build: Android `3.0.60158` (`60158`), `arm64-v8a`
- Status: verified on the tested build

## Changes

The patch changes the game and UI resolution controllers from a 16:9 minimum
to 4:3, then changes the shared gameplay output from 640x360 to 640x480. The
horizontal world view and pixel scale are retained, with additional world area
shown above and below. It also applies the narrowly scoped SurfaceView startup
repair when that helper is present and recognized.

Source-specific startup branding is not part of compatibility detection. The
shared cleanup pass removes a recognized instance when possible and otherwise
continues silently.

## Compatibility

The tested version is a reference, not a version lock. Bundle names, APK
signatures, APK hashes, version names, and version codes are not compatibility
requirements. The patcher searches Addressables bundles for the expected
`MobileResolutionManager`, `UIResolutionController`, and
`GameResolutionController` object structures and requires a unique native
instruction target. The gameplay controller target is the one Addressables
cohort containing six distinct serialized scenes with one `RpgCamera`
controller each; isolated controller prefabs elsewhere are not part of the live
resolution path. A second matching cohort is ambiguous. Unknown or ambiguous
core structures are left untouched.

For the tested build, the repository records the known bundle filenames as a
performance hint so the usual check extracts only the relevant entries. Those
hash-like filenames are accepted as tested-entry locators only when their
semantic targets also match. If they are absent or incomplete, discovery falls
back to the configured Addressables scan and global ambiguity checks.

The native gameplay patch currently supports the tested 64-bit ARM code shape.
A build whose compiler emits a different instruction sequence will be reported
as unsupported rather than patched at a guessed offset.

## Known limitations

- A raw split-APK set must be merged before patching.
- Other CPU architectures need their own audited native instruction pattern.
- The original developer signature cannot be retained after rebuilding.
