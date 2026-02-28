#!/usr/bin/env python3
"""
prepare_windows_build.py  -  v3 (final)
========================================
Run this ONCE from inside the libpff-main directory BEFORE running:
  python setup.py build_ext --inplace

What it does
------------
1. Downloads all 17 missing dependency libraries from GitHub and extracts
   their .c, .h, AND .h.in source files into the correct sub-folders.
2. Generates .h files from every .h.in template found (in all sub-folders,
   common/, and include/libpff/) by substituting autoconf @TOKEN@ values
   with the correct Windows/MSVC values.
3. Writes common/config.h for MSVC.

Requirements: Python 3.7+, internet access.

Usage:
  cd C:\\Users\\<you>\\libpff-main
  python prepare_windows_build.py
  python setup.py build_ext --inplace
"""

import io
import os
import re
import sys
import urllib.request
import zipfile

# ---------------------------------------------------------------------------
# All dependency libraries hosted at https://github.com/libyal/<name>
# ---------------------------------------------------------------------------
DEPENDENCY_LIBS = [
    "libcerror",
    "libcthreads",
    "libcdata",
    "libclocale",
    "libcnotify",
    "libcsplit",
    "libuna",
    "libcfile",
    "libcpath",
    "libbfio",
    "libfcache",
    "libfdata",
    "libfdatetime",
    "libfguid",
    "libfvalue",
    "libfwnt",
    "libfmapi",
]

GITHUB_ZIP_URL = "https://github.com/libyal/{lib}/archive/refs/heads/main.zip"

