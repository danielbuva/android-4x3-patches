# Cuphead gameplay camera probe (ARM64 only)

This is an opt-in investigation, **not a finished 4:3 conversion**. Menus,
fixed artwork, HUD/touch layout, render effects and special scenes are not
certified. It is deliberately absent from the normal game registry. ARMv7
remains unchanged. Do not distribute the generated APK.

## Reproduce on macOS or Windows

Install the repository's Python dependencies, Java and Android SDK Build Tools
as described in the root README. From the repository root:

```sh
python games/cuphead/probe/probe.py --check Cuphead.apk
python games/cuphead/probe/probe.py Cuphead.apk --output Cuphead-camera-experiment.apk
```

Use `python3` on macOS if necessary. Output must not already exist. The script
checks the package, ARM64 library and IL2CPP metadata independently of APK
signatures, container layout and whole-APK checksum. Unknown revisions are
rejected before writing output. Already patched native entries are recognized.
Repacking, alignment and local signing use the repository's shared tools. No
installation or device interaction is performed by this script.

The tested source revision and APK checksum are in the parent investigation
record. The output retains the source manifest version. Only an ARM64 process
receives the camera experiment. Windows execution is covered by proprietary-free
CI tests; rebuilding this commercial APK on Windows has not been tested.

## Mechanism

The hook replaces the single forwarding branch in
`AbstractCupheadCamera.LateUpdate`. It first invokes the original `UpdateRect`,
then handles orthographic `CupheadLevelCamera` and `CupheadMapCamera` instances:

1. Reset the projection and obtain the game's current 16:9 projection.
2. Preserve `m00`, which fixes horizontal world coverage.
3. Set `m11 = m00 * screenWidth / screenHeight`.
4. Set the viewport rectangle to `(0, 0, 1, 1)` and apply that projection.

At 1280×960 this is visually equivalent to enlarging the ordinary orthographic
half-height by 4/3. The stored orthographic size, zoom, camera bounds and
controller movement code are unchanged. Running each `LateUpdate` handles
initialization and changing zoom without repeatedly multiplying an earlier
expanded projection. Projection consumers, render effects and scripted
camera paths still need a complete audit; unchanged logical bounds are not a
proof that every game behavior is unaffected.

For local A/B comparison, an empty file named `camera-baseline` in the app's
external `files` directory selects the original viewport/projection. Removing
it restores the experiment without restarting the scene. This is a development
switch, not a production feature. The probe logs geometry every 120 frames with
the `CUPHEAD4X3` prefix. It writes no save data and has no stage-jump helpers.

## Payload provenance and rebuilding

`payload.hex` contains **only the new probe's own compiled code and strings**,
not extracted game code. `camera_probe.c` and `probe.ld` are its complete sources.
Addresses are specific to the exact hash-guarded native entry. The optional ELF
note program-header slot becomes a separate read/execute load segment beyond
the existing BSS. Existing load segments and their addresses are preserved.

The checked payload was compiled with Apple clang 21.0.0 and LLVM lld:

```sh
clang -target aarch64-linux-android -O2 -fno-builtin -fno-stack-protector -fPIC -ffreestanding -fno-unwind-tables -fno-asynchronous-unwind-tables -c camera_probe.c -o camera_probe.o
ld.lld -T probe.ld camera_probe.o -o probe.elf
llvm-objcopy --dump-section .probe=probe.bin probe.elf
```

The `.probe` section is 986 bytes, SHA-256
`a838e9030ca9ed298a35a1daa30afc7fe63dea167a726b3cc5b90864bd6003cc`.
Other compiler versions may produce different code and need fresh review and
verification; simply changing the expected hash is not a compatibility fix.
No compiler is needed to apply the reviewed payload with Python.

## Optional Forest Follies artwork trial

`--fit-forest-background` additionally enlarges the opening meadow decoration
uniformly to 150%, allowing cropping of that decorative layer. Its upper edge
stays fixed and the layer extends downward to cover the newly visible strip.
Only one leaf object with exactly a Transform and SpriteRenderer is changed;
it has no children, collider or script. The camera position, gameplay terrain,
actors, sky, overworld and other scenes are untouched. The scene entry has
independent source/output hash guards and a unique named-object check.

This is a narrow artwork experiment, not a fit for every background or every
part of Forest Follies. Other finite layers and foreground artwork may still
show edges. Use only if background-only cropping is acceptable to you.
