import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "tools" / "lint_rules.py"


def run_lint(*paths):
    return subprocess.run(
        [sys.executable, str(LINT), *map(str, paths)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_repository_rules_pass_lint():
    result = run_lint(ROOT / "rules")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 error(s)" in result.stdout


def test_lint_rejects_broad_rule_before_narrow_rule(tmp_path):
    rules = tmp_path / "localize.txt"
    rules.write_text('"Terminal"|"终端"\ntitle:"Terminal"|title:"终端"\n', encoding="utf-8")

    result = run_lint(rules)

    assert result.returncode == 1
    assert "shadows later rule" in result.stdout


def test_lint_rejects_invalid_regex(tmp_path):
    rules = tmp_path / "localize.txt"
    rules.write_text("/[unclosed/|x\n", encoding="utf-8")

    result = run_lint(rules)

    assert result.returncode == 1
    assert "invalid regex" in result.stdout


def test_lint_rejects_missing_separator(tmp_path):
    rules = tmp_path / "localize.txt"
    rules.write_text("no separator here\n", encoding="utf-8")

    result = run_lint(rules)

    assert result.returncode == 1
    assert "missing '|' separator" in result.stdout

def test_lint_accepts_plain_path_starting_with_slash(tmp_path):
    rules = tmp_path / "localize.txt"
    rules.write_text("/opt/Termius|/opt/Termius-zh\n", encoding="utf-8")

    result = run_lint(rules)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 error(s)" in result.stdout
