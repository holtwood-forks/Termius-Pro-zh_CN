from types import SimpleNamespace

import fontlang


class FontModifier(fontlang.FontTermiusModifier):
    def __init__(self, termius_path, fonts_dir):
        super().__init__(termius_path, SimpleNamespace(beta=False, style=False))
        self._test_fonts_dir = fonts_dir

    @property
    def _fonts_dir(self):
        return self._test_fonts_dir


def make_app(tmp_path):
    assets = tmp_path / "app" / "ui-process" / "assets"
    assets.mkdir(parents=True)
    css = assets / "main-test.css"
    css.write_text(".xterm-viewport{color:red}", encoding="utf-8")
    return assets, css


def make_fonts(tmp_path):
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "fonts.css").write_text(
        '@font-face{font-family:"CodeNewRoman Nerd Font Mono"}', encoding="utf-8"
    )
    (fonts / "CodeNewRomanNerdFontMono-Regular.otf").write_bytes(b"font")
    (fonts / "OFL-1.1.txt").write_text("OFL", encoding="utf-8")
    (fonts / "NOTICE.md").write_text("notice", encoding="utf-8")
    return fonts


def test_apply_fonts_copies_fonts_licenses_and_is_idempotent(tmp_path):
    assets, css = make_app(tmp_path)
    fonts = make_fonts(tmp_path)
    modifier = FontModifier(str(tmp_path), str(fonts))

    modifier.apply_fonts()

    assert (assets / "CodeNewRomanNerdFontMono-Regular.otf").read_bytes() == b"font"
    assert (assets / "OFL-1.1.txt").read_text(encoding="utf-8") == "OFL"
    assert (assets / "NOTICE.md").read_text(encoding="utf-8") == "notice"
    first = css.read_text(encoding="utf-8")
    assert first.count("CodeNewRoman Nerd Font Mono") == 1

    modifier.apply_fonts()

    assert css.read_text(encoding="utf-8") == first


def test_compile_font_rules_loads_font_txt():
    modifier = FontModifier("/nonexistent", "/nonexistent")

    modifier._compile_font_rules()

    assert len(modifier.compiled_rules) == 6
    assert all(rule[0] in ("plain", "regex") for rule in modifier.compiled_rules)

def test_unmatched_report_lists_only_missing_rules(tmp_path):
    report = tmp_path / "unmatched.txt"

    class ReportModifier(fontlang.FontTermiusModifier):
        def __init__(self, termius_path, report_path):
            super().__init__(termius_path, SimpleNamespace(beta=False, style=False))
            self._test_report_path = report_path

        @property
        def _report_path(self):
            return self._test_report_path

    modifier = ReportModifier(str(tmp_path), str(report))
    modifier.compiled_rules = [
        ("plain", "a|b", "a", "b"),
        ("plain", "c|d", "c", "d"),
    ]
    modifier.applied_rules = {"a|b"}

    modifier._write_unmatched_report()

    text = report.read_text(encoding="utf-8")
    assert "1/2" in text
    assert "c|d" in text
    assert "a|b" not in text

def test_font_default_rule_matches_all_three_processes():
    modifier = FontModifier("/nonexistent", "/nonexistent")
    modifier._compile_font_rules()
    regex_rules = [rule for rule in modifier.compiled_rules if rule[0] == "regex"]
    assert len(regex_rules) == 1
    _, _, pattern, replacement = regex_rules[0]

    samples = [
        '"termius dark",kM="Source Code Pro"',
        '"termius dark",defaultFontFamily$1="Source Code Pro"',
        '"termius dark",QAe="Source Code Pro"',
    ]
    for sample in samples:
        result = pattern.sub(replacement, sample)
        assert result.endswith('="CodeNewRoman Nerd Font Mono"')
        assert '"Source Code Pro"' not in result


def test_font_rules_run_before_style_rules(tmp_path):
    modifier = FontModifier("/nonexistent", "/nonexistent")
    modifier.compiled_rules = [
        ("plain", "CircularXX|system-ui", "CircularXX", "system-ui"),
    ]

    modifier._compile_font_rules()
    result, _ = modifier.replace_content('fontFamily:"CircularXX, sans-serif"')

    assert "'CodeNewRoman Nerd Font Mono'" in result
    assert "system-ui" not in result
