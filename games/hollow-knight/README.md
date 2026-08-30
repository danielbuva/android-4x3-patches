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
  operands, removes the hidden overscan crop, expands every associated vertical
  camera-bound calculation, and changes the serialized world camera from
  1920×1080 to 1920×1440 with a guarded 0.75 zoom factor. That combination
  preserves the original horizontal world span while revealing the additional
  top and bottom area. The patch also fits the disclaimer text, changes the
  runtime UI reference to 1920×1440, places the health HUD at the physical
  top-left edge, and moves utility touch controls to the real top edge. Because
  the port restores the inventory hierarchy when the menu opens, a semantic CIL
  hook restores its uniform scale and centered position after that reset. Its
  translucent backdrop is enlarged separately to cover the complete 4:3 frame.
  Every inventory page, border, cursor, and transition therefore remains in one
  coordinate system without horizontal or vertical stretching.

For the Mono port, the original already uses Unity's expanding canvas mode and
a full-screen gameplay surface. That alone is not the finished 4:3 result: its
camera limits and auxiliary aspect handlers remain 16:9, and its HUD is visibly
clipped. The Mono patch preserves the existing horizontal game span, exposes
the additional vertical area consistently, and corrects those UI assumptions.
Earlier public Mono patches expanded the HUD camera but retained the original
inset, and intermediate releases compensated for the cropped world projection
by shrinking or moving the HUD and inventory. Current releases recognize and
migrate those states to the true 4:3 camera, stable health-HUD position,
centered inventory, and full-frame backdrop. The migration also recognizes the
unique PlayMaker `Come In` scale action used when the gameplay HUD returns.

This Mono port may extract bundled Unity data into app-specific storage. A
replace-install worked in place on the primary test device, but a port build or
Android version that retains an older extracted copy can make a new patch look
unchanged. If that happens, back up any wanted saves, use Android's app-info
screen to **clear storage while the app is still installed**, then uninstall
and install the newly patched APK. On some devices, uninstall alone can leave
external `Android/data` or `Android/obb` files behind.

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
