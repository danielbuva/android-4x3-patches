# Verification record

This project separates four kinds of evidence so a successful structure check
is never presented as visual proof:

- **Synthetic tests** exercise target matching, original/patched/ambiguous
  states, idempotence, repacking, signing, and failure behavior without game
  files.
- **Clean-to-patched reproduction** runs the public patcher on an unmodified or
  cleanup-only user-supplied APK, then verifies the rebuilt APK's postconditions.
- **Archived post-state recognition** confirms that a development APK still
  contains every expected patched target. It does not prove that a currently
  unavailable clean source can be reproduced byte-for-byte.
- **Physical-device verification** checks launch and presentation on the
  1280x960 Android test device. Emulator or host-side checks are not counted as
  physical visual verification.

No APK, extracted game asset, signing key, device identifier, or local path is
stored in this record.

## Current results

| Game group | Repository state | Verification evidence |
|---|---|---|
| Blasphemous, FAITH, Hollow Knight, Hollow Knight: Silksong, Hotline Miami, Sea of Stars, Shin Chan, Skul, Vampire Survivors | Verified | Proprietary-free tests, archived patched-state recognition, and physical-device visual checks performed during development |
| Streets of Rage 4 | Verified | Clean-to-patched public-command reproduction; all managed, named-bigfile, and 17 video targets reached patched state; signed archive verification passed; filler removal and gameplay were verified at 1280x960. The latest nested-canvas, bottom-control, loading, and stage-map targets are recognized on both the clean reference and archived prior post-state; the upgraded build reached signed post-state, installed on adopted storage, and cold-launched. Exact placement awaits visual confirmation. |
| Baba Is You | Experimental | Structural and archived post-state checks pass, but the known right-edge shift/crop remains visible |
| Advent Neon, AM2R | Experimental | Advent Neon was rebuilt clean-to-patched with centered title/controls/warning foregrounds and exact-known GameMaker splash neutralization; signed post-state recognition, adopted-storage installation, and cold launch passed. Latest placement awaits visual confirmation. AM2R retains its prior result. |
| Rogue Legacy, STALKER: Call of Pripyat Mobile | Experimental | Rogue Legacy's clean reference and archived prior post-state both recognize the expanded 1220x890 map/teleporter target plus its 990-line labels and legend; the upgraded build reached signed post-state, installed on adopted storage, and cold-launched. STALKER upgrades settings text to 19/21/24/26 while accepting the earlier pass as input. Visual confirmation remains pending. |
| Children of Morta, Death Road to Canada, Dusklight, Grimvalor, Huntdown | Experimental | Proprietary-free target tests and development-output checks pass. Death Road analog-axis, D-pad, and idle captures kept the same selection and showed the same animated highlight, so no input patch was added. Complete visual inspection remains pending. |

The supported-games table in [README.md](README.md#supported-patches) is the
authoritative status list. Experimental modules require
`--allow-experimental`; that flag acknowledges the documented visual state and
does not weaken structural compatibility checks.

## Native 4:3 and deferred titles

Brotato, Dead Cells, DREDGE, and Thronefall already supported 4:3 in the tested
Android builds, so this repository has no modules for them. GRID Legends is
deferred because the available source wrapper exited before game startup even
without a 4:3 modification.

## Release checks

Before a release, maintainers run the full proprietary-free test suite, ZIP and
signature verification for reproduced outputs, a prohibited-artifact scan, and
`git diff --check`. A release must contain no APK/APKS/AAB files, extracted
commercial assets, native or managed game binaries, private signing material,
or machine-specific paths.
