# Hyper Light Drifter

- Android **1.1.99 (1001099)**, package `com.abylight.HyperLightDrifter`.
- **ARM64 Android devices only.** The ARMv7 runtime is not patched or supported.
- Target: **1280×960, 4:3**.
- Experimental: opening gameplay and selected menus have been manually checked;
  this is not a full-game acceptance test.

## Changes

The gameplay camera keeps its 480-unit horizontal view and increases its height
from 270 to 360. This reveals additional vertical world content without stretching
sprites or removing horizontal content. Existing gameplay tracking is retained.

Menu panels and the shared quit, overwrite and erase confirmation layouts are
centered on the taller canvas. Pause-menu backgrounds and dimming overlays cover the
full display. The separate map/inventory backdrop still needs correction. Startup notice and logo rooms use the same proportional canvas,
with fixed backgrounds centered instead of stretched. The title illustration retains its original proportions and gains
centered, proportionally scaled upper and lower extension sprites already present
in the supplied game. Black areas that are part of that artwork remain black;
no generated replacement art is included.

Settings → Controls → **Controller Options** adds two saved choices:

- **Swap left stick / D-pad:** OFF by default; exchanges directional movement
  and menu-navigation inputs.
- **Aiming stick:** LEFT by default. RIGHT raises the gun while the right stick
  is deflected and uses it for aiming and firing direction; the normal fire button
  remains necessary. Movement stays available while aiming in this mode.

Press A to open/change, Up/Down to select and B to return. The added page also
has touch targets matching its visible rows. Options are saved separately from
normal game preferences. Existing saves are not rewritten by these options.

Startup retains developer/publisher branding, the autosave notice, initialization
and room transitions. Two timed waits are shortened from 167 to 90 base frames
(the developer screen applies its original multiplier). A development launch
reached the title in approximately 16 seconds. This is an observation on one
installation, not a guaranteed benchmark. The initial illustration and remaining
loading/transition intervals are retained. Changing ZIP compression would not
help this source: its main game data and native libraries are already uncompressed.

Fixed-aspect videos are not altered. Their complete image should be retained
with borders where needed; intro/finale playback has not been comprehensively
verified. Existing artwork is never resampled into a different aspect ratio by
this patch.

## Build on macOS

Follow the repository [setup guide](../../PATCHING_GUIDE.md), then:

```sh
./patch.sh --allow-experimental --check "/path/to/Hyper-Light-Drifter.apk"
./patch.sh --allow-experimental --output "output/Hyper-Light-Drifter-v1.1.99-4x3.apk" "/path/to/Hyper-Light-Drifter.apk"
```

## Build on Windows

After installing the same prerequisites, in PowerShell:

```powershell
.\patch.ps1 --allow-experimental --check "C:\Games\Hyper-Light-Drifter.apk"
.\patch.ps1 --allow-experimental --output "output\Hyper-Light-Drifter-v1.1.99-4x3.apk" "C:\Games\Hyper-Light-Drifter.apk"
```

`patch.bat` accepts the same arguments. No native compiler or game-asset editor is
needed to apply the patch. Both hosts use the repository's normal APK alignment
and local-signing tools.

### Original-aspect companion

This keeps the original camera and room layout while applying the startup and
controller improvements. Supply an original APK, not a 4:3 copy.

```sh
.venv/bin/python games/hyper-light-drifter/original_aspect.py "/path/to/Hyper-Light-Drifter.apk" --output "output/Hyper-Light-Drifter-v1.1.99-original-aspect.apk"
```

```powershell
.\.venv\Scripts\python.exe games\hyper-light-drifter\original_aspect.py "C:\Games\Hyper-Light-Drifter.apk" --output "output\Hyper-Light-Drifter-v1.1.99-original-aspect.apk"
```

## Supported input and checks

Source APK SHA-256:

```text
5455e20aa63fd72734b0037649d0ed52c503845de25fdaf511fc9296463307a9
```

The exact native library and game-data hashes are recorded in
[fingerprints.json](fingerprints.json). The whole-APK hash identifies the audited
source; matching native/data contents can also accept differently signed or
repackaged copies. Unknown native libraries, changed game data and mixed patch
revisions are refused. `--allow-experimental` does not bypass these checks.
Completed outputs are recognized without adding another payload. The
original-aspect output can be upgraded to 4:3; conversion back requires the
original source.

The authored native payload occupies a new read/execute ELF segment without
moving existing load segments or making code writable. Every replaced
instruction is checked, and final native/data hashes must match. The native
sources, linker addresses, entry hooks and payload are included under
[native/](native/); no game binaries, assets or signing keys are distributed.

## Known unfinished work

This release freezes the confirmed gameplay and control changes. In RIGHT aiming
mode, movement and firing are independent and the cursor follows the aiming stick,
but the character can slide in a standing pose instead of playing a walking
animation. The gun no longer disappears when moving diagonally upward.

Map and inventory content is usable, but its shared backdrop still has incorrect
placement/coverage. The hallucination backdrop and campfire scene also need
further 4:3 work. These are known incomplete scenes, not successful conversions.
The final release excludes the later experimental backdrop and diagnostic builds.

## Verification and limits

- Opening 4:3 gameplay, menu artwork, quit confirmation and controller option
  toggling have been checked on a physical ARM64 Android handheld with owner input.
- macOS source-APK builds and the original-aspect companion are checked locally.
- Synthetic tests check payload placement, branch bounds, unknown-input rejection,
  idempotency and inconsistent revisions. Repository CI runs on macOS and Windows.
- Windows execution with the proprietary source APK is not locally tested.
- All weapon variants, touch controls, languages, cinematics and late-game screens
  require broader manual coverage. Do not interpret a passing structural check
  as verification of every game scene.
