import hashlib
import json
from types import SimpleNamespace

import pytest

import fontlang
import lang


@pytest.fixture(autouse=True)
def no_asar_version(monkeypatch):
    monkeypatch.setattr(fontlang.FontTermiusModifier, "_asar_version", lambda self, path: None)


def make_modifier(tmp_path):
    return fontlang.FontTermiusModifier(str(tmp_path), SimpleNamespace(beta=False, style=False))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_backup(tmp_path, content, meta=None):
    (tmp_path / "app.asar.bak").write_bytes(content)
    if meta is not None:
        (tmp_path / "app.asar.bak.json").write_text(json.dumps(meta), encoding="utf-8")


def test_refresh_stale_backup_when_app_updated(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"new-version")
    write_backup(tmp_path, b"old-version", {"patched_sha256": sha(b"patched")})

    make_modifier(tmp_path)._refresh_stale_backup()

    assert (tmp_path / "app.asar.bak").read_bytes() == b"new-version"
    assert not (tmp_path / "app.asar.bak.json").exists()


def test_keep_backup_when_current_is_last_patched_output(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"patched")
    write_backup(tmp_path, b"original", {"patched_sha256": sha(b"patched")})

    make_modifier(tmp_path)._refresh_stale_backup()

    assert (tmp_path / "app.asar.bak").read_bytes() == b"original"


def test_keep_backup_when_metadata_is_missing(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"new-version")
    write_backup(tmp_path, b"original")

    make_modifier(tmp_path)._refresh_stale_backup()

    assert (tmp_path / "app.asar.bak").read_bytes() == b"original"


def test_pack_writes_backup_metadata(tmp_path, monkeypatch):
    (tmp_path / "app.asar").write_bytes(b"packed")
    write_backup(tmp_path, b"original")
    monkeypatch.setattr(lang.TermiusModifier, "pack_to_asar", lambda self: None)

    make_modifier(tmp_path).pack_to_asar()

    meta = json.loads((tmp_path / "app.asar.bak.json").read_text(encoding="utf-8"))
    assert meta["patched_sha256"] == sha(b"packed")


def test_restore_changes_restores_and_cleans_metadata(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"patched")
    write_backup(tmp_path, b"original", {"patched_sha256": sha(b"patched")})

    make_modifier(tmp_path).restore_changes()

    assert (tmp_path / "app.asar").read_bytes() == b"original"
    assert not (tmp_path / "app.asar.bak").exists()
    assert not (tmp_path / "app.asar.bak.json").exists()


def test_restore_tool_with_explicit_path(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"patched")
    (tmp_path / "app.asar.bak").write_bytes(b"original")
    (tmp_path / "app.asar.bak.json").write_text("{}", encoding="utf-8")

    from tools.restore import main

    assert main(["--path", str(tmp_path)]) == 0
    assert (tmp_path / "app.asar").read_bytes() == b"original"
    assert not (tmp_path / "app.asar.bak.json").exists()

def test_refresh_backup_when_asar_version_changes(tmp_path, monkeypatch):
    (tmp_path / "app.asar").write_bytes(b"new-version")
    write_backup(tmp_path, b"old-version", {"patched_sha256": sha(b"patched")})
    monkeypatch.setattr(
        fontlang.FontTermiusModifier,
        "_asar_version",
        lambda self, path: "10.5.0" if path.endswith("app.asar") else "10.4.0",
    )

    make_modifier(tmp_path)._refresh_stale_backup()

    assert (tmp_path / "app.asar.bak").read_bytes() == b"new-version"
    assert (tmp_path / "app.asar.bak.old").read_bytes() == b"old-version"


def test_keep_backup_when_asar_versions_match(tmp_path, monkeypatch):
    (tmp_path / "app.asar").write_bytes(b"patched")
    write_backup(tmp_path, b"original")
    monkeypatch.setattr(fontlang.FontTermiusModifier, "_asar_version", lambda self, path: "10.4.0")

    make_modifier(tmp_path)._refresh_stale_backup()

    assert (tmp_path / "app.asar.bak").read_bytes() == b"original"
