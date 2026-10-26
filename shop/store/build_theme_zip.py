#!/usr/bin/env python3
"""Build shopify-theme.zip, the manual-upload fallback for the Dawn Dropship theme.

    python build_theme_zip.py ciel-site-shopify-theme.zip         # GitHub "Download ZIP" of the branch
    python build_theme_zip.py path/to/theme-folder -o theme.zip   # a folder
    python build_theme_zip.py SOURCE --no-license

SOURCE is a zip or a folder. The script finds the folder that holds layout/theme.liquid
(GitHub wraps a download in one extra folder), keeps the seven Shopify theme folders and
Dawn's LICENSE.md, and drops everything else (.git, .github, node_modules, README, Mac and
Windows leftovers). The zip it writes has the theme folders at its root. Same content in,
same bytes out.

Exit code 0 means the zip was written, 1 means the theme is incomplete or a JSON file is
broken, 2 means the input could not be read or is unsafe (path escape, symlink, duplicate
name, too many files).

// FILL: whether Shopify's uploader accepts LICENSE.md at the zip root. Dawn's license asks
// that its notice travel with copies, so the zip keeps it. If the upload is refused, rebuild
// with --no-license.

Stdlib only. Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import zipfile
from typing import Dict, Iterable, List, Optional

THEME_DIRS = ("assets", "config", "layout", "locales", "sections", "snippets", "templates")
OPTIONAL_DIRS = ("blocks",)
LICENSE = "LICENSE.md"
MARKER = "layout/theme.liquid"
EXCLUDED_NAMES = {".git", ".github", "node_modules", "__MACOSX", ".DS_Store", "Thumbs.db", "desktop.ini"}
JSON_DIRS = ("config/", "locales/", "sections/", "templates/")
MAX_FILES = 20000
MAX_TOTAL_BYTES = 200 * 1024 * 1024
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


class ThemeError(Exception):
    """The input is readable but is not a complete theme (exit 1)."""


class InputError(Exception):
    """The input cannot be read or is unsafe (exit 2)."""


def normalise(name: str) -> str:
    """Return a clean relative POSIX path, or raise InputError for anything that could escape."""
    if "\x00" in name:
        raise InputError(f"unsafe path (NUL byte): {name!r}")
    path = name.replace("\\", "/")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise InputError(f"unsafe path (absolute): {name!r}")
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise InputError(f"unsafe path (..): {name!r}")
    return "/".join(parts)


def is_excluded(path: str) -> bool:
    parts = path.split("/")
    return any(p in EXCLUDED_NAMES for p in parts) or parts[-1].startswith("._")


def strip_json_comments(text: str) -> str:
    """Drop /* block */ and // line comments outside strings. Shopify allows both in theme JSON.

    Newlines inside a block comment are kept so parse errors still point at the right line.
    """
    out: List[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i : j + 1])
            i = j + 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end == -1:
                raise ValueError("unterminated /* comment")
            out.append("\n" * text.count("\n", i, end))
            i = end + 2
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end == -1 else end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def read_dir(root: str) -> Dict[str, bytes]:
    files: Dict[str, bytes] = {}
    total = 0
    for here, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_NAMES)
        for d in dirs:
            if os.path.islink(os.path.join(here, d)):
                raise InputError(f"symlink not allowed: {os.path.relpath(os.path.join(here, d), root)}")
        for name in sorted(names):
            full = os.path.join(here, name)
            rel = normalise(os.path.relpath(full, root))
            if is_excluded(rel):
                continue
            if os.path.islink(full):
                raise InputError(f"symlink not allowed: {rel}")
            total += os.path.getsize(full)
            if len(files) + 1 > MAX_FILES or total > MAX_TOTAL_BYTES:
                raise InputError("too many or too large files; this is not a theme folder")
            with open(full, "rb") as handle:
                files[rel] = handle.read()
    return files


def read_zip(path: str) -> Dict[str, bytes]:
    files: Dict[str, bytes] = {}
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_TOTAL_BYTES:
            raise InputError("too many or too large files; this is not a theme zip")
        for info in infos:
            rel = normalise(info.filename)
            if info.filename.endswith(("/", "\\")) or not rel or is_excluded(rel):
                continue
            if info.create_system == 3 and stat.S_ISLNK(info.external_attr >> 16):
                raise InputError(f"symlink not allowed: {info.filename}")
            if rel in files:
                raise InputError(f"duplicate entry: {rel}")
            files[rel] = zf.read(info)
    return files


def read_source(source: str) -> Dict[str, bytes]:
    if os.path.isdir(source):
        return read_dir(source)
    if os.path.isfile(source):
        if not zipfile.is_zipfile(source):
            raise InputError(f"not a zip file or a folder: {source}")
        return read_zip(source)
    raise InputError(f"no such file or folder: {source}")


def find_root(paths: Iterable[str]) -> str:
    """Return the prefix (empty or ending in '/') in front of layout/theme.liquid; shallowest wins."""
    roots = []
    for p in paths:
        if p == MARKER:
            roots.append("")
        elif p.endswith("/" + MARKER):
            roots.append(p[: -len(MARKER)])
    if not roots:
        raise ThemeError(
            f"{MARKER} not found. Point SOURCE at the shopify-theme branch (or its download), "
            "not the kit branch."
        )
    roots.sort(key=lambda r: (r.count("/"), r))
    ties = [r for r in roots if r.count("/") == roots[0].count("/")]
    if len(ties) > 1:
        raise ThemeError("more than one theme found: " + ", ".join(repr(r) for r in ties))
    return roots[0]


def select(files: Dict[str, bytes], root: str, keep_license: bool) -> Dict[str, bytes]:
    keep: Dict[str, bytes] = {}
    for path, data in files.items():
        if not path.startswith(root):
            continue
        rel = path[len(root) :]
        top = rel.split("/", 1)[0]
        if "/" in rel and top in THEME_DIRS + OPTIONAL_DIRS:
            keep[rel] = data
        elif rel == LICENSE and keep_license:
            keep[rel] = data
    return keep


def validate(files: Dict[str, bytes]) -> List[str]:
    problems: List[str] = []
    for folder in THEME_DIRS:
        if not any(p.startswith(folder + "/") for p in files):
            problems.append(f"missing or empty folder: {folder}/")
    if "config/settings_schema.json" not in files:
        problems.append("missing file: config/settings_schema.json")
    if "templates/index.json" not in files and "templates/index.liquid" not in files:
        problems.append("missing file: templates/index.json")
    if not any(re.fullmatch(r"locales/[^/]+\.default\.json", p) for p in files):
        problems.append("missing default locale: locales/en.default.json")
    layout = files.get(MARKER, b"").decode("utf-8", "replace")
    for token in ("content_for_header", "content_for_layout"):
        if MARKER in files and token not in layout:
            problems.append(f"{MARKER} is missing {token}")
    for path in sorted(files):
        if path.endswith(".json") and path.startswith(JSON_DIRS):
            try:
                json.loads(strip_json_comments(files[path].decode("utf-8-sig")))
            except (UnicodeDecodeError, ValueError) as exc:
                problems.append(f"invalid JSON: {path}: {exc}")
    return problems


def write_zip(path: str, files: Dict[str, bytes]) -> None:
    tmp = path + ".part"
    try:
        with zipfile.ZipFile(tmp, "w") as zf:
            for name in sorted(files):
                info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                zf.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def check_output(source: str, out: str) -> None:
    folder = os.path.dirname(os.path.abspath(out))
    if not os.path.isdir(folder):
        raise InputError(f"output folder does not exist: {folder}")
    if os.path.isdir(source):
        real_src, real_out = os.path.realpath(source), os.path.realpath(out)
        try:
            inside = os.path.commonpath([real_src, real_out]) == real_src
        except ValueError:  # different drives on Windows
            inside = False
        if inside:
            raise InputError("output file is inside the theme folder; choose another -o path")
    elif os.path.exists(out) and os.path.samefile(source, out):
        raise InputError("output file is the same as the input zip; choose another -o path")


def top_names(paths: Iterable[str]) -> set:
    return {p.split("/", 1)[0] for p in paths}


def summary(out: str, files: Dict[str, bytes], dropped: List[str]) -> str:
    counts: Dict[str, int] = {}
    for p in files:
        top = p.split("/", 1)[0]
        counts[top] = counts.get(top, 0) + 1
    size = os.path.getsize(out)
    lines = [
        f"wrote {out}: {len(files)} files, {size / 1024 / 1024:.1f} MB",
        "  " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())),
    ]
    if dropped:
        shown = ", ".join(dropped[:8]) + (" ..." if len(dropped) > 8 else "")
        lines.append(f"  left out (not theme files): {shown}")
    return "\n".join(lines)


def build(source: str, out: str, keep_license: bool) -> str:
    check_output(source, out)
    files = read_source(source)
    root = find_root(files)
    theme = select(files, root, keep_license)
    problems = validate(theme)
    if problems:
        raise ThemeError("\n".join(problems))
    write_zip(out, theme)
    seen = top_names(p[len(root) :] for p in files if p.startswith(root))
    return summary(out, theme, sorted(seen - top_names(theme)))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build shopify-theme.zip from the theme folder or a GitHub download.")
    parser.add_argument("source", help="theme folder, or the zip downloaded from GitHub")
    parser.add_argument("-o", "--out", default="shopify-theme.zip", help="output zip (default: shopify-theme.zip)")
    parser.add_argument("--no-license", action="store_true", help="leave LICENSE.md out of the zip")
    args = parser.parse_args(argv)
    try:
        print(build(args.source, args.out, not args.no_license))
    except ThemeError as exc:
        print(f"problems:\n{exc}")
        return 1
    except (InputError, OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
