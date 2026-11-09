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
    (tmp_path / "app.asar.bak.json").write_text(
        json.dumps({"patched_sha256": sha(b"patched")}), encoding="utf-8"
    )

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


def test_manage_workspace_aborts_on_stale_backup_without_metadata(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"new-version")
    write_backup(tmp_path, b"old-version")

    with pytest.raises(SystemExit):
        make_modifier(tmp_path).manage_workspace()

    assert (tmp_path / "app.asar").read_bytes() == b"new-version"


def test_manage_workspace_refreshes_backup_with_metadata(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"new-version")
    write_backup(tmp_path, b"old-version", {"patched_sha256": sha(b"patched")})

    make_modifier(tmp_path).manage_workspace()

    assert (tmp_path / "app.asar").read_bytes() == b"new-version"
    assert (tmp_path / "app.asar.bak").read_bytes() == b"new-version"
    meta = json.loads((tmp_path / "app.asar.bak.json").read_text(encoding="utf-8"))
    assert meta["backup_sha256"] == sha(b"new-version")


def test_restore_refuses_stale_backup_without_force(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"new-version")
    write_backup(tmp_path, b"old-version", {
        "patched_sha256": sha(b"patched"),
        "backup_sha256": sha(b"old-version"),
    })

    modifier = make_modifier(tmp_path)

    assert modifier.restore_changes() is False
    assert (tmp_path / "app.asar").read_bytes() == b"new-version"
    assert (tmp_path / "app.asar.bak").exists()

    assert modifier.restore_changes(force=True) is True
    assert (tmp_path / "app.asar").read_bytes() == b"old-version"
    assert not (tmp_path / "app.asar.bak").exists()


def test_restore_refuses_when_metadata_is_missing(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"new-version")
    write_backup(tmp_path, b"old-version")

    assert make_modifier(tmp_path).restore_changes() is False
    assert (tmp_path / "app.asar").read_bytes() == b"new-version"


def test_restore_allows_recovery_after_failed_pack(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"partial-output")
    write_backup(tmp_path, b"original", {"backup_sha256": sha(b"original")})

    assert make_modifier(tmp_path).restore_changes() is True
    assert (tmp_path / "app.asar").read_bytes() == b"original"


def test_create_backup_refuses_missing_backup_with_metadata(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"patched")
    (tmp_path / "app.asar.bak.json").write_text(
        json.dumps({"patched_sha256": sha(b"patched")}), encoding="utf-8"
    )

    with pytest.raises(SystemExit):
        make_modifier(tmp_path).create_backup()

    assert not (tmp_path / "app.asar.bak").exists()


def test_fuse_byte_is_recorded_and_restored(tmp_path, monkeypatch):
    (tmp_path / "app.asar").write_bytes(b"patched")
    write_backup(tmp_path, b"original", {"patched_sha256": sha(b"patched")})

    fuse_count = 8
    states = bytearray(b"0" * fuse_count)
    states[lang.FUSE_ASAR_INTEGRITY] = ord("1")
    exe = tmp_path / "Termius"
    exe.write_bytes(lang.FUSE_SENTINEL + bytes([1, fuse_count]) + bytes(states) + b"tail")
    original_exe = exe.read_bytes()
    offset = len(lang.FUSE_SENTINEL) + 2 + lang.FUSE_ASAR_INTEGRITY

    modifier = make_modifier(tmp_path)
    monkeypatch.setattr(lang, "is_macos", lambda: False)
    monkeypatch.setattr(modifier, "_find_fuse_executable", lambda: str(exe))

    modifier.disable_asar_integrity_validation()

    assert exe.read_bytes()[offset] == ord("0")
    meta = json.loads((tmp_path / "app.asar.bak.json").read_text(encoding="utf-8"))
    assert meta["fuse"]["path"] == str(exe)
    assert meta["fuse"]["offset"] == offset
    assert meta["fuse"]["original"] == ord("1")
    assert meta["fuse"]["executable_sha256"] == sha(exe.read_bytes())

    assert modifier.restore_changes() is True
    assert (tmp_path / "app.asar").read_bytes() == b"original"
    assert exe.read_bytes() == original_exe
    assert not (tmp_path / "app.asar.bak.json").exists()


def test_restore_tool_refuses_stale_backup_unless_forced(tmp_path):
    (tmp_path / "app.asar").write_bytes(b"new-version")
    (tmp_path / "app.asar.bak").write_bytes(b"old-version")

    from tools.restore import main

    assert main(["--path", str(tmp_path)]) == 1
    assert (tmp_path / "app.asar").read_bytes() == b"new-version"

    assert main(["--path", str(tmp_path), "--force"]) == 0
    assert (tmp_path / "app.asar").read_bytes() == b"old-version"


def test_fuse_restore_skips_when_executable_changed(tmp_path, monkeypatch):
    (tmp_path / "app.asar").write_bytes(b"patched")
    write_backup(tmp_path, b"original", {"patched_sha256": sha(b"patched")})

    fuse_count = 8
    states = bytearray(b"0" * fuse_count)
    states[lang.FUSE_ASAR_INTEGRITY] = ord("1")
    exe = tmp_path / "Termius"
    exe.write_bytes(lang.FUSE_SENTINEL + bytes([1, fuse_count]) + bytes(states) + b"tail")
    offset = len(lang.FUSE_SENTINEL) + 2 + lang.FUSE_ASAR_INTEGRITY

    modifier = make_modifier(tmp_path)
    monkeypatch.setattr(lang, "is_macos", lambda: False)
    monkeypatch.setattr(modifier, "_find_fuse_executable", lambda: str(exe))
    modifier.disable_asar_integrity_validation()

    with open(exe, "ab") as file:
        file.write(b"updated")

    assert modifier.restore_changes() is True
    assert (tmp_path / "app.asar").read_bytes() == b"original"
    assert exe.read_bytes()[offset] == ord("0")


def test_restore_runs_macos_fix(tmp_path, monkeypatch):
    (tmp_path / "app.asar").write_bytes(b"patched")
    write_backup(tmp_path, b"original", {"patched_sha256": sha(b"patched")})

    modifier = make_modifier(tmp_path)
    called = []
    monkeypatch.setattr(lang, "is_macos", lambda: True)
    monkeypatch.setattr(modifier, "apply_macos_fix", lambda: called.append(True))

    assert modifier.restore_changes() is True
    assert called == [True]
    assert (tmp_path / "app.asar").read_bytes() == b"original"


def test_manage_workspace_allows_legacy_backup_same_version(tmp_path, monkeypatch):
    (tmp_path / "app.asar").write_bytes(b"patched")
    write_backup(tmp_path, b"original")
    monkeypatch.setattr(fontlang.FontTermiusModifier, "_asar_version", lambda self, path: "10.4.0")

    make_modifier(tmp_path).manage_workspace()

    assert (tmp_path / "app.asar").read_bytes() == b"original"


def test_restore_allows_legacy_backup_same_version(tmp_path, monkeypatch):
    (tmp_path / "app.asar").write_bytes(b"patched")
    write_backup(tmp_path, b"original")
    monkeypatch.setattr(fontlang.FontTermiusModifier, "_asar_version", lambda self, path: "10.4.0")

    assert make_modifier(tmp_path).restore_changes() is True
    assert (tmp_path / "app.asar").read_bytes() == b"original"
