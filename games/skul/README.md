# Skul: The Hero Slayer

- Package: `com.playdigious.skul`
- Engine: Unity IL2CPP
- Tested build: `1.0.13 (66)`
- Status: verified

The patch changes the GameBase scene's pixel-perfect gameplay reference from
640×360 to 640×480. This retains its horizontal view while adding vertical
area. The gameplay canvas reference and its safe-content rectangle are
expanded from 1920×1080 to 1920×1440 so top- and bottom-anchored HUD elements
follow the true 4:3 edges.

## Compatibility

The patcher locates the `Main Camera`, `UI Canvas`, and `Inside Of Letterbox`
objects by semantic name and verifies the surrounding component policies and
field values. It does not depend on their Unity PathIDs, the APK signature,
the package version, or a whole-APK hash. An already-patched bundle is
recognized without being rewritten.

If any required object is missing, duplicated, or contains an unrecognized
layout, patching stops before rebuilding the APK. Source-specific branding is
not a required target and cannot block this 4:3 transformation.
