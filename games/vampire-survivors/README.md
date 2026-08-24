# Vampire Survivors

- Package: `com.poncle.vampiresurvivors`
- Engine: Unity IL2CPP (AArch64)
- Tested build: `1.15.115` (version code `64958511`)

## Changes

Vampire Survivors already draws its game world across the physical 4:3 screen,
but its UI helper forces a 16:10 safe area and translucent aspect-mask images
cover the extra space. This patch clears that forced ratio in the four built-in
scenes and prevents the mask from being enabled. The game's existing responsive
layout then places UI at the real top and bottom edges without cropping,
stretching, or squashing the world.

## Compatibility

The Unity objects are located through scene, GameObject, component, and Safe
Area relationships rather than PathIDs or object hashes. The native method is
located through a unique contextual AArch64 instruction sequence rather than a
fixed file offset. APK version, signature, source, and whole-file hashes are not
compatibility gates.

All four UI helpers and the native mask method must be recognized uniquely.
Original, partially patched, and already-patched inputs are handled safely;
unknown or ambiguous required structures are refused. Only AArch64 IL2CPP is
currently supported.
