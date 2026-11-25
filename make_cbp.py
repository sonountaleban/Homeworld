#!/usr/bin/env python3
"""
Generate a Code::Blocks project (Homeworld.cbp) for HomeworldSDL.

Usage (from anywhere):
    python3 make_cbp.py /path/to/HomeworldSDL [--movies] [--out Homeworld.cbp]

What it does
  1. Runs `meson setup` ONCE in <repo>/build-cbp (configure only; Meson is not used
     to compile the game). This is needed because part of the sources are generated
     (e.g. the KAS script compiler in tools/ uses flex/bison).
  2. Builds only the generated source files via ninja (so they exist on disk).
  3. Reads build-cbp/compile_commands.json and takes the exact source list,
     -D defines and -I include paths used for the `homeworld` executable.
  4. Writes a .cbp (Debug + Release targets) that Code::Blocks compiles itself.

Prerequisites (Ubuntu 24.04):
    sudo apt install build-essential meson ninja-build pkg-config flex bison \
        libsdl2-dev libgl-dev libx11-dev
    # only with --movies:
    sudo apt install libavcodec-dev libavformat-dev libavutil-dev libswscale-dev
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
from xml.sax.saxutils import quoteattr


def run(cmd, cwd=None):
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--movies", action="store_true",
                    help="enable FFMPEG cutscene support (default: off)")
    ap.add_argument("--out", default="Homeworld.cbp")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    build = os.path.join(repo, "build-cbp")
    ccj = os.path.join(build, "compile_commands.json")

    if not os.path.exists(ccj):
        run(["meson", "setup", "build-cbp", "-Db_sanitize=none",
             "-Dmovies=" + ("true" if args.movies else "false")], cwd=repo)

    with open(ccj) as f:
        entries = json.load(f)

    # Meson puts objects of target "homeworld" in "homeworld.p/".
    def is_hw(e):
        out = e.get("output", "").replace("\\", "/")
        parts = out.split("/")
        if "homeworld.p" in parts:
            return True
        # Everything else under src/ is part of the game (e.g. the static library
        # linked via `link_with: [lib_sdl]`). Skip build-host helper tools
        # (kas2c, biggie, ...) and subprojects.
        return parts[0] == "src"

    all_entries = entries
    entries = [e for e in all_entries if is_hw(e)]
    if not entries:
        seen = sorted({(e.get("output") or "?").split("/")[0] for e in all_entries})
        sys.exit("No entries for the 'homeworld' target in compile_commands.json.\n"
                 "Output dirs found: " + ", ".join(seen[:20]))

    print("Including build dirs:",
          ", ".join(sorted({os.path.dirname(e["output"]) for e in entries})))

    defines, includes = [], []
    sources = []
    generated = []

    for e in entries:
        argv = e.get("arguments") or shlex.split(e["command"])
        cwd = e["directory"]
        src = os.path.normpath(os.path.join(cwd, e["file"]))
        sources.append(src)
        if src.startswith(build + os.sep):
            generated.append(os.path.relpath(src, build))
        i = 0
        while i < len(argv):
            a = argv[i]
            if a in ("-I", "-isystem", "-D") and i + 1 < len(argv):
                a, val = a, argv[i + 1]
                i += 1
            elif a.startswith("-D"):
                a, val = "-D", a[2:]
            elif a.startswith("-I"):
                a, val = "-I", a[2:]
            elif a.startswith("-isystem"):
                a, val = "-isystem", a[8:]
            else:
                i += 1
                continue
            if a == "-D":
                if val not in defines:
                    defines.append(val)
            else:
                p = os.path.normpath(os.path.join(cwd, val))
                if p not in includes:
                    includes.append(p)
            i += 1

    # Make sure generated sources exist.
    if generated:
        run(["ninja", "-C", build] + sorted(set(generated)))

    def rel(p):
        return os.path.relpath(p, os.path.dirname(os.path.abspath(args.out)) if
                               os.path.dirname(args.out) else repo)

    # Project lives in the repo root by default.
    out_path = args.out if os.path.isabs(args.out) else os.path.join(repo, args.out)
    base = os.path.dirname(out_path)

    def r(p):
        return os.path.relpath(p, base)

    # Headers (for the project tree only).
    headers = []
    for root, _, files in os.walk(os.path.join(repo, "src")):
        for fn in files:
            if fn.endswith(".h"):
                headers.append(os.path.join(root, fn))
    headers.sort()

    movies = "HW_ENABLE_MOVIES" in defines

    def common_opts():
        o = ["-std=gnu11", "-Wall", "-Wno-unused-result"]
        o += ["`pkg-config --cflags sdl2`"]
        # Mirror the project's warning suppressions that matter for gnu11 on modern GCC.
        o += ["-Wno-implicit-function-declaration", "-Wno-incompatible-pointer-types",
              "-Wno-int-conversion", "-Wno-pointer-to-int-cast",
              "-Wno-int-to-pointer-cast"]
        return o

    libs = ["-no-pie", "`pkg-config --libs sdl2`", "-lGL", "-lX11", "-lm"]
    if movies:
        libs += ["`pkg-config --libs libavutil libswscale libavcodec libavformat`"]

    L = []
    w = L.append
    w('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>')
    w('<CodeBlocks_project_file>')
    w('\t<FileVersion major="1" minor="6" />')
    w('\t<Project>')
    w('\t\t<Option title="HomeworldSDL" />')
    w('\t\t<Option pch_mode="2" />')
    w('\t\t<Option compiler="gcc" />')
    w('\t\t<Build>')
    for name, extra, dbg in (("Debug", ["-g", "-O0"], True),
                             ("Release", ["-O2"], False)):
        w(f'\t\t\t<Target title="{name}">')
        w(f'\t\t\t\t<Option output="bin/{name}/homeworld" prefix_auto="0" extension_auto="0" />')
        w(f'\t\t\t\t<Option object_output="obj/{name}/" />')
        w('\t\t\t\t<Option type="1" />')
        w('\t\t\t\t<Option compiler="gcc" />')
        w('\t\t\t\t<Compiler>')
        for o in extra:
            w(f'\t\t\t\t\t<Add option={quoteattr(o)} />')
        w(f'\t\t\t\t\t<Add option="-DHW_BUILD_FOR_{"DEBUGGING" if dbg else "DISTRIBUTION"}" />')
        w('\t\t\t\t</Compiler>')
        w('\t\t\t</Target>')
    w('\t\t</Build>')

    w('\t\t<Compiler>')
    for o in common_opts():
        w(f'\t\t\t<Add option={quoteattr(o)} />')
    for d in defines:
        # The build-type define is set per target above.
        if d in ("HW_BUILD_FOR_DEBUGGING", "HW_BUILD_FOR_DISTRIBUTION"):
            continue
        w(f'\t\t\t<Add option={quoteattr("-D" + d)} />')
    for inc in includes:
        w(f'\t\t\t<Add directory={quoteattr(r(inc))} />')
    w('\t\t</Compiler>')
    w('\t\t<Linker>')
    for l in libs:
        w(f'\t\t\t<Add option={quoteattr(l)} />')
    w('\t\t</Linker>')

    for s in sorted(set(sources)):
        w(f'\t\t<Unit filename={quoteattr(r(s))}>')
        w('\t\t\t<Option compilerVar="CC" />')
        w('\t\t</Unit>')
    for h in headers:
        w(f'\t\t<Unit filename={quoteattr(r(h))}>')
        w('\t\t\t<Option compile="0" />')
        w('\t\t\t<Option link="0" />')
        w('\t\t</Unit>')
    w('\t</Project>')
    w('</CodeBlocks_project_file>')

    with open(out_path, "w") as f:
        f.write("\n".join(L) + "\n")

    print(f"\nWrote {out_path}")
    print(f"  {len(set(sources))} sources, {len(defines)} defines, {len(includes)} include dirs")
    print("Open it in Code::Blocks and build the Debug or Release target.")


if __name__ == "__main__":
    main()
