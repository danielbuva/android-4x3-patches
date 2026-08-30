# Hollow Knight

- Package: `com.TeamCherry.HollowKnight`
- Engine: Unity IL2CPP or Unity Mono, selected from APK structure
- Tested builds: IL2CPP port revision `1.5.78.11833`; Mono port `1.3.0.0`
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

## Port-specific implementations

The two tested ports share the Android package name but are not binary
revisions of one implementation. The patcher selects between them from their
runtime files; the filename and displayed version are not used as selectors.

- The IL2CPP port stores camera behavior in `libil2cpp.so`. Its patch uses the
  Unity HUD/touch hierarchy plus unique contextual native constant groups.
- The 1.3.0.0 Mono port stores camera behavior in `Assembly-CSharp.dll` and
  packages its Unity scenes into one large `data.unity3d` bundle. Its patch
  resolves named managed types and methods, changes only their recognized CIL
  operands, forces the full viewport, expands every associated vertical
  camera-bound calculation, fits the disclaimer text, changes both the
  serialized and runtime UI reference from 1920×1080 to 1920×1440, repositions
  the gameplay HUD at the physical top edge, and moves utility touch controls
  to the real top edge. Its dedicated HUD camera is widened enough to contain
  the complete 16:9 inventory composition; the gameplay HUD is compensatingly
  scaled so health and soul retain their intended physical size. Because the
  port restores the inventory hierarchy when the menu opens, a semantic CIL
  hook uniformly fits and centers that hierarchy after the reset. This keeps
  every inventory page, border, cursor, and transition in the same coordinate
  system without horizontal stretching.

For the Mono port, the original already uses Unity's expanding canvas mode and
a full-screen gameplay surface. That alone is not the finished 4:3 result: its
camera limits and auxiliary aspect handlers remain 16:9, and its HUD is visibly
clipped. The Mono patch preserves the existing horizontal game span, exposes
the additional vertical area consistently, and corrects those UI assumptions.
Earlier public Mono patches expanded the HUD camera but retained the original
inset, and one intermediate release enlarged the HUD without fitting the
inventory. Current releases recognize and migrate each of those states. The
migration also patches the unique PlayMaker `Come In` scale action that
otherwise restores the gameplay HUD after scene load.

This Mono port extracts bundled Unity data into app-specific storage on first
run. Android's replace-install can preserve that older extracted copy when an
APK with the same version is installed over it. On at least one tested device,
ordinary uninstall also left the package's external `Android/data` and
`Android/obb` directories behind. Back up any wanted saves, use Android's app
info screen to **clear storage while the app is still installed**, then
uninstall it before testing a newly patched revision. A genuinely clean install
ensures the revised HUD and inventory assets are loaded.

Because the Mono APK is large, extraction and its single structure-preserving
Unity bundle rewrite can take several minutes and temporarily require multiple
gigabytes of free disk space. This is expected; do not interrupt the patcher
while it is rebuilding.

An IL2CPP APK may contain ARM64, ARMv7, or both. At least one of those supported
IL2CPP libraries must be present. Every supported library that is present is
independently inspected and patched; an APK is rejected if any present
supported ABI has missing, duplicated, ambiguous, or unrecognized targets.
Other architectures are left untouched. A Mono APK must instead contain the
recognized managed methods and Unity objects. An input that unexpectedly
contains both runtime forms is rejected as ambiguous rather than guessed.

Source-specific branding cleanup is intentionally not a required part of
this game module. A clean or differently sourced APK can receive the 4:3
patch without containing those optional additions.
