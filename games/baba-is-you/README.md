# Baba Is You

> **Experimental:** this patch does not fully solve the presentation problem.
> On the tested 1280 x 960 device, the game remains shifted and part of the
> right edge is cropped. Do not expect a complete or production-quality 4:3
> result.

This module adapts the ARM64 Chowdren renderer to an 854 x 640 logical view. It
also lets the game framebuffer use the full drawable behind the touch controls,
clamps the Lua layout width to 854, and adjusts the horizontal camera origin.
It is based on the original Baba 4:3 patch, not the later menu, touch, or
diagnostic experiments.

## Usage

Experimental patches must be enabled explicitly:

```sh
./patch.sh --allow-experimental "/path/to/Baba-Is-You.apk"
```

The output name is `Baba-Is-You-experimental-4x3.apk`.

## Compatibility

- Package: `org.hempuli.baba`
- Tested build: 617.0 (version code 617)
- Required architecture: ARM64
- Required entry: `lib/arm64-v8a/libChowdren.so`

Compatibility is determined from unique native instruction contexts and their
recognized original or patched values. The version and complete-library hash
are not compatibility gates, so differently signed copies and compatible minor
revisions can still be considered. Unknown or ambiguous renderer code is
refused rather than patched at a guessed offset.

Optional third-party branding cleanup is handled by the shared framework. Its
presence or absence is not required by this module.

## Device workflow verification

On 2026-08-24, the complete experimental workflow was repeated with a
standalone 617.0 (version code 617) APK whose informational SHA-256 fingerprint
is `37e95bc195721f3458cc0146a9944a2c55a38c2c3ed41c4e33df4e9266e296af`.
The source passed a full CRC check, was recognized as original, patched with
`--allow-experimental`, aligned, signed, re-recognized as patched, installed on
a physical 1280x960 device, and survived a cold launch.

This confirms the patching, signing, installation, and startup path only. It
does not change the experimental visual status: the known right-edge shift and
crop still require manual review and remain expected limitations.

## Known limitations

- The view remains horizontally shifted and cropped at the right edge.
- Only the ARM64 library layout has a known safe transformation.
- The result has not incorporated any of the later experimental touch/menu
  selector changes.
