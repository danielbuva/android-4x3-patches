# Hollow Knight: Silksong

- Package: `com.game.silksong`
- Engine: Unity IL2CPP (AArch64)
- Tested build: `1.2.0` (version code `8`)

## Changes

The camera's narrow-screen limit is changed from 16:10 to 4:3. The existing
camera code then uses the full viewport, keeps the original horizontal view,
and exposes additional world above and below. It does not crop, stretch, or
squash gameplay.

When the tested launcher scene is present, its loading label is moved to the
new bottom edge. If that required UI rewrite is already happening, a uniquely
recognized port watermark canvas may be hidden opportunistically. Branding is
never reported, never affects compatibility, and never causes a rewrite by
itself.

## Compatibility

Compatibility is decided from the package name, required APK entries, a unique
contextual AArch64 instruction sequence, and semantic Unity scene objects. APK
version, signature, source, and whole-file hashes are not compatibility gates.
The patcher accepts both original and already-patched target states and refuses
to guess if the required native target is missing or ambiguous.

Only the AArch64 IL2CPP library is currently supported. Other CPU
architectures fail safely.
