#!/usr/bin/env python3
"""Static checks for rules/*.txt.

Rules are applied in file order and plain rules use str.replace(), so a broad
rule that appears before a narrower one silently makes the narrower rule dead.
This linter enforces the "specific before generic" invariant and validates the
rule format before a release build.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Matches lang.TermiusModifier.load_rules order, with font.txt appended by fontlang.py.
LOAD_ORDER = ("skip_login.txt", "trial.txt", "style.txt", "localize.txt", "font.txt")
MIN_SHADOW_LENGTH = 4


def is_comment(line: str) -> bool:
    return line.strip().startswith("#")


def iter_rule_files(paths):
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for name in LOAD_ORDER:
                candidate = path / name
                if candidate.is_file():
                    yield candidate
        elif path.is_file():
            yield path
        else:
            raise FileNotFoundError(path)


def load_rules(paths):
    rules = []
    for path in iter_rule_files(paths):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or is_comment(line):
                continue
            rules.append((path, line_no, line))
    return rules


def check(paths):
    """Return (errors, warnings, parsed_count)."""
    errors = []
    warnings = []
    parsed = []

    for path, line_no, line in load_rules(paths):
        where = f"{path}:{line_no}"
        if "|" not in line:
            errors.append(f"{where}: missing '|' separator: {line}")
            continue
        old, new = line.split("|", 1)
        if not old:
            errors.append(f"{where}: empty search text")
            continue
        if not new:
            warnings.append(f"{where}: empty replacement deletes the matched text")
        if old == new:
            warnings.append(f"{where}: replacement is identical to search text")

        if old.startswith("/") and old.endswith("/"):
            if "//" in old:
                errors.append(f"{where}: '//' makes lang.is_regex_pattern treat this as plain text: {old}")
                continue
            try:
                pattern = re.compile(old[1:-1])
            except re.error as exc:
                errors.append(f"{where}: invalid regex ({exc}): {old}")
                continue
            parsed.append((path, line_no, old, new, pattern))
        else:
            if old.startswith("/") and any(ch in old for ch in "\\[](){}*+?^$"):
                warnings.append(
                    f"{where}: starts with '/' but is not a /regex/; treated as plain text"
                )
            parsed.append((path, line_no, old, new, None))

    # Duplicate search text: inside one file the later rule is always dead;
    # across files it depends on which flags are combined.
    by_old = {}
    for path, line_no, old, _, _ in parsed:
        by_old.setdefault(old, []).append((path, line_no))
    for old, locations in by_old.items():
        if len(locations) < 2:
            continue
        files = {p for p, _ in locations}
        message = f"duplicate search text {old!r} at " + ", ".join(f"{p}:{n}" for p, n in locations)
        if len(files) == 1:
            errors.append(message + " (later rule is dead)")
        else:
            warnings.append(message + " (only loaded together with certain flags)")

    plain = [(p, n, old) for p, n, old, _, pattern in parsed if pattern is None]

    # Same file: a broad rule before a narrow rule always shadows the narrow one.
    by_file = {}
    for path, line_no, old in plain:
        by_file.setdefault(path, []).append((line_no, old))
    for path, items in by_file.items():
        for index, (line_a, broad) in enumerate(items):
            if len(broad) < MIN_SHADOW_LENGTH:
                continue
            for line_b, narrow in items[index + 1:]:
                if broad != narrow and broad in narrow:
                    errors.append(
                        f"{path}:{line_a}: broad rule {broad!r} shadows later rule "
                        f"at line {line_b} ({narrow!r})"
                    )

    # Across files: warning only, because rules are loaded per feature flag.
    for index, (path_a, line_a, broad) in enumerate(plain):
        if len(broad) < MIN_SHADOW_LENGTH:
            continue
        for path_b, line_b, narrow in plain[index + 1:]:
            if path_a == path_b or broad == narrow:
                continue
            if broad in narrow:
                warnings.append(
                    f"{path_a}:{line_a}: broad rule {broad!r} may shadow "
                    f"{path_b}:{line_b} ({narrow!r})"
                )

    return errors, warnings, len(parsed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=["rules"], help="rule files or directories")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)

    try:
        errors, warnings, total = check(args.paths or ["rules"])
    except FileNotFoundError as exc:
        print(f"error: rule path not found: {exc}")
        return 1
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    print(f"checked {total} rules: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
