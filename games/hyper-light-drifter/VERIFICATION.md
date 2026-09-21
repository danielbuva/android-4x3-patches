# Verification checkpoint

Android 1.1.99 (1001099), ARM64. This is an experimental checkpoint with the
unfinished animation and scene work listed in [README.md](README.md).

## Performed on macOS

- Built original-aspect and 4:3 APKs from the documented user-supplied source.
- Verified ZIP integrity, APK signing, alignment, exact native/game-data output
  fingerprints, incompatible-input rejection and original-aspect-to-4:3 upgrade.
- Rebuilt the authored native sources with the documented toolchain and matched
  the shipped hexadecimal payload byte for byte; no relocations or writable
  sections remain.
- Ran the repository suite: **256 passed, 1 skipped**. The skip is the unrelated
  Regenesis native-tool test requiring GDRE Tools.

## Physical Android checks

The owner manually tested the gameplay camera, quit dialog, control-option
switching, movement/D-pad swap, right-stick gun activation, independent movement
and firing, cursor alignment and diagonal gun visibility. The final 4:3 native
library and room data match that confirmed build. Later diagnostic and backdrop
experiments are excluded.

The final original-aspect companion was installed and observed reaching its
title screen. This is a startup check, not a separate full-game playthrough.
Installation verification checks both package and private-data placement on
existing adopted storage, rather than relying on an installation preference.

## Platform and coverage limits

The repository's existing Mac/Windows workflow runs synthetic tests, real APK
signing/alignment tests and platform launchers without proprietary game inputs.
Windows execution with this game's source APK has not been performed locally.
The source APK and device captures are not part of CI or the public repository.

Touch-target geometry is implemented but broad touch testing, all weapon types,
languages, cinematics and late-game screens remain unverified. Known animation,
map/inventory-backdrop, hallucination and campfire issues remain open.
