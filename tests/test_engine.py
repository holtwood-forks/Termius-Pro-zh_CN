import re
from types import SimpleNamespace

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
