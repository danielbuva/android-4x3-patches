# Blasphemous

- Package: `com.thegamekitchen.blasphemousmobile`
- Engine: Unity IL2CPP
- Tested build: `1.9.0 (38)`
- Status: verified

This patch changes the internal 640×360 rendering pipeline to 640×480. It
expands the vertical gameplay view without cropping, stretching, or squashing
the image, updates the gameplay and UI output quads, and keeps the original
tablet-mode threshold independent from the 4:3 game camera.

The taller UI canvas exposed the resting achievement banner at the top edge.
The patch moves that banner's parent by the exact 60-unit half-height increase,
so its hidden and shown animation positions work as they did at 16:9.

## Compatibility

The tested version is informational. Compatibility is determined by the
required Unity hierarchy, recognized original or patched component values, and
unique contextual ARM64 instruction sequences. APK filename, version, signing
certificate, source, and whole-APK hash are not compatibility gates.

Clean, partially patched, and already-patched inputs are recognized. The patch
stops without guessing if a required Unity object or native sequence is
missing, duplicated, or has an unknown state.

The current native transformation targets the ARM64 IL2CPP library. An APK
whose relevant IL2CPP code has changed can still be supported when its unique
instruction context remains the same; otherwise the module fails safely.

Third-party branding is not a compatibility requirement. Optional shared
cleanup may remove a recognized addition, while an official or differently
sourced APK proceeds without it.
