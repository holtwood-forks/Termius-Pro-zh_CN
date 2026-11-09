import hashlib
import json
import os

from tools.verify_asar import render_text, verify


class StubModifier:
    def __init__(self, versions):
        self.versions = versions

    def _asar_version(self, path):
        return self.versions.get(os.path.basename(path))

    def _file_sha256(self, path):
        return hashlib.sha256(open(path, "rb").read()).hexdigest()


def make_fixture(tmp_path, versions=None):
    (tmp_path / "app.asar").write_bytes(b"patched")
    (tmp_path / "app.asar.bak").write_bytes(b"original")
    (tmp_path / "app.asar.bak.json").write_text(
        json.dumps({"patched_sha256": hashlib.sha256(b"patched").hexdigest()}),
        encoding="utf-8",
    )
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "TestFont.otf").write_bytes(b"font")
    (fonts / "OFL-1.1.txt").write_text("OFL", encoding="utf-8")
    (fonts / "NOTICE.md").write_text("notice", encoding="utf-8")
    listing = "\n".join([
        "/ui-process/assets/TestFont.otf",
        "/ui-process/assets/OFL-1.1.txt",
        "/ui-process/assets/NOTICE.md",
        "/ui-process/assets/main-test.css",
    ])
    modifier = StubModifier(versions or {"app.asar": "10.4.0", "app.asar.bak": "10.4.0"})
    return modifier, listing, fonts


def statuses(result):
    return {item["name"]: item["status"] for item in result["checks"]}


def test_verify_all_ok(tmp_path):
    modifier, listing, fonts = make_fixture(tmp_path)

    result = verify(
        str(tmp_path), modifier, listing, fonts_dir=str(fonts),
        css_reader=lambda asar, path: '@font-face{font-family:"CodeNewRoman Nerd Font Mono"}',
        report={"version": "10.4.0", "matched": 1555, "total": 1555, "unmatched": 0},
    )

    assert statuses(result) == {
        "app_asar_exists": "ok",
        "asar_readable": "ok",
        "version": "ok",
        "version_matches_backup": "ok",
        "meta_matches_asar": "ok",
        "fonts_packed": "ok",
        "css_marker": "ok",
        "rule_report": "ok",
    }


def test_verify_version_mismatch(tmp_path):
    modifier, listing, fonts = make_fixture(
        tmp_path, {"app.asar": "10.5.0", "app.asar.bak": "10.4.0"}
    )

    result = verify(str(tmp_path), modifier, listing, fonts_dir=str(fonts))

    assert statuses(result)["version_matches_backup"] == "fail"


def test_verify_missing_font(tmp_path):
    modifier, listing, fonts = make_fixture(tmp_path)
    listing = listing.replace("/ui-process/assets/TestFont.otf\n", "")

    result = verify(str(tmp_path), modifier, listing, fonts_dir=str(fonts))

    assert statuses(result)["fonts_packed"] == "fail"


def test_verify_unreadable_asar(tmp_path):
    modifier, _, fonts = make_fixture(tmp_path)

    result = verify(str(tmp_path), modifier, None, fonts_dir=str(fonts))

    assert statuses(result)["asar_readable"] == "fail"


def test_verify_skips_fonts_without_fonts_dir(tmp_path):
    modifier, listing, _ = make_fixture(tmp_path)

    result = verify(str(tmp_path), modifier, listing, fonts_dir=str(tmp_path / "none"))

    assert statuses(result)["fonts_packed"] == "skip"


def test_verify_css_marker_missing(tmp_path):
    modifier, listing, fonts = make_fixture(tmp_path)

    result = verify(
        str(tmp_path), modifier, listing, fonts_dir=str(fonts),
        css_reader=lambda asar, path: "body{}",
    )

    assert statuses(result)["css_marker"] == "fail"


def test_render_text_contains_check_labels(tmp_path):
    modifier, listing, fonts = make_fixture(tmp_path)
    result = verify(str(tmp_path), modifier, listing, fonts_dir=str(fonts))

    text = render_text(result)

    assert "[OK  ] app_asar_exists" in text
    assert "Termius version : 10.4.0" in text

def test_verify_meta_mismatch(tmp_path):
    modifier, listing, fonts = make_fixture(tmp_path)
    (tmp_path / "app.asar.bak.json").write_text(
        json.dumps({"patched_sha256": "0" * 64}), encoding="utf-8"
    )

    result = verify(str(tmp_path), modifier, listing, fonts_dir=str(fonts))

    assert statuses(result)["meta_matches_asar"] == "fail"


def test_verify_rule_report_missing(tmp_path):
    modifier, listing, fonts = make_fixture(tmp_path)

    result = verify(str(tmp_path), modifier, listing, fonts_dir=str(fonts), report={})

    assert statuses(result)["rule_report"] == "warn"


def test_verify_rule_report_unmatched(tmp_path):
    modifier, listing, fonts = make_fixture(tmp_path)

    result = verify(
        str(tmp_path), modifier, listing, fonts_dir=str(fonts),
        report={"version": "10.4.0", "matched": 1553, "total": 1555, "unmatched": 2},
    )

    assert statuses(result)["rule_report"] == "warn"


def test_verify_rule_report_version_mismatch(tmp_path):
    modifier, listing, fonts = make_fixture(tmp_path)

    result = verify(
        str(tmp_path), modifier, listing, fonts_dir=str(fonts),
        report={"version": "10.3.0", "matched": 1555, "total": 1555, "unmatched": 0},
    )

    assert statuses(result)["rule_report"] == "warn"


def test_verify_no_fonts_skips_font_checks(tmp_path):
    modifier, listing, fonts = make_fixture(tmp_path)

    result = verify(
        str(tmp_path), modifier, listing, fonts_dir=str(fonts), check_fonts=False,
    )

    assert statuses(result)["fonts_packed"] == "skip"
    assert statuses(result)["css_marker"] == "skip"


def test_verify_fonts_dir_without_font_files(tmp_path):
    modifier, listing, _ = make_fixture(tmp_path)
    fonts = tmp_path / "empty-fonts"
    fonts.mkdir()
    (fonts / "OFL-1.1.txt").write_text("OFL", encoding="utf-8")

    result = verify(str(tmp_path), modifier, listing, fonts_dir=str(fonts))

    assert statuses(result)["fonts_packed"] == "fail"


def test_verify_css_extract_failure(tmp_path):
    modifier, listing, fonts = make_fixture(tmp_path)

    result = verify(
        str(tmp_path), modifier, listing, fonts_dir=str(fonts),
        css_reader=lambda asar, path: None,
    )

    assert statuses(result)["css_marker"] == "fail"
    detail = next(item["detail"] for item in result["checks"] if item["name"] == "css_marker")
    assert "cannot extract" in detail
