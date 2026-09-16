"""Regenerate own-code display-hook.json (maintainers only; needs LLVM tools).

python games/skate-3/build_display_hook.py --llvm-bin /path/to/llvm/bin
Normal APK patching uses the reviewed JSON and does not need a compiler.
"""
import argparse
import json
import struct
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llvm-bin", default="")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    def run(tool, *values):
        executable = str(Path(args.llvm_bin) / tool) if args.llvm_bin else tool
        return subprocess.check_output([executable, *map(str, values)], text=True)
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        run("clang", "--target=aarch64-linux-android33", "-O2", "-ffreestanding",
            "-fno-stack-protector", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables",
            "-ffp-contract=off", "-fno-slp-vectorize", "-c", root/"overlay_classifier.c", "-o", temp/"classifier.o")
        run("llvm-mc", "-triple=aarch64-linux-android", "-filetype=obj",
            root/"display_hook.S", "-o", temp/"hook.o")
        chunks = []
        for name in ("hook", "classifier"):
            if "R_AARCH64" in run("llvm-readelf", "-r", temp/f"{name}.o"):
                raise RuntimeError("Unexpected unresolved relocation")
            run("llvm-objcopy", "-O", "binary", "--only-section=.text", temp/f"{name}.o", temp/f"{name}.bin")
            chunks.append((temp/f"{name}.bin").read_bytes())
        symbols = {parts[2]: int(parts[0], 16)
                   for line in run("llvm-nm", "-n", temp/"hook.o").splitlines()
                   if len(parts := line.split()) == 3}
        links = {name: symbols[name] for name in
                 ("ea_return", "normal_return", "overlay_return", "class_title_page", "class_title_load",
                  "class_screen_page", "class_screen_load", "class_warmup_page", "class_warmup_load",
                  "class_menu_page", "class_menu_load", "scene_begin_load", "scene_end_load")}
        image = bytearray(b"".join(chunks))
        call = symbols["classifier_call"]
        struct.pack_into("<I", image, call, 0x94000000 | ((len(chunks[0])-call)//4))
        (root/"display-hook.json").write_text(json.dumps({"links": links, "code": image.hex()}, indent=2)+"\n")


if __name__ == "__main__":
    main()
