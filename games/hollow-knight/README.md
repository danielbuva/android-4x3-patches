# Hollow Knight

- Package: `com.TeamCherry.HollowKnight`
- Engine: Unity IL2CPP
- Tested build: `1.5.78.11833`
- Status: verified

This patch changes the forced viewport from 16:9 to 4:3 while retaining the
original horizontal span. The existing camera projection therefore reveals
additional world above and below instead of cropping, stretching, or
squashing it. It also expands the vertical room-bound allowance, resizes and
repositions the HUD, and re-anchors the upper touch buttons to the new top
edge.

## Compatibility

The tested version is informational. Compatibility is determined from the
Unity hierarchy, the original or patched component values, and unique groups
of native camera constants in each bundled architecture. Package version,
APK signature, filename, and whole-APK hash are not compatibility gates.

The patch accepts an already-patched input. It stops without guessing if a
required object is missing, duplicated, or has an unrecognized value. The
ARMv7 camera-bound literals are located as a contextual cluster rather than
by the fixed offsets used by the original development script.

The APK may contain ARM64, ARMv7, or both. At least one of those supported
IL2CPP libraries must be present. Every supported library that is present is
independently inspected and patched; an APK is rejected if any present
supported ABI has missing, duplicated, ambiguous, or unrecognized targets. Other
architectures are left untouched.

Source-specific branding cleanup is intentionally not a required part of
this game module. A clean or differently sourced APK can receive the 4:3
patch without containing those optional additions.
