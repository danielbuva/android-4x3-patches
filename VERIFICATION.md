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
| Rogue Legacy, STALKER: Call of Pripyat Mobile | Experimental | Rogue Legacy's clean reference recognizes the jointly centered options, full 1320x990 map/teleporter target, restored 720-line world-grid normalization, post-scale right-aligned proportional full-height loading gate, top-overscanned pause dimmer, bottom-docked projectile edge marker, top-anchored extended death spotlights, and screen-local touch-overlay suppression. The unrelated rune shop remains at its original Y=360. The rebuilt APK reached signed post-state and was installed on adopted storage. STALKER upgrades settings text to 19/21/24/26 while accepting the earlier pass as input. Rogue Legacy's latest visual confirmation remains pending. |
| Children of Morta, Death Road to Canada, Dusklight, Grimvalor, Huntdown | Experimental | Proprietary-free target tests and development-output checks pass. Death Road analog-axis, D-pad, and idle captures kept the same selection and showed the same animated highlight, so no input patch was added. Complete visual inspection remains pending. |

| Mega Man X Regenesis | Experimental | Developer APK 1.00.82 rebuilt with the public command; signed post-state and sparse-index integrity verified. Streamed installation and in-place updates succeeded on adopted storage. Opening sequence, enlarged save-selection screen, and opening in-world dialogue inspected at 1280×960; no script errors after correcting the sparse directory. Transient Vulkan surface-loss messages occurred during transitions, followed by successful rendering; extended stability testing is pending. Options follow-up: inspected all 14 rows at 1280×960 with separated labels, checkboxes, volume bars, language and save-slot values; long English labels remain visible. The title background sprite is disabled in this developer build; settled-menu particles extend outside the old 16:9 frame, so no image crop was applied. All 192 synthetic tests pass locally, including the native rebuild/signing fixture. Full gameplay and translated UI review remain pending. |

| Skate 3 Mobile | Experimental | Buku313 2.1.0 (20100), ARM64: clean-to-patched signed reproduction; 24 native/DEX targets; actual ARM64 camera/culling/HUD/hook checks; user accepted the 16:9/4:3 gameplay comparison and raised name-entry dialog. Adopted APK/private/shared storage and one installed package verified. Full career and extended stability testing remain pending. |

The supported-games table in [README.md](README.md#supported-patches) is the
authoritative status list. Experimental modules require
`--allow-experimental`; that flag acknowledges the documented visual state and
does not weaken structural compatibility checks.

### Hollow Knight 1.3.0.0 Mono port

The Mono implementation was reproduced from its unmodified source APK with the
public patch command, rebuilt, aligned, signed, and recognized as patched by the
post-build target probe. After discovering that this port can retain an
extracted Unity bundle across replace-installs and ordinary uninstalls, its
package-scoped private and external state was removed, and the signed APK was
clean-installed on adopted internal storage and cold-launched on the 1280×960
physical device. The
disclaimer, language selection, startup logos, main menu,
profile/overscan/brightness UI, opening sequence, initial gameplay, top-edge
HUD/touch layout, and inventory were exercised. The inventory's complete frame
and page composition are uniformly fitted, fully visible at both horizontal
edges, and centered within about 10 pixels of the 640×480 display midpoint,
without horizontal stretching. The runtime menu-open hook was required because
the port restores its original inventory transform after loading. The process
remained alive without a fatal exception. Final gameplay-wide
acceptance remains the device owner's check.

### Skate 3 Mobile 2.1.0

The public patch command reproduces the modified APK from the original port,
rebuilds/aligned-signs it, and verifies all 24 targets. Compatibility uses guarded
executable instructions, exported native function ranges, resolved movie-state
loads, immutable render-frame layout, and DEX method/field identities. The APK
patch does not change the Xbox ISO or extracted assets. A separate optional
background packer edits four named texture arenas in a new archive copy; no
commercial or generated game assets are included in the repository.

Proprietary-free tests cover ambiguous/unknown/relocated targets, architecture,
DEX identity, mixed/post states, idempotence, ELF hook integrity, matrix columns,
connected portrait/panel groups, full-canvas and tiled backdrop classification,
stock/custom title effects, guest button byte order, and adopted-install
failures without uninstalling or clearing data. Development also executed the
actual patched ARM64 camera, culling, display, keyboard, and output-aspect code
with synthetic inputs. Horizontal camera coverage stays unchanged; top/bottom
visibility expands without repeated scaling. A connected Coach Frank portrait
and panel retain a common anchor while unrelated bottom HUD moves outward.
Only the active first-movie YUV draw uses cover cropping. Hook calls preserve
live registers and stack state. The keyboard hook requests (640,120) with a
top-center pivot at 1280×960. Reapplying output settings retains exactly 4:3.

Physical-device checks at 1280×960 covered the EA movie ending, clean title
background/grain/glow alignment, enlarged difficulty and camera dialogs, camera
previews fitting their frames, initial gameplay, menus, absence of TOUCH/HIDE,
and adopted-storage installation. The first tutorial now shows Coach Frank
with a joined head/body and its intact text panel; the objective HUD sits at the
bottom edge. The device owner accepted the original 16:9
versus patched 4:3 gameplay comparison and confirmed the raised name field. Fresh team-name and character-name dialogs were also
verified above the Android keyboard.
The off-canvas “Sign up” action remains implemented but outside the visible edge.
Only one package remains installed.

Startup testing used a temporary isolated test save location; the final APK
retains the original save paths. A camera confirmation was also reaching the
port's global movie-skip poll. Its shortcut now recognizes Start only, including
the guest button field's big-endian representation. A subsequent fresh flow
completed the intro movie and reached the populated team-creation prompt
without the empty difficulty screen, then advanced through naming,
customization, and the first tutorial. The enlarged dialog scales
preview videos and frames together. Complete career, every individual overlay,
and long-session behavior have not been exhaustively tested; this module
remains experimental.

## Native 4:3 and deferred titles

Brotato, Dead Cells, DREDGE, and Thronefall already supported 4:3 in the tested
Android builds, so this repository has no modules for them. GRID Legends is
deferred because the available source wrapper exited before game startup even
without a 4:3 modification.

Cuphead 1.0.2 (build 4) now has an opt-in ARM64 camera probe. Live A/B geometry
and screenshots establish unchanged horizontal coverage, proportional rendering
and one-third more vertical coverage at 1280×960. The overworld also fills 4:3.
Finite background edges, UI, overlays and full-game compatibility remain
unfinished. The original-aspect APK and camera experiment were built/signed on
macOS; commercial-APK rebuilding on Windows and ARMv7 execution are untested.
See the [investigation record](games/cuphead/README.md) for exact measurements,
source guards and the limitations of the earlier rejected diagnostic.

## Release checks

Before a release, maintainers run the full proprietary-free test suite, ZIP and
signature verification for reproduced outputs, a prohibited-artifact scan, and
`git diff --check`. A release must contain no APK/APKS/AAB files, extracted
commercial assets, native or managed game binaries, private signing material,
or machine-specific paths.
