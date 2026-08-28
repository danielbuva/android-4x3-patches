# Dusklight

- Package: `dev.twilitrealm.dusk`
- Engine: native SDL/Aurora
- Tested build: `1.4.1` (version code `10401000`)
- Status: experimental; visual verification is still pending

## Changes

This module enables Dusklight's own proportional 4:3 presentation path by
updating three top-level values in the configuration stored inside
`assets/data1`:

- `video.lockAspectRatio` is set to `true`, selecting Aurora's aspect-fit
  viewport;
- `game.menuScalingMode` is set to `0`, selecting the original GameCube menu
  scale instead of the added widescreen mode; and
- `game.disableCutscenePillarboxing` is set to the audited value `false`.

The transformation applies to the shared game presentation path rather than
stretching or squashing the final image. It does not replace game content or
patch the emulator runtime.

Some third-party builds name an embedded, user-supplied disc image and its
configured path with a source-specific suffix. When that exact entry/path pair
is recognized, the patcher removes only the suffix from the entry name and
updates the matching path in the configuration. The image payload is copied
unchanged. A clean name, a different name, or an unfamiliar layout is left
alone and does not block the 4:3 patch.

## Usage

Dusklight is currently experimental, so it requires an explicit opt-in:

```sh
./patch.sh --allow-experimental "/path/to/Dusklight.apk"
```

The default output name is `Dusklight-v1.4.1-4x3.apk`.

## Compatibility

Compatibility is determined semantically from the package name, the nested
archive at `assets/data1`, and the three required configuration keys and value
types.
Version, signature, filename, APK source, unrelated archive entries, unrelated
configuration values, and whole-file hashes are not compatibility gates.

Missing required keys can be added and recognized original values can be
updated in place. Already-patched values are accepted. Duplicate required keys,
invalid JSON, incompatible value types, or a malformed nested archive are
refused rather than guessed at. Unrelated configuration text and nested entries
are preserved while the archive is rebuilt.

The tested build contains source-named JNI libraries that are required for
startup and data extraction. The shared cleanup framework recognizes and
preserves that launch-critical set. Their presence, absence, or names do not
decide whether the semantic 4:3 configuration itself is compatible.

## Known limitations

- The result still needs complete visual review of gameplay, menus, and
  cutscenes on a physical 4:3 device.
- Rebuilding the large nested archive requires substantial temporary free
  space and can take longer than most modules.
- The original developer signature cannot be retained after rebuilding.
