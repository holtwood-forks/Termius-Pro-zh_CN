#!/usr/bin/env python3
"""Read-only rule coverage report for the installed Termius app.asar.

Extracts app.asar to a temporary directory, applies the selected rules in
memory, and writes extract/rule-report.txt + extract/unmatched-rules.txt.
Termius itself is never modified.
"""
import argparse
import logging
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import lang  # noqa: E402
import fontlang  # noqa: E402
from logger import setup_logging  # noqa: E402


class ReportModifier(fontlang.FontTermiusModifier):
    """把解包目录指向临时目录，并禁用字体文件写入"""

    def __init__(self, termius_path, args, app_dir):
        super().__init__(termius_path, args)
        self._report_app_dir = app_dir

    @property
    def _app_dir(self):
        return self._report_app_dir

    def apply_fonts(self):
        pass


def analyze(modifier):
    """在内存中应用规则，返回 (files, rules, matched, unmatched, errors)"""
    files = modifier.collect_code_files()
    matched = set()
    errors = []
    for path in files:
        try:
            content = lang.read_file(path, strip_empty=False)
            _, hits = modifier.replace_content(content)
            matched |= hits
        except Exception as exc:
            errors.append((path, repr(exc)))
    rules = [line for _, line, _, _ in modifier.compiled_rules]
    unmatched = [line for line in rules if line not in matched]
    return files, rules, matched, unmatched, errors


def write_report(report_path, unmatched_path, version, files, rules, unmatched, errors):
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as file:
        file.write(f"# Termius version: {version or 'unknown'}\n")
        file.write(f"# files: {len(files)}\n")
        file.write(f"# rules: {len(rules) - len(unmatched)}/{len(rules)} matched\n")
        file.write(f"# read errors: {len(errors)}\n")
    with open(unmatched_path, "w", encoding="utf-8") as file:
        file.write(f"# unmatched rules: {len(unmatched)}/{len(rules)}\n")
        if unmatched:
            file.write("\n".join(unmatched) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only rule coverage report for Termius.")
    parser.add_argument("-b", "--beta", action="store_true", help="Operate on Termius Beta.")
    parser.add_argument("-l", "--localize", action="store_true", help="Check localization rules.")
    parser.add_argument("-t", "--trial", action="store_true", help="Check trial rules.")
    parser.add_argument("-k", "--skip-login", action="store_true", help="Check skip-login rules.")
    parser.add_argument("-s", "--style", action="store_true", help="Check style rules.")
    parser.add_argument("-p", "--path", help="Termius resources directory (contains app.asar).")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when rules do not match or files fail to read.")
    parser.add_argument("-v", "--verbose", type=lambda s: s.upper(), dest="log_level",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO")
    args = parser.parse_args(argv)

    if not any((args.localize, args.trial, args.skip_login, args.style)):
        args.localize = True
    setup_logging(args.log_level)

    if args.path:
        termius_path = lang.resolve_resources_dir(args.path)
        if not termius_path:
            logging.error(f"app.asar not found under: {args.path}")
            return 1
    else:
        termius_path = lang.get_termius_path(args.beta)

    asar_path = os.path.join(termius_path, "app.asar")
    version = None
    with tempfile.TemporaryDirectory() as temp_dir:
        app_dir = os.path.join(temp_dir, "app")
        lang.run_command([lang.get_asar_cmd(), "extract", asar_path, app_dir])
        modifier = ReportModifier(termius_path, args, app_dir)
        version = modifier._asar_version(asar_path)
        modifier.load_rules()
        files, rules, matched, unmatched, errors = analyze(modifier)

    extract_dir = os.path.join(ROOT, "extract")
    report_path = os.path.join(extract_dir, "rule-report.txt")
    unmatched_path = os.path.join(extract_dir, "unmatched-rules.txt")
    write_report(report_path, unmatched_path, version, files, rules, unmatched, errors)

    logging.info(f"Termius version: {version or 'unknown'}")
    logging.info(f"Files scanned: {len(files)}")
    logging.info(f"Rules matched: {len(rules) - len(unmatched)}/{len(rules)}")
    logging.info(f"Unmatched rules: {len(unmatched)} (see {unmatched_path})")
    if errors:
        logging.warning(f"Files that could not be read: {len(errors)}")
    for line in unmatched[:20]:
        logging.info(f"  unmatched: {line}")
    if len(unmatched) > 20:
        logging.info(f"  ... {len(unmatched) - 20} more in {unmatched_path}")

    if args.strict and (unmatched or errors):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
