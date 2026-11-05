#!/usr/bin/env python3
"""Restore Termius app.asar from app.asar.bak without the asar CLI.

`python lang.py --restore` runs check_asar_installed() before dispatch, so a
missing @electron/asar blocks a rollback. This entry point only copies files.
"""
import argparse
import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import lang  # noqa: E402
from logger import setup_logging  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Restore Termius app.asar from app.asar.bak.")
    parser.add_argument("-b", "--beta", action="store_true", help="Operate on Termius Beta.")
    parser.add_argument("-p", "--path", help="Termius resources directory (contains app.asar).")
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

    lang.TermiusModifier(termius_path, args).restore_changes()
    meta_path = os.path.join(termius_path, "app.asar.bak.json")
    if os.path.exists(meta_path):
        os.remove(meta_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
