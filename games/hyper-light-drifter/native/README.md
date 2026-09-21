# Rebuilding the authored payload

Normal patch users do not compile this code. The checked-in hexadecimal payload
is built from these authored C/assembly sources, not extracted game code.
Absolute interfaces apply only to the native fingerprint in the parent directory.

Development toolchain: Android NDK r21d (21.3.6528147), Clang 9.0.8, target aarch64-linux-android21.
From this directory, with the NDK compiler and LLVM tools available:

```sh
clang --target=aarch64-linux-android21 -O2 -fPIC -fno-stack-protector \
  -fno-unwind-tables -fno-asynchronous-unwind-tables -nostdlib -static \
  -Wl,-T,layout.ld -Wl,--build-id=none layout.c controls.c trampolines.S -o payload.elf
llvm-objcopy -O binary --only-section=.text payload.elf payload.bin
llvm-readelf -r payload.elf
```

There must be no remaining relocations or writable sections. The linker rejects
writable data and counters because the payload is mapped read/execute only. A compiler change can change symbol
positions: regenerate `hooks.json` from the resulting ELF symbol table, rather
than reusing old entry addresses. Update the payload and final output hashes
only after rebuilding both variants and verifying runtime behavior. Keep ELF,
binary, APK and extracted game inputs in the repository's ignored work directory.

The hook ABI uses the engine's 16-byte value representation and original entry
prologues. Default control mode delegates to the original game behavior. Options
are stored through the existing game save-file API; no absolute storage paths
or device identifiers are used.
