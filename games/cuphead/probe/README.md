# Cuphead experimental display modes (ARM64)

This opt-in patch adds three mutually exclusive checkboxes to **Settings → Video**:

| Choice | Gameplay stages | Overworld | UI area |
|---|---|---|---|
| 16:9 Original | Original framing with borders on a 4:3 screen | Original framing | Original 16:9 |
| 4:3 Expanded | Original horizontal coverage, additional vertical coverage | Expanded 4:3 | Full 4:3 |
| 4:3 Cropped | Original vertical coverage, cropped sides | **Same expanded map as Expanded** | **Same full 4:3 UI** |

Expanded is the default. Confirm a checkbox with the controller or tap its row;
only one can be selected. The choice is saved using a separate PlayerPrefs key
and takes effect immediately. Existing video options and Back remain available.
The Video card and text are enlarged proportionally for handheld readability.
The UI camera and CanvasScaler use the full display area in both 4:3 modes, so
anchored HUD, menu dimming and touch coordinates share the same viewport.

**Experimental: updated assets are still needed for a complete 4:3 presentation.**
Expanded view can expose artwork edges. A separate decorative camera in Forest
Follies crops selected background layers proportionally, but seams remain and
other scenery is not repaired. Cropped mode deliberately removes horizontal
stage visibility; use Expanded when preserving the original field of view is
important. Collision geometry, stored gameplay zoom and logical bounds are not
changed. Fixed-aspect illustrations and story scenes are not certified as 4:3.
ARMv7 remains unchanged. Do not distribute the generated APK.

## Apply on macOS or Windows

Install the repository's Python dependencies, Java and Android SDK Build Tools
as described in the root README. From the repository root:

```sh
python games/cuphead/probe/probe.py --check Cuphead.apk
python games/cuphead/probe/probe.py Cuphead.apk --output Cuphead-4x3-experimental.apk
```

Use `python3` on macOS if necessary. Output must not already exist. Supply your
own original **Cuphead 1.0.2, version code 4** APK. The source checksum and engine
revision are in the [investigation record](../README.md). Compatibility is
verified separately against the ARM64 library, metadata and Forest Follies
scene hashes; filenames, package versions or signatures alone do not establish
compatibility. Unknown inputs and older camera-only experiments are rejected;
start from the supported original APK. Applying this exact revision again is
recognized. No files are written by `--check`.

Repacking, alignment and local signing use the shared repository tools. The
script does not install anything or control a device. Cuphead remains outside
the normal game registry: the opt-in command above is required. There is no
commercial APK, extracted asset or signing key in this patch.

## Mechanism and limitations

The shared `AbstractCupheadCamera.LateUpdate` hook invokes original viewport
calculation first. Level and map projections are reset each frame, then changed
according to the selected mode. Expanded retains `m00` and computes
`m11 = m00 * screenWidth / screenHeight`. Cropped retains `m11` and computes
`m00 = m11 * screenHeight / screenWidth`, **only for level cameras with a live
gameplay Level**. Other scenes keep their original framing in Cropped mode. Original
retains the game's viewport and projection. Gameplay orthographic size, zoom,
camera movement and logical bounds retain the source behavior. Screen effects
and special camera consumers still require broader testing.

The UI camera uses its own full-screen orthographic projection in 4:3 modes.
The common canvas-reference update is adjusted at its call site so camera
updates cannot restore a 16:9 safe area. Original mode restores the original
UI area. The menu hook adds ordinary managed menu entries and uses the existing
controller selection/color logic. Touch selection tests the rendered text's
RectTransform against its actual canvas camera.

`scene.py` moves exactly 48 decorative leaf objects to an unused render layer
in the hash-guarded Forest Follies scene. Only those GameObject layer fields
change; every other serialized object and every transform is checked. Objects
with collision components, children, or scrolling-copy behavior are excluded.
A second camera renders that layer with original vertical coverage and cropped
sides. Original mode disables the second camera and restores the original
culling mask. This improves some backgrounds, not all scene artwork.

The patch logs geometry periodically under `CUPHEAD4X3`, and menu changes under
`CUPHEAD_VIDEO`. It has no stage-jump helpers or save-data edits. The former
`camera-baseline` and `background-baseline` development files are no longer used.

## Source and rebuilding

`payload.hex` contains only newly authored native patch code and strings. Its
complete sources are `camera_probe.c`, `video_menu.c`, `ui.h`, `trampolines.S`
and `probe.ld`. `hooks.json` records hash-guarded native hook sites, original
instruction guards and their targets. A separate read/execute ELF segment uses
the optional note-header slot; existing load segments and addresses are retained.
No runtime compiler is needed to apply the checked payload. The reviewed payload
is 5,151 bytes, SHA-256
`cef1edc4064dae578205366b30b49188ede7aeb397d184572cdbdb67c533fd89`.

Compiled with Apple clang 21 and LLVM lld:

```sh
clang -target aarch64-linux-android -O2 -fno-builtin -fno-stack-protector -fPIC -ffreestanding -fno-unwind-tables -fno-asynchronous-unwind-tables -c camera_probe.c -o camera_probe.o
clang -target aarch64-linux-android -O2 -fno-builtin -fno-stack-protector -fPIC -ffreestanding -fno-unwind-tables -fno-asynchronous-unwind-tables -c video_menu.c -o video_menu.o
clang -target aarch64-linux-android -c trampolines.S -o trampolines.o
ld.lld -T probe.ld camera_probe.o video_menu.o trampolines.o -o probe.elf
llvm-objcopy --dump-section .probe=probe.bin probe.elf
```

Compiler changes require renewed review and verification, not just a changed
checksum. `probe.py` checks the payload and final native-entry hashes.

## Verification scope

The commercial APK was rebuilt, aligned, signed and archive-checked on macOS.
ARM64 handheld checks observed all three camera modes, switching in the Video
menu, full-screen HUD/dimming, and the expanded map in both 4:3 modes. Tests use
synthetic ELF fixtures and verify incompatible input rejection and unchanged
load segments. Repository CI covers macOS and Windows; commercial APK rebuilding
on Windows, ARMv7 runtime behavior, every touch gesture, other languages, all
boss phases, plane stages and all story/overlay scenes remain untested.
