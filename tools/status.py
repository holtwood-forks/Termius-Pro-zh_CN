#!/usr/bin/env python3
"""Show the local Termius patch status without modifying anything.

Reports the installed version, whether app.asar is original/patched/unknown,
backup and metadata state, whether fonts are packed in, and the latest rule
report summary.
"""
import argparse
import json
import logging
import os
import subprocess
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import lang  # noqa: E402
import fontlang  # noqa: E402
from logger import setup_logging  # noqa: E402


def asar_listing(asar_path):
    try:
        result = subprocess.run(
            [lang.get_asar_cmd(), "list", asar_path],
            check=True, capture_output=True, text=True,
        )
        return result.stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def read_report(report_path, unmatched_path):
    report = {}
    try:
        for line in open(report_path, "r", encoding="utf-8"):
            line = line.rstrip("\n")
            if line.startswith("# Termius version: "):
                report["version"] = line.split(": ", 1)[1]
            elif line.startswith("# rules: "):
                matched, total = line.split(": ", 1)[1].split(" ", 1)[0].split("/")
                report["matched"] = int(matched)
                report["total"] = int(total)
            elif line.startswith("# read errors: "):
                report["read_errors"] = int(line.split(": ", 1)[1])
    except (OSError, ValueError):
        pass
    try:
        first = open(unmatched_path, "r", encoding="utf-8").readline().strip()
        if first.startswith("# unmatched rules: "):
            report["unmatched"] = int(first.split(": ", 1)[1].split("/", 1)[0])
    except (OSError, ValueError):
        pass
    return report


def collect_status(termius_path, modifier, listing=None):
    asar_path = os.path.join(termius_path, "app.asar")
    backup_path = asar_path + ".bak"
    meta_path = backup_path + ".json"

    status = {
        "termius_path": termius_path,
        "version": None,
        "app_asar": {"exists": os.path.exists(asar_path), "state": "missing"},
        "backup": {"exists": os.path.exists(backup_path)},
        "backup_old": {"exists": os.path.exists(backup_path + ".old")},
        "meta": {"exists": os.path.exists(meta_path)},
        "fonts": {"injected": None if listing is None else "CodeNewRomanNerdFontMono-Regular.otf" in listing},
        "report": read_report(
            os.path.join(ROOT, "extract", "rule-report.txt"),
            os.path.join(ROOT, "extract", "unmatched-rules.txt"),
        ),
    }

    if not status["app_asar"]["exists"]:
        return status

    status["version"] = modifier._asar_version(asar_path)
    current_hash = modifier._file_sha256(asar_path)
    status["app_asar"].update({
        "size": os.path.getsize(asar_path),
        "sha256": current_hash,
    })

    backup_hash = None
    if status["backup"]["exists"]:
        backup_hash = modifier._file_sha256(backup_path)
        status["backup"].update({
            "size": os.path.getsize(backup_path),
            "version": modifier._asar_version(backup_path),
            "sha256": backup_hash,
        })

    meta = {}
    if status["meta"]["exists"]:
        try:
            with open(meta_path, "r", encoding="utf-8") as file:
                meta = json.load(file)
        except (OSError, ValueError):
            meta = {}
        status["meta"].update({
            "patched_sha256": meta.get("patched_sha256"),
        })

    if backup_hash and current_hash == backup_hash:
        status["app_asar"]["state"] = "original"
    elif meta.get("patched_sha256") and current_hash == meta["patched_sha256"]:
        status["app_asar"]["state"] = "patched"
    else:
        status["app_asar"]["state"] = "unknown"

    return status


def render_text(status):
    state = status["app_asar"]["state"]
    state_text = {
        "original": "原版（与备份一致）",
        "patched": "已打补丁（与 app.asar.bak.json 一致）",
        "unknown": "未知（既不是备份，也不是上次打包产物）",
        "missing": "未找到 app.asar",
    }[state]
    lines = [
        f"Termius version : {status['version'] or 'unknown'}",
        f"app.asar         : {state_text}",
    ]
    if status["backup"]["exists"]:
        lines.append(
            f"backup          : {status['backup'].get('version') or 'unknown'}"
            f"（{status['backup'].get('size', 0) / 1024 / 1024:.1f} MB）"
        )
    else:
        lines.append("backup          : 无")
    lines.append(f"backup.old      : {'有' if status['backup_old']['exists'] else '无'}")
    fonts = status["fonts"]["injected"]
    lines.append(f"fonts           : {'已注入' if fonts else '未注入' if fonts is False else '未知'}")
    report = status["report"]
    if report:
        lines.append(
            f"last report     : {report.get('version', 'unknown')}, "
            f"{report.get('matched', '?')}/{report.get('total', '?')} matched, "
            f"{report.get('unmatched', '?')} unmatched"
        )
    else:
        lines.append("last report     : 无（可运行 python tools/report_rules.py）")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Show Termius patch status without modifying anything.")
    parser.add_argument("-b", "--beta", action="store_true", help="Operate on Termius Beta.")
    parser.add_argument("-p", "--path", help="Termius resources directory (contains app.asar).")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when app.asar is missing or unknown.")
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
    status = collect_status(termius_path, modifier, listing)

    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(render_text(status))

    if args.strict and status["app_asar"]["state"] in ("missing", "unknown"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
