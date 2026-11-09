#!/usr/bin/env python3
"""Read-only verification for a generated app.asar before publishing.

Checks that the archive is listable and, for font builds, that every font,
license and the CSS @font-face marker are actually present. It does not need
an installed Termius or backup metadata.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import lang  # noqa: E402
from logger import setup_logging  # noqa: E402

FONT_EXTENSIONS = (".ttf", ".otf", ".woff2")
FONT_LICENSES = ("OFL-1.1.txt", "NOTICE.md")
CSS_MARKER = "CodeNewRoman Nerd Font Mono"


def asar_list(asar_path):
    try:
        result = subprocess.run(
            [lang.get_asar_cmd(), "list", asar_path],
            check=True, capture_output=True, text=True,
        )
        return result.stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def extract_file(asar_path, inner_path):
    # subprocess 的 cwd 会切到临时目录；相对 asar 路径必须先转成绝对路径。
    asar_path = os.path.abspath(asar_path)
    # @electron/asar 在 Windows 上要求内部路径使用反斜杠，list 输出则是正斜杠。
    extract_path = inner_path.replace("/", os.sep)
    basename = os.path.basename(extract_path)
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess.run(
                [lang.get_asar_cmd(), "extract-file", asar_path, extract_path],
                cwd=temp_dir, check=True, capture_output=True, text=True,
            )
            for root, _, files in os.walk(temp_dir):
                if basename in files:
                    with open(os.path.join(root, basename), "r", encoding="utf-8") as file:
                        return file.read()
            return None
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def expected_font_files():
    fonts_dir = os.path.join(ROOT, "fonts")
    if not os.path.isdir(fonts_dir):
        return []
    names = [
        name for name in os.listdir(fonts_dir)
        if name.lower().endswith(FONT_EXTENSIONS)
    ]
    names += [name for name in FONT_LICENSES if os.path.isfile(os.path.join(fonts_dir, name))]
    return names


def css_entries(listing):
    entries = []
    for line in listing.splitlines():
        normalized = line.replace("\\", "/").lstrip("/")
        if re.search(r"ui-process/assets/main-[^/]+\.css$", normalized):
            entries.append(normalized)
    return entries


def verify(asar_path, listing=None, require_fonts=False, css_reader=None):
    checks = []
    if listing is None:
        listing = asar_list(asar_path)
    if listing is None or not listing.strip():
        return [{"name": "asar_readable", "status": "fail", "detail": "asar list failed or empty"}]

    checks.append({
        "name": "asar_readable",
        "status": "ok",
        "detail": f"{len(listing.splitlines())} entries",
    })
    if not require_fonts:
        return checks

    expected = expected_font_files()
    font_files = [name for name in expected if name.lower().endswith(FONT_EXTENSIONS)]
    if not font_files:
        checks.append({
            "name": "fonts_packed",
            "status": "fail",
            "detail": "no font files found under fonts/",
        })
        return checks
    missing = [name for name in expected if name not in listing]
    if missing:
        checks.append({
            "name": "fonts_packed",
            "status": "fail",
            "detail": "missing: " + ", ".join(missing),
        })
    else:
        checks.append({
            "name": "fonts_packed",
            "status": "ok",
            "detail": f"{len(expected)} files",
        })

    paths = css_entries(listing)
    if not paths:
        checks.append({"name": "css_marker", "status": "fail", "detail": "main-*.css not found"})
        return checks
    reader = css_reader or extract_file
    unreadable = []
    for path in paths:
        content = reader(asar_path, path)
        if content is None:
            unreadable.append(path)
            continue
        if CSS_MARKER in content:
            checks.append({"name": "css_marker", "status": "ok", "detail": path})
            break
    else:
        if unreadable:
            detail = "cannot extract: " + ", ".join(unreadable)
        else:
            detail = "marker missing in: " + ", ".join(paths)
        checks.append({"name": "css_marker", "status": "fail", "detail": detail})
    return checks


def render_text(asar_path, checks):
    lines = [f"asar: {asar_path}"]
    labels = {"ok": "OK", "fail": "FAIL"}
    for item in checks:
        lines.append(f"[{labels[item['status']]:4}] {item['name']}: {item['detail']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify a generated app.asar before publishing.")
    parser.add_argument("asar", help="Path to the generated app.asar.")
    parser.add_argument("--fonts", action="store_true", help="Require all fonts, licenses and CSS marker.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("-v", "--verbose", type=lambda s: s.upper(), dest="log_level",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO")
    args = parser.parse_args(argv)
    setup_logging(args.log_level)

    checks = verify(args.asar, require_fonts=args.fonts)
    if args.json:
        print(json.dumps({"asar": args.asar, "checks": checks}, ensure_ascii=False, indent=2))
    else:
        print(render_text(args.asar, checks))
    return 1 if any(item["status"] == "fail" for item in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
