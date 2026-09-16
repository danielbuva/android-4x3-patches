# Bundled 4:3 artwork delta

This bundle reconstructs the title and startup-menu artwork tested on the
1280×960 device. Users supply their original `fedynamic.big`, not artwork files.

`manifest.json` names four texture arenas and records their original/patched
SHA-256 values. Each `.xor.zlib` is a compressed bytewise XOR difference between
the original and modified arena, not a standalone texture. The two title
resources share one delta. The bundle totals approximately 516 KiB.

Application checks the named resource's size and digest, verifies the delta,
XORs it with that source, and checks the result. Complete APKs, ISO files,
archives, and standalone background images are not included. Other archive
members do not participate in compatibility checks and remain unchanged.

## Artwork provenance

The original user-supplied title scene and menu gradient were extended with the
built-in ImageGen tool during device development on 2026-09-15. The title edit
continued the scene into the top/bottom letterbox areas, preserving the central
composition and avoiding logos/prompts or extra objects. The menu edit continued
the existing dark blue texture and lighting into a seamless 4:3 background.
Both were then packed and inspected with the live title effects and startup UI.
The deltas distribute that fixed, tested result; patching never calls an image
service and is deterministic.

The patch code is original; the underlying game artwork remains associated
with its original rights holders. This bundle does not provide the source game.

## Maintainer regeneration

Starting with the original archive and a locally verified replacement archive:

```sh
python games/skate-3/build_artwork_delta.py \
  --original /path/to/original/fedynamic.big \
  --modified /path/to/verified/fedynamic.big \
  --output /path/to/new-artwork-bundle
```

The output directory must not exist. The generator refuses changes outside the
four named resources or changes in arena size, shares identical deltas, and
verifies reconstruction before returning. Review the generated manifest and
payloads together when replacing this bundle.
