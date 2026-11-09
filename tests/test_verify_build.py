import tools.verify_build as verify_build


def statuses(checks):
    return {item["name"]: item["status"] for item in checks}


def font_listing():
    expected = verify_build.expected_font_files()
    return "\n".join([f"/{name}" for name in expected] + ["/ui-process/assets/main-test.css"])


def test_verify_build_accepts_font_package():
    checks = verify_build.verify(
        "app.asar",
        listing=font_listing(),
        require_fonts=True,
        css_reader=lambda asar, path: '@font-face{font-family:"CodeNewRoman Nerd Font Mono"}',
    )

    assert statuses(checks) == {
        "asar_readable": "ok",
        "fonts_packed": "ok",
        "css_marker": "ok",
    }


def test_verify_build_rejects_missing_font():
    expected = verify_build.expected_font_files()
    listing = font_listing().replace(f"/{expected[0]}\n", "")

    checks = verify_build.verify(
        "app.asar", listing=listing, require_fonts=True,
        css_reader=lambda asar, path: verify_build.CSS_MARKER,
    )

    assert statuses(checks)["fonts_packed"] == "fail"


def test_verify_build_rejects_missing_css_marker():
    checks = verify_build.verify(
        "app.asar", listing=font_listing(), require_fonts=True,
        css_reader=lambda asar, path: "body{}",
    )

    assert statuses(checks)["css_marker"] == "fail"


def test_verify_build_non_font_only_checks_listing():
    checks = verify_build.verify("app.asar", listing="/ui-process/assets/main-test.css")

    assert checks == [{"name": "asar_readable", "status": "ok", "detail": "1 entries"}]


def test_verify_build_fails_when_asar_cannot_be_listed(monkeypatch):
    monkeypatch.setattr(verify_build, "asar_list", lambda path: None)

    checks = verify_build.verify("app.asar")

    assert statuses(checks)["asar_readable"] == "fail"


def test_verify_build_checks_all_css_candidates():
    listing = font_listing() + "\n/ui-process/assets/main-second.css"

    checks = verify_build.verify(
        "app.asar", listing=listing, require_fonts=True,
        css_reader=lambda asar, path: verify_build.CSS_MARKER
        if path.endswith("main-second.css") else "body{}",
    )

    assert statuses(checks)["css_marker"] == "ok"


def test_verify_build_rejects_missing_font_directory(monkeypatch):
    monkeypatch.setattr(verify_build, "expected_font_files", lambda: [])

    checks = verify_build.verify(
        "app.asar", listing="/ui-process/assets/main-test.css", require_fonts=True,
    )

    assert statuses(checks)["fonts_packed"] == "fail"
