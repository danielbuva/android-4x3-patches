# Skate 3 Mobile

- Package: `chat.buku.skate3`
- Tested port: Buku313 2.1.0 (version code 20100), ARM64
- Engine: native renderer / rexglue static Xbox 360 recompilation
- Status: experimental; opening gameplay and menus inspected at 1280×960,
  complete career and long-session testing pending

## Changes

The port already has a 4:3 output mode, but its original aspect correction
reduces horizontal coverage. This patch selects that output and changes the
camera correction to preserve the original horizontal view while revealing
more above and below. It does not stretch the image or zoom into a 16:9 frame.

- Scale the projection and combined view/projection Y columns by 3/4, including
  the inlined frame-building path. X, depth, and perspective-divide columns stay
  unchanged. At 4:3 this shows 4/3 of the original vertical extent, adding 1/6
  of the old height on each side.
- Adapt the port's existing cached guest visibility-plane expansion to the top
  and bottom planes with the same 3/4 factor. Retain its native-renderer gate,
  zero-pointer guard, finite-plane checks, normalization, and repeat protection.
  The left/right and near/far planes stay unchanged.
- Fit authored menus proportionally across the full screen width. Keep HUD
  elements at that same readable size, but anchor top/bottom gameplay groups
  to the taller screen's perimeter. On a 1280×960 display the groups move
  120 pixels outward, preserving their original edge margins; middle groups
  stay centered. Use the port's HUD draw flag and transformed vertical bounds
  and the render-thread frontend state to exclude menus, video, and perspective
  draws from this translation. Connected artwork, portrait tiles, effects, and
  text move as one group, avoiding split Coach Frank portraits and tutorial
  panels. The classifier reads the immutable render-frame snapshot.
- Correct the 2D transform's Y row and remove the old horizontal edge snap
  constraint. Native photo capture preserves the full horizontal view and
  selects the central 16:9 vertical region for the game's 16:9 photo raster.
- Detach the Android `TouchControllerView`, including its persistent top-center
  **TOUCH/HIDE** button. The original control-visibility preference hides only
  the controls, not this button. Use a physical controller with this patch.

- Place the native character/team name-entry dialog at one eighth of the display
  height, centered horizontally, so Android's keyboard does not cover the field.
- Give the **EA startup movie only** a proportional center crop to fill 4:3.
  The port's existing first-boot-movie lifecycle disables this correction after
  that intro ends or is skipped; later career and windowed movies retain their
  original presentation. Increase the existing four-second recovery timeout to
  one minute so the full intro can play; keep manual skipping and stuck-movie
  recovery. Existing explicit timer settings still take precedence.
- Extend full-canvas dark backdrops, solid transition fades, and complete tiled
  grain layers to the full screen. Small black panels remain panels.
- Enlarge the difficulty/camera startup dialogs and their preview videos by
  50% together. Anchor the title logo, prompt, and glow effects near the top,
  and loading spinner near the bottom. Keep intentionally off-canvas prompts
  outside the expanded view without removing their actions.
- Keep 4:3 output when the native settings screen reapplies its preferences.
- Reserve the port's global movie-skip shortcut for Start, so confirming a
  camera choice with A does not also interrupt its preview movies.

The stock title background and its highlights use proportional cover cropping.
The optional artwork workflow below supplies extra image content instead.
Other pre-rendered videos retain their proportions and can remain letterboxed. They cannot gain additional scene content. The Android
launcher uses its existing responsive layout. This patch does not redesign
every individual game screen or change text sizes independently.

## Build

Supply your own APK and game data. No APK, ISO, game asset, or signing key is
included in this repository.

```sh
./patch.sh --allow-experimental --check "/path/to/Skate3-mobile.apk"
./patch.sh --allow-experimental "/path/to/Skate3-mobile.apk"
```

Output: `output/Skate3-Mobile-4x3.apk`. Windows users can use `patch.ps1` or
`patch.bat` with the same arguments. The patch does not modify the ISO or require
an ISO on the patching computer.

To build and install on a connected device's adopted SD card:

```sh
./patch.sh --allow-experimental --install-adopted "/path/to/Skate3-mobile.apk"
```

