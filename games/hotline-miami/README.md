# Hotline Miami

This module patches the GameMaker archive at `assets/game.droid`.

## Changes

- Expands ordinary gameplay cameras to 400 x 300 while retaining their
  centers; the special ending views together form the same 4:3 canvas.
- Changes the Android runner's presentation surface to 1440 x 1080 and uses
  the largest centered 4:3 viewport available on the display.
- Expands the mobile GUI from 341.5 x 192 to 341.5 x 256.125.
- Expands darkness and lighting surfaces to cover the added vertical view,
  including the tutorial particle range and wrap limits.

## Compatibility

The patcher identifies the package and then asks UndertaleModTool to verify the
named GameMaker project, bytecode format, special rooms, scripts, events, and
source fragments that are changed. The APK version and whole-file hash are
informational and do not decide compatibility.

The transformation was tested on version `1.0.180` (`1000180`) on a physical
1280 x 960 Android device. Minor revisions may also work when all structural
targets are unchanged.

UndertaleModCli `0.9.1.2` is the tested version. Set `ANDROID_4X3_UMT` to the
CLI executable if it is not available on `PATH`.

The two port-promotion objects present in the tested third-party build are
removed only when their complete resource and URL signatures are recognized.
Official APKs and builds without those objects remain compatible.
