import re
from types import SimpleNamespace

import pytest

import lang


def make_modifier(tmp_path, rules):
    args = SimpleNamespace(beta=False, style=False, skip_login=False, trial=False, localize=True)
    modifier = lang.TermiusModifier(str(tmp_path), args)
    modifier.compiled_rules = rules
    return modifier


def test_specific_rule_runs_before_generic(tmp_path):
    modifier = make_modifier(tmp_path, [
        ("plain", 'title:"Terminal"|title:"终端"', 'title:"Terminal"', 'title:"终端"'),
        ("plain", '"Terminal"|"终端"', '"Terminal"', '"终端"'),
    ])

    result, matched = modifier.replace_content('const a={title:"Terminal"};')

    assert result == 'const a={title:"终端"};'
    assert len(matched) == 1


def test_plain_replacement_is_idempotent(tmp_path):
    modifier = make_modifier(tmp_path, [
        ("plain", '"Save"|"保存"', '"Save"', '"保存"'),
    ])

    once, _ = modifier.replace_content('"Save"')
    twice, matched = modifier.replace_content(once)

    assert once == twice == '"保存"'
    assert not matched


def test_regex_rule_uses_group_references(tmp_path):
    pattern = re.compile(r'return (\w+)\.account\.pro_mode')
    modifier = make_modifier(tmp_path, [
        ("regex", r'/return (\w+)\.account\.pro_mode/|return \g<1>.account.user_type',
         pattern, r"return \g<1>.account.user_type"),
    ])

    result, matched = modifier.replace_content("return user.account.pro_mode")

    assert result == "return user.account.user_type"
    assert len(matched) == 1


def test_resolve_resources_dir_walks_nested_app_bundle(tmp_path):
    resources = tmp_path / "Termius.app" / "Contents" / "Resources"
    resources.mkdir(parents=True)
    (resources / "app.asar").write_bytes(b"asar")

    assert lang.resolve_resources_dir(str(tmp_path / "Termius.app")) == str(resources)
    assert lang.resolve_resources_dir(str(resources)) == str(resources)


def test_resolve_resources_dir_returns_none_without_asar(tmp_path):
    (tmp_path / "Resources").mkdir()

    assert lang.resolve_resources_dir(str(tmp_path)) is None


def test_validate_patch_result_rejects_no_files(tmp_path):
    modifier = make_modifier(tmp_path, [("plain", "a|b", "a", "b")])
    modifier.files_scanned = 0
    modifier.applied_rules = {"a|b"}

    assert modifier._validate_patch_result() is False


def test_validate_patch_result_rejects_no_rules(tmp_path):
    modifier = make_modifier(tmp_path, [])
    modifier.files_scanned = 1

    assert modifier._validate_patch_result() is False


def test_validate_patch_result_rejects_zero_matches(tmp_path):
    modifier = make_modifier(tmp_path, [("plain", "a|b", "a", "b")])
    modifier.files_scanned = 1

    assert modifier._validate_patch_result() is False


def test_validate_patch_result_rejects_file_errors(tmp_path):
    modifier = make_modifier(tmp_path, [("plain", "a|b", "a", "b")])
    modifier.files_scanned = 1
    modifier.applied_rules = {"a|b"}
    modifier.patch_errors = [("broken.js", "read failed")]

    assert modifier._validate_patch_result() is False


def test_validate_patch_result_allows_partial_match(tmp_path):
    modifier = make_modifier(tmp_path, [
        ("plain", "a|b", "a", "b"),
        ("plain", "c|d", "c", "d"),
    ])
    modifier.files_scanned = 1
    modifier.applied_rules = {"a|b"}

    assert modifier._validate_patch_result() is True


def test_replace_rules_counts_files_and_errors(tmp_path, monkeypatch):
    assets = tmp_path / "app" / "ui-process" / "assets"
    assets.mkdir(parents=True)
    good = assets / "good.js"
    bad = assets / "bad.js"
    good.write_text("x", encoding="utf-8")
    bad.write_text("x", encoding="utf-8")

    modifier = make_modifier(tmp_path, [("plain", "x|y", "x", "y")])

    def fake_read(path, strip_empty=False):
        if str(path) == str(bad):
            raise OSError("read failed")
        return "x"

    monkeypatch.setattr(lang, "read_file", fake_read)
    modifier.replace_rules()

    assert modifier.files_scanned == 1
    assert modifier.applied_rules == {"x|y"}
    assert modifier.patch_errors == [(str(bad), "read failed")]


def test_apply_changes_aborts_before_fuse_and_pack(tmp_path, monkeypatch):
    modifier = make_modifier(tmp_path, [("plain", "x|y", "x", "y")])
    calls = []

    monkeypatch.setattr(modifier, "manage_workspace", lambda: calls.append("manage"))
    monkeypatch.setattr(modifier, "decompress_asar", lambda: calls.append("decompress"))
    monkeypatch.setattr(modifier, "load_rules", lambda: calls.append("load"))

    def replace():
        modifier.files_scanned = 1
        modifier.patch_errors = [("bad.js", "write failed")]
        modifier.applied_rules = {"x|y"}

    monkeypatch.setattr(modifier, "replace_rules", replace)
    monkeypatch.setattr(modifier, "clean_workspace", lambda: calls.append("clean"))
    monkeypatch.setattr(modifier, "disable_asar_integrity_validation", lambda: calls.append("fuse"))
    monkeypatch.setattr(modifier, "pack_to_asar", lambda: calls.append("pack"))
    monkeypatch.setattr(lang, "is_macos", lambda: False)

    with pytest.raises(SystemExit):
        modifier.apply_changes()

    assert "pack" not in calls
    assert "fuse" not in calls
    assert "clean" in calls


def test_apply_changes_packs_when_rules_match(tmp_path, monkeypatch):
    modifier = make_modifier(tmp_path, [("plain", "x|y", "x", "y")])
    calls = []

    monkeypatch.setattr(modifier, "manage_workspace", lambda: calls.append("manage"))
    monkeypatch.setattr(modifier, "decompress_asar", lambda: calls.append("decompress"))
    monkeypatch.setattr(modifier, "load_rules", lambda: calls.append("load"))

    def replace():
        modifier.files_scanned = 1
        modifier.patch_errors = []
        modifier.applied_rules = {"x|y"}

    monkeypatch.setattr(modifier, "replace_rules", replace)
    monkeypatch.setattr(modifier, "disable_asar_integrity_validation", lambda: calls.append("fuse"))
    monkeypatch.setattr(modifier, "pack_to_asar", lambda: calls.append("pack"))
    monkeypatch.setattr(lang, "is_macos", lambda: False)

    modifier.apply_changes()

    assert calls == ["manage", "decompress", "load", "fuse", "pack"]


def test_localize_firewall_sentence_survives_skip_login(tmp_path):
    args = SimpleNamespace(beta=False, style=False, skip_login=True, trial=False, localize=True)
    modifier = lang.TermiusModifier(str(tmp_path), args)
    modifier.load_rules()

    source = '"your firewall allows HTTP requests to and responses from the api.termius.com server"'
    result, _ = modifier.replace_content(source)

    assert "防火墙允许向 localhost 服务器发送 HTTP 请求并接收响应" in result
