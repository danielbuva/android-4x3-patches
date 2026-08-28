# STALKER: Call of Pripyat Mobile

> [!IMPORTANT]
> This patch is experimental. Its native and Unity targets are verified
> structurally, but complete visual testing is still pending. Use
> `--allow-experimental` to acknowledge that status; the flag does not force
> an unsupported APK to patch.

- Package: `com.Death13.S.T.A.L.K.E.R.CallofPripyat`
- Engine: Unity 2021.3 IL2CPP
- Tested build: `0.3` (version code `1`)
- Audited architectures: ARM64 and ARMv7
- Output: `STALKER-Call-of-Pripyat-4x3.apk`

## What the patch changes

The tested port offers three 2:1 render-resolution tiers. The patch replaces
all three with matching 4:3 tiers:

| Quality tier | Original | Patched |
|---|---:|---:|
| Low | 720×360 | 640×480 |
| Medium | 1440×720 | 1280×960 |
| High | 2160×1080 | 1920×1440 |

The main-menu, character, and first-person weapon cameras are changed from a
60-degree vertical field of view to approximately 81.786789 degrees. This is
calculated to preserve the original 2:1 horizontal view while revealing more
area above and below at 4:3. It does not stretch, squash, or side-crop the
world view.

The Unity UI is updated alongside those render changes:

- the main-menu reference canvas becomes 1280×960
- the author/credits and gameplay/pause reference canvases become 1920×1440
- main-menu and pause-menu resolution labels show the new 4:3 choices
- a recognized VK promotion button is hidden in the main and pause menus when
  its exact object, component, and listener are safely identified

VK-button hiding is optional and source-specific. Missing or unfamiliar
variants are preserved silently and never affect 4:3 compatibility. Shared
APKVision cleanup is also optional and non-blocking.

## Usage

Check the APK before creating an output:

```sh
./patch.sh --check --allow-experimental "/path/to/STALKER-Call-of-Pripyat.apk"
```

Create the patched APK on macOS or Linux:

```sh
./patch.sh --allow-experimental "/path/to/STALKER-Call-of-Pripyat.apk"
```

On Windows:

```bat
patch.bat --allow-experimental "C:\path\to\STALKER-Call-of-Pripyat.apk"
```

The original APK is not overwritten. Unless `--output` is supplied, the
result is written under `output/` as
`STALKER-Call-of-Pripyat-4x3.apk`.

## Compatibility and safety

The tested version is informational. Compatibility is determined from the
Android package and the actual native and Unity targets, not from the APK's
filename, source, version, signature, or whole-file hash.

The module requires `assets/bin/Data/data.unity3d` to be a supported UnityFS
bundle containing the expected `level0` and `level1` scenes. It resolves core
objects by full hierarchy path and then verifies the expected component type
and, for UI behaviours, MonoScript identity. It does not trust Unity PathIDs
as stable identifiers.

At least one audited `libil2cpp.so` must be present:

- `lib/arm64-v8a/libil2cpp.so`
- `lib/armeabi-v7a/libil2cpp.so`

Each audited ABI included in the APK must expose exactly one guarded
`GameSettings.DropVideoQuality` instruction region, inside an executable ELF
segment, with all six resolution values in recognized original or patched
states. The patcher updates every audited ABI that is present. A package with
one supported audited ABI is acceptable; a present but unrecognized audited
ABI causes a safe refusal.

Unity camera, CanvasScaler, and resolution-dropdown targets must likewise be
unique and contain recognized original or patched values. Mixed-state and
already-patched APKs can be completed or accepted. Missing, duplicated, or
unknown required targets stop the patch without guessed offsets.

## Signing and installation

The rebuilt APK cannot keep the developer's original signature. By default,
the shared patcher generates and reuses a random local PKCS12 signing identity
outside this repository; no signing key is distributed with the project.

Android rejects an in-place update when the installed app uses a different
signature. Back up saves before uninstalling an existing copy, because
uninstalling may erase private app data. Retain the generated local key so
later patched builds can update earlier ones signed by that same key. The
shared signing options also allow an explicitly supplied personal key.

## Verification and limitations

The proprietary-free tests exercise both audited ABIs, executable-segment and
unique-pattern guards, all three render tiers, original/patched states,
idempotent Unity edits, exact CanvasScaler validation, dropdown callback and
label checks, the horizontal-view-preserving field-of-view calculation, and
non-blocking optional cleanup. The patch also reopens its rebuilt Unity and
native entries and requires a fully patched postcondition.

The production targets come from the audited `0.3` build. Other revisions may
work when these semantic and instruction-level structures are unchanged, but
complete device-side visual review of the menu, author screen, pause UI,
gameplay cameras, weapon camera, and all quality tiers is still pending.

Intro-related objects in the tested data are inspected only as optional,
non-gating presentation invariants; this module does not rewrite an unfamiliar
intro implementation. The currently audited native patches cover ARM64 and
ARMv7 only.