The card must already be adopted **and primary shared storage**. Add
`--device SERIAL` if needed. This verifies the APK/private data volume and
primary shared-storage selection. Skate 3's standard private paths hold saves,
settings, and caches; its external app directory holds extracted game files.
Both therefore use the adopted volume. Android itself can still retain small
system-managed records internally. No device-specific path is embedded in the
patch. See [installation details](../../README.md#optional-adopted-sd-storage).

The rebuilt APK has a different signing certificate from the developer APK.
Back up saves before replacing that installation. The optional installer never
uninstalls it for you. Preserve extracted game files outside the app's
`Android/data` directory before uninstalling if you want to reuse them; Android
can delete that directory during uninstall. The original ISO can be imported
again through the launcher.

## Optional custom 4:3 backgrounds

The APK patch works with the original game assets. To use your own seamless
4:3 artwork for the title and startup menus, the separate packer creates a copy
of `data/big/fedynamic.big`. It replaces only the background textures in four
named frontend resources; interactive UI and unrelated archive members stay
intact. The title image must contain only the scene, without the logo or prompt.
Use an outpaint that retains the original central scene so animated highlights
still line up. Both input images must be landscape 4:3.

```sh
python -m pip install 'Pillow>=12'
python games/skate-3/backgrounds.py \
  --archive "/path/to/original/fedynamic.big" \
  --title "/path/to/title-4x3.png" --menu "/path/to/menu-4x3.png" \
  --output "/path/to/custom/fedynamic.big"
```

Back up the original archive **outside the app directory**, stop the game, and
copy the new archive to the extracted game's `data/big/fedynamic.big`. Preserve
the original backup for restoration. The packer refuses to overwrite an existing
output. No original or generated game artwork is distributed by this repository.
This optional step changes the extracted archive, never the ISO or APK.

## Compatibility and verification

Both native libraries must be little-endian ARM64 ELFs with every required
instruction sequence uniquely recognizable in executable code. Exported
function ranges constrain the camera and culling targets. No fixed file offset,
APK filename, version number, certificate, or whole-file hash decides
compatibility. Unknown variants and additional unaudited ABIs are refused.

Small position-independent hooks add one read/execute segment per library by
reusing a unique optional ELF note descriptor. The note bytes remain mapped;
existing code/data/BSS and non-executable stack permissions stay in place. The
keyboard hook resolves exported dialog/ImGui functions. The display hook resolves
its UI instruction context, first-movie flags, and render-thread menu state
from guarded loads and branches. The timer default is resolved through its
exported storage accessor. Each hook retains enough metadata to reconstruct and verify
its exact post-state, including instructions and linked destinations.

`display_hook.S` and `overlay_classifier.c` are original patch code. Their
precompiled instructions are recorded in `display-hook.json`; normal patching
needs no compiler. Maintainers can regenerate it with LLVM using
`python games/skate-3/build_display_hook.py --llvm-bin /path/to/llvm/bin`.
The classifier checks transformed corners, texture layout, frontend state, and
bounded groups of neighboring draws. Tiled layers must cover the full authored
canvas. Invalid geometry and oversized snapshots fall back to proportional UI.

The touch edit resolves the exact activity, `onCreate(Bundle)` method, and
`ViewGroup.addView`/`LayoutParams` method and touch-view field identities from DEX metadata, then
requires the recognized final attachment sequence. Method indices and offsets
are discovered. DEX checksums are regenerated. Both original and patched states
are recognized, including partially patched inputs, and all replacements are
re-probed before the signed APK is published.

Synthetic tests cover target relocation, ambiguity, changed instructions,
wrong architecture, DEX method identity, original/patched states, idempotence,
and actual matrix instruction behavior. Development also executed the patched
native culling instructions against synthetic planes: only top/bottom widened,
and repeating the operation did not compound the scale. Clean-to-patched
reproduction, signing, and physical-device checks are recorded in
[VERIFICATION.md](../../VERIFICATION.md).

## Source references

The native and Android behavior was traced against the public
[Buku313/Skate3-Mobile source](https://github.com/Buku313/Skate3-Mobile/tree/fbf94a50d2d4c6bbf669cd6f518fd2628658414c),
particularly `skate3_native_scene.cpp`, `skate3_native_scene_gpu.cpp`,
`skate3_ultrawide_guest.h`, `skate3_demo_path.cpp`, `Skate3Activity.java`, and
`TouchControllerView.java`. Native keyboard behavior was traced in the port's
[rexglue SDK](https://github.com/Buku313/rexglue-skate3-android/tree/edd4344723ecac3ffa18c5dcd2fcc268f468ff9e),
`src/kernel/xam/xam_ui.cpp` and ImGui's window-position API.
This patch is an independent community modification of that Android port.