# Substitution values for all @TOKEN@ placeholders on Windows/MSVC
WIN_SUBS = {
    "@PACKAGE@":                   "libpff",
    "@VERSION@":                   "20250101",
    "@HAVE_WIDE_CHARACTER_TYPE@":  "1",
    "@HAVE_MULTI_THREAD_SUPPORT@": "0",
    "@HAVE_LIBBFIO@":              "0",
    "@HAVE_SYS_TYPES_H@":          "0",
    "@HAVE_INTTYPES_H@":           "0",
    "@HAVE_STDINT_H@":             "1",
    "@HAVE_WCHAR_H@":              "1",
    "@HAVE_SIZE32_T@":             "0",
    "@HAVE_SSIZE32_T@":            "0",
    "@HAVE_SIZE64_T@":             "0",
    "@HAVE_SSIZE64_T@":            "0",
    "@HAVE_OFF64_T@":              "0",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def download_zip(url, lib):
    print(f"  downloading {lib} ...", end=" ", flush=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
        print(f"OK ({len(data)//1024} KB)")
        return data
    except Exception as exc:
        print(f"FAILED: {exc}")
        return b""


def extract_lib_sources(zip_data, lib, dest_dir):
    """
    From a GitHub zip structured as <lib>-main/<lib>/<files>,
    extract ALL .c, .h, and .h.in files into dest_dir.
    """
    os.makedirs(dest_dir, exist_ok=True)
    extracted = 0
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        for member in zf.namelist():
            parts = member.split("/")
            # Want: <lib>-main/<lib>/<filename>  (exactly depth 3)
            if (len(parts) >= 3
                    and parts[1] == lib
                    and parts[-1]
                    and (parts[-1].endswith(".c")
                         or parts[-1].endswith(".h")
                         or parts[-1].endswith(".h.in")
                         or parts[-1] == "Makefile.am")):
                target = os.path.join(dest_dir, parts[-1])
                with zf.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                extracted += 1
    return extracted


def generate_h_from_template(src_path, subs):
    """
    Generate <name>.h from <name>.h.in next to it.
    Applies subs dict then replaces remaining @TOKEN@ with 0.
    """
    dst_path = src_path[:-3]  # strip ".in"
    with open(src_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    for k, v in subs.items():
        content = content.replace(k, v)
    content = re.sub(r"@[A-Za-z0-9_]+@", "0", content)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(content)
    return dst_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    root = os.path.abspath(os.path.dirname(__file__))
    if not os.path.exists(os.path.join(root, "setup.py")):
        root = os.getcwd()
    if not os.path.exists(os.path.join(root, "setup.py")):
        sys.exit("ERROR: Run this script from inside the libpff-main directory.")

    print(f"\n[prepare_windows_build v3] Root: {root}\n")

    # ------------------------------------------------------------------
    # STEP 1: Download and extract all dependency libraries
    # ------------------------------------------------------------------
    print("=" * 62)
    print("STEP 1 -- Downloading + extracting dependency libraries")
    print("=" * 62)

    failed = []
    for lib in DEPENDENCY_LIBS:
        dest = os.path.join(root, lib)
        if os.path.isdir(dest) and any(f.endswith(".c") for f in os.listdir(dest)):
            # Check if we also have .h.in files (v2 skipped them)
            has_h_in = any(f.endswith(".h.in") for f in os.listdir(dest))
            if has_h_in:
                print(f"  {lib}: already complete, skipping")
                continue
            else:
                print(f"  {lib}: re-downloading (missing .h.in files from previous run)")

        url = GITHUB_ZIP_URL.format(lib=lib)
        zip_data = download_zip(url, lib)
        if not zip_data:
            failed.append(lib)
            continue
        n = extract_lib_sources(zip_data, lib, dest)
        print(f"  {lib}: extracted {n} files -> {dest}")
        if n == 0:
            failed.append(lib)

    if failed:
        print(f"\nERROR: Failed to download/extract: {', '.join(failed)}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # STEP 2: Generate ALL .h files from .h.in templates
    #         - in every dependency lib subfolder
    #         - in common/
    #         - in include/libpff/
    # ------------------------------------------------------------------
    print("\n" + "=" * 62)
    print("STEP 2 -- Generating .h files from .h.in templates")
    print("=" * 62)

    generated = 0

    # Scan: all lib subdirs + common + include/libpff
    scan_dirs = [os.path.join(root, lib) for lib in DEPENDENCY_LIBS + ["libpff"]]
    scan_dirs += [
        os.path.join(root, "common"),
        os.path.join(root, "include", "libpff"),
        os.path.join(root, "include"),
    ]

    for scan_dir in scan_dirs:
        if not os.path.isdir(scan_dir):
            continue
        for fname in os.listdir(scan_dir):
            if not fname.endswith(".h.in"):
                continue
            src = os.path.join(scan_dir, fname)
            dst = generate_h_from_template(src, WIN_SUBS)
            print(f"  generated: {dst}")
            generated += 1

    print(f"\n  Total generated: {generated} header files")

    # ------------------------------------------------------------------
    # STEP 3: Generate setup.cfg from setup.cfg.in
    # ------------------------------------------------------------------
    print("\n" + "=" * 62)
    print("STEP 3 -- Generating setup.cfg")
    print("=" * 62)
    setup_cfg_in = os.path.join(root, "setup.cfg.in")
    setup_cfg    = os.path.join(root, "setup.cfg")
    if os.path.exists(setup_cfg_in):
        with open(setup_cfg_in, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("@VERSION@", "20250101")
        content = re.sub(r"@[A-Za-z0-9_]+@", "0", content)
        with open(setup_cfg, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  written: {setup_cfg}")
    else:
        # Write a minimal one if .in is missing
        with open(setup_cfg, "w", encoding="utf-8") as f:
            f.write("[metadata]\nname = pypff\nversion = 20250101\n")
        print(f"  written (minimal): {setup_cfg}")

    # ------------------------------------------------------------------
    # STEP 4: Generate common/config.h for MSVC
    # ------------------------------------------------------------------
    print("\n" + "=" * 62)
    print("STEP 4 -- Writing common/config.h")
    print("=" * 62)
    config_h = os.path.join(root, "common", "config.h")
    with open(config_h, "w", encoding="utf-8") as f:
        f.write("""\
/* config.h - Windows/MSVC minimal configuration
 * Generated by prepare_windows_build.py v3 */
#ifndef CONFIG_H
#define CONFIG_H

#define WINAPI_USE_PREFIXED_FUNCTIONS   1
#define HAVE_WIDE_CHARACTER_TYPE        1
#define HAVE_WCHAR_H                    1
#define HAVE_STDINT_H                   1
#define HAVE_STRING_H                   1
#define HAVE_MEMORY_H                   1
#define HAVE_STDLIB_H                   1
#define HAVE_SYS_TYPES_H                0
#define HAVE_INTTYPES_H                 0
#define HAVE_UNISTD_H                   0
#define HAVE_OFF64_T                    0
#define HAVE_SIZE32_T                   0
#define HAVE_SSIZE32_T                  0
#define HAVE_SIZE64_T                   0
#define HAVE_SSIZE64_T                  0
#define HAVE_PRINTF_JD                  0
#define HAVE_PRINTF_ZD                  0
#define HAVE_PTHREAD_H                  0
#define HAVE_LOCAL_LIBCERROR            1

#endif /* CONFIG_H */
""")
    print(f"  written: {config_h}")

    # ------------------------------------------------------------------
    # STEP 4: Verify everything is in place
    # ------------------------------------------------------------------
    print("\n" + "=" * 62)
    print("STEP 5 -- Verification")
    print("=" * 62)

    all_ok = True

    for lib in DEPENDENCY_LIBS + ["libpff"]:
        d = os.path.join(root, lib)
        c_count  = len([f for f in os.listdir(d) if f.endswith(".c")]) if os.path.isdir(d) else 0
        ok = c_count > 0
        if not ok:
            all_ok = False
        print(f"  [{'OK' if ok else 'MISSING'}] {lib}/ -- {c_count} .c files")

    for path in [
        os.path.join(root, "common", "types.h"),
        os.path.join(root, "common", "config.h"),
        os.path.join(root, "include", "libpff", "types.h"),
        os.path.join(root, "include", "libpff", "features.h"),
        os.path.join(root, "include", "libpff", "definitions.h"),
        os.path.join(root, "libpff",  "libpff_definitions.h"),
    ]:
        ok = os.path.exists(path)
        if not ok:
            all_ok = False
        print(f"  [{'OK' if ok else 'MISSING'}] {path}")

    if all_ok:
        print("""
==============================================================
  Ready! Now run (in this same command prompt window):

    python setup.py build_ext --inplace

  or:
    pip install .
==============================================================
""")
    else:
        print("\n[ERROR] Some files are still missing. See above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
