# Cuphead — 4:3 conversion deferred

No Cuphead 4:3 patch is registered or released. A camera prototype for the
build below did not satisfy proportional, uncropped presentation at 1280×960.
Do not treat a fullscreen Android surface, a taller HUD, or a bordered 16:9
scene as evidence of a successful gameplay conversion.

## Investigated source

| Field | Value |
|---|---|
| Package | `com.gabedeveloper.cuphead` |
| Version | `1.0.2` (version code `4`) |
| Engine | Unity `2017.4.40f1`, IL2CPP |
| Included architectures | `arm64-v8a`, `armeabi-v7a` |
| APK size | 1,946,927,147 bytes |
| APK SHA-256 | `e73b2dd9877b30f8d511b10fc3040e64fa2061487a25b0ec463269802505a70f` |

The checksum identifies the investigated input; it does not establish support
for this or any other Cuphead APK. Both Windows and macOS launchers reject the
unregistered package. `--allow-experimental` does not enable Cuphead.

## Specific blockers

The shared camera's `UpdateRect` fits a 16:9 viewport to the screen. Ordinary
level cameras use an orthographic half-height of 360. At the original horizontal
coverage, a 4:3 view needs a half-height of 480. Changing only the viewport loses
horizontal content; changing the renderer size alone is insufficient.

Camera dimensions also participate in level tracking and gameplay boundary
calculations. Those calculations must be separated from display expansion.
The build additionally has independent initial-camera, map-initialization,
zoom, cinematic, UI, and special-effect camera paths. One global aspect or
size replacement does not cover them safely.

A local ARM64 diagnostic changed the shared viewport, enlarged the zoom-path
projection without changing the gameplay dimension getters, and adjusted UI
camera/reference height. A limited physical-device check found:

- Title artwork and the opening storybook were cropped. These fixed-aspect
  presentations need their own proportional fit with borders.
- The first playable room retained its bordered artwork even while the HUD
  moved to the bottom of the 4:3 surface. This was not a demonstrated expanded
  gameplay scene.
- UI and touch controls did not receive a complete scene-by-scene reflow or
  alignment verification. No complete-game compatibility claim was made.

The scene data supplies an additional concrete artwork constraint: the
serialized tutorial background's front and back layers each have a 665×374
sprite rectangle, approximately 0.52 pixels per unit, and a cumulative 1.25
scale. Their initial vertical extent is about 899 world units, less than the
960-unit view required to preserve horizontal coverage. Simply enlarging the
camera cannot supply missing artwork. Scaling the artwork to cover that gap
would require a separate audit of framing and preservation of existing content.

These findings block release of the camera prototype under the no-crop,
no-distortion requirements. They are not a claim that every future port or a
full scene-by-scene reimplementation is impossible. A future attempt must
handle fixed-aspect exceptions explicitly, demonstrate genuine expanded
playable scenes, preserve gameplay boundaries and special camera effects, and
verify HUD, menus, subtitles, and touch hit regions at the actual display size.

## Verification and disposition

The original-aspect output was rebuilt and signed on macOS. Archive integrity,
Android signature verification, preservation of the game's engine/assets, and
a limited physical-device startup through the title and first playable room
were checked. The diagnostic was rejected and removed; it is not a downloadable
artifact. The final device state contains no installed Cuphead package.

The diagnostic was exercised only on ARM64. No ARMv7 runtime check, Windows
Cuphead rebuild, full playthrough, or comprehensive touch/UI verification was
performed. Shared repository CI does not constitute Cuphead support.

Only this investigation record is published. No game APK, extracted game
binary, artwork, signing material, device identifier, or diagnostic patch is
included.
