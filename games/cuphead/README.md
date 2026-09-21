# Cuphead — expanded gameplay camera experiment

A second ARM64 experiment demonstrates a true 4:3 viewport with the original
16:9 horizontal world coverage and one-third more vertical coverage. A
reproducible [opt-in camera probe](probe/README.md) is available. **This is not
a finished whole-game 4:3 patch** and Cuphead remains outside the normal registry.

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

## Camera findings

This Android port uses IL2CPP: the relevant Assembly-CSharp classes are compiled
into `libil2cpp.so`, with names and fields recoverable from IL2CPP metadata.
Desktop BepInEx plugins cannot simply be installed into this Android build.

- `AbstractCupheadCamera.UpdateRect` repeatedly fits a 16:9 viewport.
- `AbstractCupheadGameCamera.set_zoom` sets orthographic size to the camera's
  base size divided by zoom. The ordinary base is 360; map initialization uses
  3.6. `Awake` and map `Init` also set size directly.
- `AbstractCupheadCamera.get_Bounds` and `CalculateContainsBounds` read the
  actual orthographic size. Merely enlarging that property changes bounds used
  elsewhere in gameplay, even if width/height getters are left unchanged.
- `CupheadLevelCamera` is the shared level controller. The inspected camera
  hierarchy does not define separate run-and-gun, boss and plane subclasses;
  stage-specific scripts can still change zoom and need further testing.
- `CupheadMapCamera` has independent initialization and movement. Cutscene and
  shop cameras have their own classes.

The new probe modifies rendering projection each shared `LateUpdate`, after
original viewport calculation. It preserves horizontal projection (`m00`), sets
vertical projection (`m11`) from the actual screen aspect, and fills the viewport.
Stored size, zoom, logical bounds and camera movement remain unchanged. At 4:3
this is visually equivalent to `orthographicSize * 4/3`, without changing the
orthographic-size value queried by the game's bounds calculations.

## Measured result

A live ARM64 comparison at 1280×960 switched the same running level between
original and expanded projection. In the Forest Follies opening:

| Quantity | Original | Expanded |
|---|---:|---:|
| Viewport | 1280×720, centered | 1280×960, full screen |
| Zoom | 0.811 | 0.811 |
| Stored orthographic size | 443.896423 | 443.896423 |
| Horizontal world coverage | 1578.298462 | 1578.298462 |
| Vertical world coverage | 887.792847 | 1183.723877 |
| Logical bounds width × height | 1578.298462 × 887.792847 | unchanged |

The horizontal projection coefficient remained `0.001267187`; vertical changed
from `0.002252778` to `0.001689583`. Horizontal and vertical pixels per world unit
remain equal. Screenshots showed unchanged character proportions and additional
vertical scenery, rather than horizontal cropping or a stretched 16:9 frame.
The overworld also filled 4:3 with additional scenery, confirmed by manual play.
Map telemetry retained 12.8 world units horizontally while expanding 7.2 to 9.6
vertically. Default level framing likewise expanded 1280×720 to 1280×960.

The first rejected diagnostic missed direct initialization paths and combined
unrelated UI changes. Its results did **not** establish that expanded gameplay
was impossible. This investigation supersedes that earlier conclusion.

## Remaining limitations

- Finite artwork can end inside the taller viewport. The opening meadow exposes
  its lower edge. Decorative backgrounds may be scaled uniformly and cropped
  separately, but that must not move colliders, platforms, enemies or the player.
  The camera-only default leaves artwork unchanged. An optional Forest Follies
  meadow trial fits one decorative layer; it does not solve every background.
- Keep the current camera positioning; there is no bottom-alignment change.
- HUD, menus, subtitles, touch anchors and fixed-aspect story scenes have not
  received the required separate treatment. A death overlay still covers only
  its original central region. The shared level-camera class also appears in
  some non-gameplay scenes, so its class name alone is not a full scene filter.
- Zoom updates and scene transitions were observed, but all boss phases, plane
  stages, render effects and projection-dependent gameplay consumers have not
  been exhaustively tested. Preserving bounds is evidence, not a complete-game
  behavioral guarantee.
- A transient `BlurOptimized.OnRenderImage` null-reference error was observed
  during a transition; attribution to the probe versus the source is unresolved.
- Only ARM64 device execution was checked. ARMv7 remains unchanged. Windows
  commercial-APK rebuilding and runtime execution were not tested.

## Reproduction and verification

See [probe instructions and source](probe/README.md). The library and metadata
have independent SHA-256 guards; unknown revisions are refused and an already
patched library is recognized. The reviewed payload contains only newly written
probe code, with complete C source and linker inputs. It uses shared APK
repacking, alignment and local signing tools on macOS and Windows.

The original-aspect output previously passed archive and Android-signature
checks, plus startup through the first playable room. The camera experiment
was built and signed on macOS, installed to adopted storage, and checked with
live geometry logs and screenshots. Manual testing continues; it is not a
production release. No game APK, extracted commercial binary, artwork, signing
material or device identifier is published.

## External references

The [4:3 hex-patch report](https://www.reddit.com/r/crtgaming/comments/1py9193/cuphead_43_fix/)
identifies the hardcoded aspect constant, but also reports horizontal cropping.
[Cuphead UltraWide](https://www.nexusmods.com/cuphead/mods/122) identifies camera
aspect/viewport patch targets and notes finite background artwork.
[DebugMod CameraZoom](https://github.com/DemoJameson/Cuphead.DebugMod/blob/master/Cuphead.DebugMod/Components/CameraZoom.cs)
uses the gameplay camera's `Zoom` method. These guided investigation; their
Windows runtime plugins are not the Android implementation.
