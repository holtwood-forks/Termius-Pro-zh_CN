import hashlib
import json
import os

from tools.status import collect_status, read_report, render_text


class StubModifier:
    def __init__(self, versions=None):
        self.versions = versions or {}

    def _asar_version(self, path):
        return self.versions.get(os.path.basename(path))

    def _file_sha256(self, path):
        return hashlib.sha256(open(path, "rb").read()).hexdigest()


def test_collect_status_original(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"same")
    (tmp_path / "app.asar.bak").write_bytes(b"same")

    status = collect_status(str(tmp_path), StubModifier(), "ui-process/assets/CodeNewRomanNerdFontMono-Regular.otf")

    assert status["app_asar"]["state"] == "original"
    assert status["fonts"]["injected"] is True


def test_collect_status_patched(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"patched")
    (tmp_path / "app.asar.bak").write_bytes(b"original")
    (tmp_path / "app.asar.bak.json").write_text(
        json.dumps({"patched_sha256": hashlib.sha256(b"patched").hexdigest()}),
        encoding="utf-8",
    )

    status = collect_status(str(tmp_path), StubModifier())

    assert status["app_asar"]["state"] == "patched"
    assert status["meta"]["exists"] is True


def test_collect_status_unknown(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"new")
    (tmp_path / "app.asar.bak").write_bytes(b"old")
    (tmp_path / "app.asar.bak.json").write_text(
        json.dumps({"patched_sha256": hashlib.sha256(b"other").hexdigest()}),
        encoding="utf-8",
    )

    status = collect_status(str(tmp_path), StubModifier())

    assert status["app_asar"]["state"] == "unknown"


def test_collect_status_missing(tmp_path):
    status = collect_status(str(tmp_path), StubModifier(), None)

    assert status["app_asar"]["state"] == "missing"
    assert status["fonts"]["injected"] is None


def test_read_report_parses_summary(tmp_path):
    report = tmp_path / "rule-report.txt"
    unmatched = tmp_path / "unmatched-rules.txt"
    report.write_text(
        "# Termius version: 10.4.0\n# rules: 1555/1555 matched\n# read errors: 0\n",
        encoding="utf-8",
    )
    unmatched.write_text("# unmatched rules: 2/1555\n", encoding="utf-8")

    result = read_report(str(report), str(unmatched))

    assert result == {"version": "10.4.0", "matched": 1555, "total": 1555, "read_errors": 0, "unmatched": 2}


def test_render_text_includes_state(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"patched")
    (tmp_path / "app.asar.bak").write_bytes(b"original")
    (tmp_path / "app.asar.bak.json").write_text(
        json.dumps({"patched_sha256": hashlib.sha256(b"patched").hexdigest()}),
        encoding="utf-8",
    )

    text = render_text(collect_status(str(tmp_path), StubModifier()))

    assert "已打补丁" in text
    assert "backup" in text
