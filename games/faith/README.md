# FAITH: The Unholy Trinity

This module patches the GameMaker archive at `assets/game.droid`.

## Changes

- Replaces the decorative 1920 x 1080 composition with a centered 1440 x
  1080 game view.
- Uses the largest centered 4:3 viewport supported by the output display. Game
  geometry is neither stretched nor squashed.
- Adds a persistent **Touch Controls** option. The overlay is hidden by
  default, while touch input and physical controllers remain active.
- Moves legacy right-side touch-control coordinates into the 4:3 GUI area.

## Compatibility

The patcher identifies the package and then asks UndertaleModTool to verify the
named GameMaker project, bytecode format, scripts, objects, and exact source
fragments that are changed. The reported APK version and any development
fingerprints are informational only and are not compatibility gates.

The transformation was tested on version `1.0.0` (`1000000`) on a physical
1280 x 960 Android device. Minor revisions may also work when all structural
targets are unchanged.

UndertaleModCli `0.9.1.2` is the tested version. Set `ANDROID_4X3_UMT` to the
CLI executable if it is not available on `PATH`.

Third-party startup or watermark cleanup is optional. Its absence or an
unknown branding variant does not prevent this 4:3 patch.
