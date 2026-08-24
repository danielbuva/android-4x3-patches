# Android 4:3 Patches

Reproducible, target-verified patches that adapt selected Android game ports to a 4:3 display without stretching, squashing, or simply cropping a widescreen frame. Where the game permits it, the patches preserve horizontal coverage and reveal additional vertical game area, then adjust UI placement for the taller view.

> New here? Start with the [step-by-step APK patching guide](PATCHING_GUIDE.md).

> [!IMPORTANT]
> This repository contains no games or APKs. You must supply your own lawfully obtained APK. It is an unofficial community project and is not affiliated with, authorized by, or endorsed by any game developer, publisher, platform holder, or Android distributor.

## Supported patches

| Game | Android package | 4:3 result | UI changes | Personally tested build | Compatibility |
|---|---|---|---|---|---|
| Blasphemous | `com.thegamekitchen.blasphemousmobile` | Expanded 640×480 compositor and camera | Canvas and achievement popup placement | 1.9.0 (38) | Target-detected |
| FAITH: The Unholy Trinity | `com.airdorf.faiththeunholytrinityunofficialandroidportbyplayer1444` | 1440×1080 view; side artwork removed | Persistent touch-overlay visibility option | 1.0.0 (1000000) | Target-detected; UndertaleModTool required |
| Hollow Knight | `com.TeamCherry.HollowKnight` | Expanded vertical camera view | HUD camera, top HUD, and touch anchors | Port revision 11833 | Target-detected |
| Hollow Knight: Silksong | `com.game.silksong` | Camera minimum lowered to 4:3 | Adaptive menu/loading placement | 1.2.0 (8) | Target-detected |
| Hotline Miami | `com.devolverdigital.hotlinemiami` | True 4:3 rooms and cameras | Mobile UI and full-height lighting surfaces | 1.0.180 (1000180) | Target-detected; UndertaleModTool required |
| Sea of Stars | `com.playdigious.seaofstars` | 640×480 renderer with added vertical world view | Edge-to-edge 4:3 UI | 3.0.60158 (60158) | Target-detected |
| Shin Chan: Shiro & Coal Town | `com.crunchyroll.gv.shinchanshiroandcoal.game` | 4:3 gameplay, title, and menu | Opening movie uses proportional center crop | 1.0.2 (11) | Target-detected |
| Skul: The Hero Slayer | `com.playdigious.skul` | 640×480 gameplay | 1920×1440 UI/HUD reference | 1.0.13 (66) | Target-detected |
| Vampire Survivors | `com.poncle.vampiresurvivors` | Removes the translucent aspect mask | Responsive UI uses real top/bottom edges | 1.15.115 (64958511) | Target-detected |
| Baba Is You | `org.hempuli.baba` | **Experimental:** incomplete 4:3 attempt | Known right-edge shift/crop remains | 617.0 (617) | Requires `--allow-experimental` |

“Personally tested build” records the APK revision used during development. It is not an exact-version requirement: compatibility is decided from the package and required patch targets.

### Games already supporting 4:3

The tested Android versions of **Brotato**, **Dead Cells**, **DREDGE**, and **Thronefall** already render correctly at 4:3 and do not need patches from this project.

## Prerequisites

- Python 3.11 or newer
- Java/JDK 17 or newer (`keytool`)
- Android SDK Build Tools (`zipalign` and `apksigner`)
- Python packages from `requirements.txt`
- For FAITH and Hotline Miami: UndertaleModTool CLI (tested with 0.9.1.2), available as `UndertaleModCli` on `PATH` or through `ANDROID_4X3_UMT`/`UMT_CLI`

The patcher looks for Android Build Tools on `PATH`, under `ANDROID_HOME`/`ANDROID_SDK_ROOT`, and in common SDK locations.

## Setup

### macOS or Linux

```sh
git clone https://github.com/danielbuva/android-4x3-patches.git
cd android-4x3-patches
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Patch an APK:

```sh
./patch.sh "/path/to/Game.apk"
```

### Windows

```bat
git clone https://github.com/danielbuva/android-4x3-patches.git
cd android-4x3-patches
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
patch.bat "C:\path\to\Game.apk"
```

The default output is `output/<Game>-4x3.apk`. Input files are never overwritten.

## Useful commands

```sh
./patch.sh --list-games
./patch.sh --check "/path/to/Game.apk"
./patch.sh --dry-run --json "/path/to/Game.apk"
./patch.sh --output "/path/with spaces/Game-4x3.apk" "/path/to/Game.apk"
./patch.sh --allow-experimental "/path/to/Baba-Is-You.apk"
```

Use `--unsigned` to produce an aligned but unsigned APK, `--keystore` with `ANDROID4X3_KEYSTORE_PASSWORD` for your own key, and `--keep-work` when debugging a compatibility failure. Custom keys can also set `ANDROID4X3_KEY_ALIAS` and a distinct `ANDROID4X3_KEY_PASSWORD`; their passwords are held only in temporary permission-restricted files during signing.

## Compatibility and safety

The patcher deliberately does not require a whole-APK hash match. For each input it:

1. Reads the Android package from the binary manifest.
2. Checks that required engine files exist.
3. Locates the relevant Unity objects, GameMaker resources, DEX methods, native instruction patterns, or serialized values.
4. Requires every core target to be uniquely recognizable as original or already patched.
5. Rebuilds once, aligns, signs, and reopens the result to verify the patched state.

An unfamiliar revision fails without changing the source APK when required targets are absent or ambiguous. APKVision and other source-specific branding cleanup is opportunistic: recognized safe targets are removed, while absent or unrecognized variants are silently left alone and never block the 4:3 patch.

For games with thousands of Addressables files, tested bundle names are used as fast-path locators only after the expected semantic targets inside them also match. If those names are absent or incomplete, the patcher falls back to the broader configured scan and applies global ambiguity checks; the filename alone is never accepted as proof of compatibility.

Universal and already-merged split APKs can work when they contain the required entries. Raw split APK sets must first be merged into one installable APK using tooling appropriate to the copy you own.

Clean Play Store-derived, differently signed, universal, and standalone APKs are all eligible when their package and patch targets are recognizable. The patcher does not remove cloud saves, Play Games, billing, purchases, or unrelated online functionality.

## Signing and installation

Modified APKs cannot retain the developer’s original signature. On first use the patcher generates a private PKCS12 key in your operating system’s user-data directory and reuses it for later builds. The key and password are never stored in this repository.

Android will reject an update when the installed app was signed by a different key. Back up saves first; installing the patched copy may require uninstalling the existing app, which can erase private app data. Cloud-save compatibility depends on the game and account environment.

Install after reviewing that implication:

```sh
adb install "/path/to/Game-4x3.apk"
```

## Troubleshooting

- **Unsupported or ambiguous target:** the APK revision changed a required structure. Run `--check --json` and include that report in a compatibility contribution; do not weaken target cardinality checks.
- **`zipalign` or `apksigner` missing:** install Android SDK Build Tools and set `ANDROID_SDK_ROOT` or add the tools to `PATH`.
- **UndertaleModTool missing:** set `ANDROID_4X3_UMT` to the CLI executable for FAITH or Hotline Miami.
- **Signature conflict:** read the signing section before uninstalling anything.
- **Baba output is cropped:** this is the documented experimental limitation, not a signing or installation fault.

See [CONTRIBUTING.md](CONTRIBUTING.md) for adding support for another revision. Patch code is MIT licensed; games, trademarks, and third-party tools remain the property of their respective owners.
