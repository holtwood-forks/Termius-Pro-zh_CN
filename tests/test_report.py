from types import SimpleNamespace

from tools.report_rules import ReportModifier, analyze, write_report


def test_analyze_counts_matched_and_unmatched(tmp_path):
    app = tmp_path / "app"
    assets = app / "ui-process" / "assets"
    assets.mkdir(parents=True)
    (assets / "main.js").write_text('title:"Terminal"', encoding="utf-8")

    modifier = ReportModifier(str(tmp_path), SimpleNamespace(style=False), str(app))
    modifier.compiled_rules = [
        ("plain", 'title:"Terminal"|title:"终端"', 'title:"Terminal"', 'title:"终端"'),
        ("plain", '"Missing"|"缺失"', '"Missing"', '"缺失"'),
    ]

    files, rules, matched, unmatched, errors = analyze(modifier)

    assert len(files) == 1
    assert len(rules) == 2
    assert len(matched) == 1
    assert unmatched == ['"Missing"|"缺失"']
    assert errors == []


def test_write_report_records_version_and_unmatched(tmp_path):
    report = tmp_path / "rule-report.txt"
    unmatched = tmp_path / "unmatched-rules.txt"

    write_report(
        str(report), str(unmatched), "10.4.0",
        ["main.js"], ["r1", "r2"], ["r2"], [],
    )

    assert "Termius version: 10.4.0" in report.read_text(encoding="utf-8")
    assert "1/2 matched" in report.read_text(encoding="utf-8")
    assert "r2" in unmatched.read_text(encoding="utf-8")
