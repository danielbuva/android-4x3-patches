# Contributing

Contributions that add compatibility for another legitimately obtained APK revision are welcome. Do not submit APKs, extracted complete game files, private signing material, copyrighted artwork, or unchanged proprietary code.

## Compatibility contributions

1. Run `./patch.sh --check --json Game.apk` and record the package, version, engine, and failed target—never upload the APK.
2. Identify the narrowest semantic target: object hierarchy and component identity for Unity, resource/code names for GameMaker, class and method descriptors for DEX, or a masked instruction sequence with surrounding function context for native code.
3. Represent the change as transformation code or a minimal before/after pattern. Avoid fixed offsets. If an offset is unavoidable, constrain it to the target entry’s known hash and architecture, not the whole APK.
4. Require a unique match and recognize both original and patched states.
5. Add proprietary-free unit fixtures and document the tested version and limitations.

Version names, version codes, filenames, signatures, and whole-APK hashes may be logged as evidence but must not be the sole compatibility gate. Optional source-specific branding must remain nonblocking and silent when it cannot be patched safely.

Run before opening a pull request:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
python -m compileall -q src games patch.py
```

Confirm that `git status` contains no APKs, extracted binaries, keystores, generated outputs, or secrets.
