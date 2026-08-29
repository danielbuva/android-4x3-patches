# Advent Neon

- Package: `com.CryoGX.adventneonunofficialandroidportbyplayer1444`
- Engine: GameMaker Studio 2 VM (Undertale bytecode 17)
- Tested build: `1.0.0` (version code `1000000`)
- Status: experimental; structural verification complete, visual verification pending

This patch converts the game's 1280x720 presentation to a centered 1280x960
view. The horizontal span and scale are retained while 120 world pixels are
added above and below; gameplay is not stretched, squashed, or cropped to
simulate 4:3.

## Changes

- Expands the enabled room views and camera ports to 1280x960 and moves their
  origins from `y = 0` to `y = -120`.
- Updates camera creation and tracking, GUI-coordinate conversion, pause/freeze
  captures, video reset, and the final shader compositor for the taller frame.
- Expands the splash, cutscene, dialogue, objective, boss-introduction,
  transition, training, stage-stat, and stage-clear layouts.
- Moves mobile controls and presentation effects into the 4:3 GUI area.
- Hides the port's always-visible drawn touch-control overlay without removing
  controller or touch-input handling.
- Moves the **Press Any Key** title prompt 60 pixels lower in the 960-pixel
  frame.

Optional third-party-source branding cleanup is handled by the shared
framework. Branding is not required for compatibility, and an official or
differently sourced APK can be patched without containing it.

## Usage

Install the repository prerequisites first, including UndertaleModTool CLI
0.9.1.2 or newer. This module was developed with 0.9.2.0. Put
`UndertaleModCli` on your command path or set `ANDROID_4X3_UMT` to the CLI
executable.

Check the APK without creating an output:

```sh
./patch.sh --check --allow-experimental "/path/to/Advent-Neon-v1.0.0.apk"
```

Create, align, sign, and verify the patched APK:

```sh
./patch.sh --allow-experimental "/path/to/Advent-Neon-v1.0.0.apk"
```

The default output name is `Advent-Neon-4x3.apk`. See the
[step-by-step guide](../../PATCHING_GUIDE.md) for Windows commands,
installation, and troubleshooting.

## Compatibility and safety checks

The APK version and whole-APK hash are informational rather than compatibility
gates. After checking the Android package and required `assets/game.droid`
entry, the module asks UndertaleModTool to require:

- the expected GameMaker project identity and bytecode version;
- the expected room and enabled-view structure;
- every named object, script, and event used by the transformation; and
- one exact original or patched occurrence of every guarded source fragment.

The patch is accepted only when all required targets form one coherent
original or already-patched state. Missing, changed, duplicated, or ambiguous
targets are refused instead of being patched by guesswork. Every scripted
mutation has a matching named postcondition, and the rebuilt
GameMaker archive is reopened and checked before APK output continues.

## Signing

Rebuilding invalidates the developer signature. By default, the patcher
generates and reuses a private local signing identity outside the repository,
then verifies the final APK's alignment and signature. Android may require an
installed copy signed by a different key to be removed before installation;
back up any saves you care about first.

## Verification status and limitations

The proprietary-free tests verify the project guards, original and patched
room geometry, all named mutation postconditions, and patch-script hygiene.
Development outputs have also passed structural patched-state recognition.
Complete intro, menu, room, and gameplay inspection on a physical device is
still pending, so `--allow-experimental` is required.

- Previously unauthored vertical world or background space may be exposed in
  individual rooms.
- Particles, cinematics, or encounter framing may need game-specific follow-up
  after visual testing.
- The visual touch-control overlay is intentionally hidden. This does not add
  new controller mappings or redesign touch-input regions.
