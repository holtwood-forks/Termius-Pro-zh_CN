#!/usr/bin/env python3
"""Read-only post-patch verification for the installed Termius app.asar.

Checks that the asar is readable, the version and metadata still match the
backup, the configured fonts/licenses are packed, the injected CSS marker
exists, and the latest rule report is consistent.
"""
import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import lang  # noqa: E402
import fontlang  # noqa: E402
from logger import setup_logging  # noqa: E402
from tools.status import read_report  # noqa: E402


def asar_listing(asar_path):
    try:
        result = subprocess.run(
            [lang.get_asar_cmd(), "list", asar_path],
            check=True, capture_output=True, text=True,
        )
        return result.stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def asar_extract_file(asar_path, inner_path):
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
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None
    return None


def check(name, status, detail):
    return {"name": name, "status": status, "detail": detail}


def verify(termius_path, modifier, listing, fonts_dir=None, css_reader=None, report=None, check_fonts=True):
    asar_path = os.path.join(termius_path, "app.asar")
    backup_path = asar_path + ".bak"
    result = {"version": None, "backup_version": None, "checks": []}
    checks = result["checks"]

    if not os.path.exists(asar_path):
        checks.append(check("app_asar_exists", "fail", "app.asar not found"))
        return result
    checks.append(check("app_asar_exists", "ok", asar_path))

    if listing is None:
        checks.append(check("asar_readable", "fail", "asar list failed"))
        return result
    checks.append(check("asar_readable", "ok", f"{len(listing.splitlines())} entries"))

    result["version"] = modifier._asar_version(asar_path)
    result["backup_version"] = modifier._asar_version(backup_path) if os.path.exists(backup_path) else None
    if result["version"]:
        checks.append(check("version", "ok", result["version"]))
    else:
        checks.append(check("version", "warn", "cannot read package.json version"))
    if result["backup_version"]:
        if result["version"] and result["version"] != result["backup_version"]:
            checks.append(check(
                "version_matches_backup", "fail",
                f"backup {result['backup_version']} != installed {result['version']}",
            ))
        else:
            checks.append(check("version_matches_backup", "ok", result["backup_version"]))
    else:
        checks.append(check("version_matches_backup", "warn", "backup missing"))

    try:
        current_hash = modifier._file_sha256(asar_path)
    except OSError:
        current_hash = None
    meta_path = backup_path + ".json"
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as file:
                meta = json.load(file)
        except (OSError, ValueError):
            meta = {}
        expected = meta.get("patched_sha256")
        if expected and expected == current_hash:
            checks.append(check("meta_matches_asar", "ok", "app.asar.bak.json matches"))
        elif expected:
            checks.append(check("meta_matches_asar", "fail", "app.asar changed after patching"))
        else:
            checks.append(check("meta_matches_asar", "warn", "meta has no patched_sha256"))
    else:
        checks.append(check("meta_matches_asar", "warn", "app.asar.bak.json missing"))

    if not check_fonts:
        checks.append(check("fonts_packed", "skip", "--no-fonts"))
        checks.append(check("css_marker", "skip", "--no-fonts"))
    else:
        fonts_dir = fonts_dir or os.path.join(ROOT, "fonts")
        if os.path.isdir(fonts_dir):
            font_files = [
                name for name in os.listdir(fonts_dir)
                if name.lower().endswith((".ttf", ".otf", ".woff2"))
            ]
            expected = list(font_files)
            expected += [name for name in ("OFL-1.1.txt", "NOTICE.md")
                         if os.path.isfile(os.path.join(fonts_dir, name))]
            missing = [name for name in expected if name not in listing]
            if not font_files:
                checks.append(check("fonts_packed", "fail", "no font files under fonts/"))
            elif missing:
                checks.append(check("fonts_packed", "fail", "missing: " + ", ".join(missing)))
            else:
                checks.append(check("fonts_packed", "ok", f"{len(expected)} files"))
        else:
            checks.append(check("fonts_packed", "skip", "fonts/ not found"))

        css_lines = [
            line.lstrip("/") for line in listing.splitlines()
            if re.search(r"ui-process/assets/main-[^/]+\.css$", line)
        ]
        if not css_lines:
            checks.append(check("css_marker", "warn", "ui-process/assets/main-*.css not found"))
        elif css_reader is None:
            checks.append(check("css_marker", "warn", "css reader not available"))
        else:
            # 不同版本的资源哈希不同，main-*.css 可能不止一个；任意一个带标记即可。
            marker = "CodeNewRoman Nerd Font Mono"
            matched = None
            unreadable = []
            for css_path in css_lines:
                content = css_reader(asar_path, css_path)
                if content is None:
                    unreadable.append(css_path)
                    continue
                if marker in content:
                    matched = css_path
                    break
            if matched:
                checks.append(check("css_marker", "ok", matched))
            elif unreadable:
                checks.append(check(
                    "css_marker", "fail",
                    "cannot extract: " + ", ".join(unreadable),
                ))
            else:
                checks.append(check(
                    "css_marker", "fail",
                    "font marker missing in: " + ", ".join(css_lines),
                ))

    if report is None:
        report = read_report(
            os.path.join(ROOT, "extract", "rule-report.txt"),
            os.path.join(ROOT, "extract", "unmatched-rules.txt"),
        )
    if not report:
        checks.append(check("rule_report", "warn", "no rule report (run tools/report_rules.py or fontlang.py)"))
    elif report.get("version") and result["version"] and report["version"] != result["version"]:
        checks.append(check(
            "rule_report", "warn",
            f"report is for {report['version']}, installed {result['version']}",
        ))
    elif report.get("unmatched", 0):
        checks.append(check("rule_report", "warn", f"{report['unmatched']} unmatched rules"))
    elif report.get("matched") is not None:
        checks.append(check("rule_report", "ok", f"{report['matched']}/{report.get('total', '?')} matched"))
    else:
        checks.append(check("rule_report", "warn", "report is incomplete"))

    return result


def render_text(result):
    lines = [
        f"Termius version : {result['version'] or 'unknown'}",
        f"backup version  : {result['backup_version'] or 'unknown'}",
    ]
    labels = {"ok": "OK", "warn": "WARN", "fail": "FAIL", "skip": "SKIP"}
    for item in result["checks"]:
        lines.append(f"[{labels[item['status']]:4}] {item['name']}: {item['detail']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only post-patch verification for Termius.")
    parser.add_argument("-b", "--beta", action="store_true", help="Operate on Termius Beta.")
    parser.add_argument("-p", "--path", help="Termius resources directory (contains app.asar).")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on warnings as well as failures.")
    parser.add_argument("--no-fonts", action="store_true",
                        help="Skip font/license/CSS checks for a non-font build.")
    parser.add_argument("-v", "--verbose", type=lambda s: s.upper(), dest="log_level",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO")
    args = parser.parse_args(argv)
    setup_logging(args.log_level)

    if args.path:
        termius_path = lang.resolve_resources_dir(args.path)
        if not termius_path:
            logging.error(f"app.asar not found under: {args.path}")
            return 1
    else:
        termius_path = lang.get_termius_path(args.beta)

    modifier = fontlang.FontTermiusModifier(termius_path, SimpleNamespace(beta=args.beta, style=False))
    asar_path = os.path.join(termius_path, "app.asar")
    listing = asar_listing(asar_path) if os.path.exists(asar_path) else None
    result = verify(
        termius_path, modifier, listing, css_reader=asar_extract_file,
        check_fonts=not args.no_fonts,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_text(result))

    statuses = {item["status"] for item in result["checks"]}
    if "fail" in statuses or (args.strict and "warn" in statuses):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
