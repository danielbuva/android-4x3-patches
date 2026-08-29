# Rogue Legacy

> [!IMPORTANT]
> This patch is experimental. Its targets and rebuilt APK are checked
> automatically, but a complete visual review of every screen and gameplay
> state is still pending. Use `--allow-experimental` to acknowledge that
> status; the flag does not bypass compatibility checks.

- Package: `com.roguelegacy.port`
- Engine: .NET 8 Android / MonoGame
- Tested build: `1.4.1-r2` (version code `1`)
- Tested APK architectures: ARM64 and ARMv7
- Output: `Rogue-Legacy-4x3.apk`

## What the patch changes

The port uses a 1320×720 virtual screen. This module keeps the full 1320-pixel
horizontal view and increases the virtual height to 990, producing a true 4:3
1320×990 game and touch-input space. The additional area is vertical; the game
is not stretched, squashed, or converted by cropping its sides.

The patch also updates the layouts that otherwise retain 720-pixel vertical
assumptions:

- BlitWorks and Cellar Door Games splash/logo placement
- title rendering, post-processing, fades, camera, selections, menus,
  copyright text, loading text, and touch-button anchors
- options-menu background centering with its relative slide distances preserved
- proportional map and teleporter rendering centered in the taller display
- pause-menu icon layout
- touch-coordinate conversion through the taller virtual screen
- an initial virtual-screen metrics refresh, so the 1320x990 dimensions reach
  the camera, viewport, overlay, and input systems before the first room is
  drawn instead of only after a later transition

Fixed 16:9 title artwork remains proportional rather than being distorted or
horizontally cropped. Such artwork does not gain newly drawn image content in
the added vertical area.

On the particular port variant used during development, the module can also
neutralize recognized porter credits, Telegram links/buttons, and the
first-run developer promotion. Those edits are optional and source-specific.
If the strings or code are absent or unfamiliar, they are left alone silently
and the 4:3 patch can still proceed. Shared APKVision cleanup follows the same
non-blocking rule.

## Usage

Check the APK before creating an output:

```sh
./patch.sh --check --allow-experimental "/path/to/Rogue-Legacy.apk"
```

Create the patched APK on macOS or Linux:

```sh
./patch.sh --allow-experimental "/path/to/Rogue-Legacy.apk"
```

On Windows:

```bat
patch.bat --allow-experimental "C:\path\to\Rogue-Legacy.apk"
```

The original APK is not overwritten. Unless `--output` is supplied, the
result is written under `output/` as `Rogue-Legacy-4x3.apk`.

## Compatibility and safety

The tested version is informational, not an exact-version requirement. The
patcher first verifies the Android package, then requires:

- `assemblies/assemblies.manifest`
- `assemblies/assemblies.blob` in the supported XABA v1 layout
- exactly one manifest mapping named `RogueLegacy.Android`
- an XALZ-compressed managed assembly that can be decoded and rebuilt
- one unambiguous instance of every required managed-code context
- each required instruction and user string to contain either its recognized
  original value or its already-patched value

The managed assembly is selected by name rather than a hard-coded descriptor
index. IL edits are located from invariant surrounding instructions rather
than APK offsets, file offsets, or a whole-file hash. Clean, mixed-state, and
already-patched inputs are supported when every required target remains
recognizable.

APK filename, source, version, signature, and whole-APK SHA-256 are not
compatibility gates. A compatible minor revision may work unchanged. If a
required context is missing, duplicated, or has an unknown value, the module
stops instead of guessing. Recompression must also fit in the original XABA
assembly allocation; an otherwise recognizable store with insufficient space
is refused safely.

## Signing and installation

Rebuilding an APK invalidates its developer signature. By default, the shared
patcher creates and reuses a random local PKCS12 signing identity outside this
repository. No private key is included here.

Android cannot install this result over a copy signed by a different key. Back
up saves before removing an existing installation, because uninstalling can
erase private game data. Keep the generated local key if you want future APKs
from this patcher to update earlier patched installs in place. You can instead
provide your own key using the shared patcher's signing options.

## Verification and limitations

The proprietary-free test suite verifies named XABA assembly resolution,
XALZ/LZ4 decode and read-back-safe repacking, original/patched/mixed states,
idempotence, unique-context enforcement, length-preserving managed edits, and
silent handling of absent or unfamiliar optional branding.

The audited `1.4.1-r2` structures are the basis for the production targets.
Full device-side visual verification across gameplay, title, options, pause,
transitions, and touch controls remains pending, so the module stays
experimental. Fixed 16:9 artwork is kept proportional and may not fill the
newly exposed vertical area with unique artwork.
