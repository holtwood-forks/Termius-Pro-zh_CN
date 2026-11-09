# -*- coding: utf-8 -*-
"""Backup/restore safety shared by lang.py and fontlang.py.

The project keeps lang.py close to upstream, so the stale-backup guard lives
here and is mixed into lang.TermiusModifier instead of growing lang.py.
"""
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile


class BackupGuardMixin:
    """Protect the original app.asar from being overwritten by a stale backup."""

    @property
    def _backup_meta_path(self):
        """备份元数据：记录备份/补丁产物 hash、版本以及 fuse 原始状态"""
        return self._backup_path + ".json"

    @staticmethod
    def _file_sha256(path):
        digest = hashlib.sha256()
        with open(path, "rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _copy_file_atomic(source, target):
        """同目录临时文件 + os.replace，避免复制中断留下半个 app.asar/备份"""
        temp_path = f"{target}.tmp"
        try:
            shutil.copy2(source, temp_path)
            os.replace(temp_path, target)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _read_backup_meta(self):
        try:
            with open(self._backup_meta_path, "r", encoding="utf-8") as file:
                meta = json.load(file)
            return meta if isinstance(meta, dict) else {}
        except (OSError, ValueError):
            return {}

    def _write_backup_meta(self, **updates):
        from lang import write_file_atomic

        meta = self._read_backup_meta()
        meta.update(updates)
        write_file_atomic(self._backup_meta_path, json.dumps(meta, ensure_ascii=False, sort_keys=True) + "\n")

    def _asar_version(self, asar_path):
        """读取 asar 内 package.json 的 version；asar CLI 不可用或文件损坏时返回 None"""
        from lang import get_asar_cmd

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                subprocess.run(
                    [get_asar_cmd(), "extract-file", asar_path, "package.json"],
                    cwd=temp_dir, check=True, capture_output=True, text=True,
                )
                with open(os.path.join(temp_dir, "package.json"), "r", encoding="utf-8") as file:
                    return json.load(file).get("version")
        except (OSError, subprocess.CalledProcessError, ValueError):
            return None

    def _record_backup_metadata(self):
        """记录备份文件的哈希与版本，供后续判断备份是否过期"""
        backup_hash = self._file_sha256(self._backup_path)
        self._write_backup_meta(
            backup_sha256=backup_hash,
            backup_version=self._asar_version(self._backup_path),
        )
        return backup_hash

    def _ensure_backup_metadata(self):
        """确保已有备份带有哈希/版本；备份被外部改动时拒绝继续"""
        meta = self._read_backup_meta()
        backup_hash = self._file_sha256(self._backup_path)
        recorded = meta.get("backup_sha256")
        if recorded and recorded != backup_hash:
            logging.error(
                "app.asar.bak does not match the recorded backup hash; "
                "refusing to use a modified backup"
            )
            raise SystemExit(1)
        if not recorded or "backup_version" not in meta:
            self._write_backup_meta(
                backup_sha256=backup_hash,
                backup_version=self._asar_version(self._backup_path),
            )
        return backup_hash

    def _replace_backup(self):
        """用当前 app.asar 刷新备份，旧备份保留为 .old（只保留第一份）"""
        old_backup = self._backup_path + ".old"
        if not os.path.exists(old_backup):
            os.replace(self._backup_path, old_backup)
            logging.warning(f"Previous backup preserved at {old_backup}")
        else:
            os.remove(self._backup_path)
        self._copy_file_atomic(self._original_path, self._backup_path)
        if os.path.exists(self._backup_meta_path):
            os.remove(self._backup_meta_path)

    def ensure_backup_current(self):
        """确认 app.asar.bak 仍是当前版本的备份。

        返回 True 表示可以安全继续；返回 False 表示无法判断或备份疑似过期，
        调用方必须中止，不能用旧备份覆盖当前 app.asar。
        """
        meta = self._read_backup_meta()
        if not os.path.exists(self._backup_path):
            if meta.get("patched_sha256") or meta.get("fuse"):
                logging.error(
                    "app.asar.bak is missing but metadata indicates a previous patch; "
                    "refusing to treat the current app.asar as the original"
                )
                return False
            if meta:
                logging.warning("Discarding stale backup metadata for missing app.asar.bak")
                os.remove(self._backup_meta_path)
            return True

        backup_hash = self._ensure_backup_metadata()
        current_hash = self._file_sha256(self._original_path)
        patched_hash = meta.get("patched_sha256")
        if patched_hash and current_hash == patched_hash:
            current_version = self._asar_version(self._original_path)
            backup_version = self._asar_version(self._backup_path)
            if current_version and backup_version and current_version != backup_version:
                logging.error(
                    "app.asar matches the last patched output but app.asar.bak "
                    f"is version {backup_version}; refusing to restore a mismatched backup"
                )
                return False
            return True
        if current_hash == backup_hash:
            return True
        if patched_hash:
            current_version = self._asar_version(self._original_path)
            backup_version = self._asar_version(self._backup_path)
            if current_version and backup_version and current_version == backup_version:
                logging.error(
                    "app.asar changed without a version bump; refusing to guess which "
                    "file is the original"
                )
                return False
            logging.warning(
                "app.asar no longer matches the last patched output; "
                "refreshing app.asar.bak from the current file"
            )
            self._replace_backup()
            return True
        current_version = self._asar_version(self._original_path)
        backup_version = self._asar_version(self._backup_path)
        if current_version and backup_version and current_version == backup_version:
            logging.warning(
                "No patch metadata exists, but app.asar and app.asar.bak are the same "
                "version; using the existing backup"
            )
            return True
        logging.error(
            "app.asar differs from app.asar.bak and no patch metadata exists; "
            "refusing to overwrite the current file. If Termius was updated, "
            "delete app.asar.bak and app.asar.bak.json, then rerun."
        )
        return False

    def _restore_is_safe(self, force=False):
        meta = self._read_backup_meta()
        if not os.path.exists(self._backup_path):
            if meta.get("patched_sha256") or meta.get("fuse"):
                logging.error("app.asar.bak is missing; cannot restore a patched app.asar")
                return False
            return True
        if force:
            return True
        backup_hash = self._file_sha256(self._backup_path)
        recorded_backup = meta.get("backup_sha256")
        if recorded_backup and recorded_backup != backup_hash:
            logging.error("app.asar.bak was modified after it was recorded; refusing to restore")
            return False
        current_hash = self._file_sha256(self._original_path)
        if current_hash == backup_hash:
            return True
        if meta.get("patched_sha256") == current_hash:
            return True
        if not meta.get("patched_sha256") and recorded_backup == backup_hash:
            # 上次打包没有完成，app.asar 可能只是半成品；允许用已知原版恢复
            return True
        current_version = self._asar_version(self._original_path)
        backup_version = self._asar_version(self._backup_path)
        if (not meta.get("patched_sha256") and current_version and backup_version
                and current_version == backup_version):
            logging.warning("No patch metadata exists, but versions match; allowing restore")
            return True
        if current_version and backup_version and current_version != backup_version:
            logging.error(
                f"backup is version {backup_version}, installed app.asar is {current_version}; "
                "refusing to downgrade. Use --force to restore anyway."
            )
        else:
            logging.error(
                "app.asar changed after the last patch; refusing to restore a possibly stale backup. "
                "Use --force to restore anyway."
            )
        return False

    def _restore_fuse(self):
        """恢复打补丁时修改过的 Electron fuse 字节"""
        from lang import write_file_atomic

        fuse = self._read_backup_meta().get("fuse")
        if not fuse:
            return True
        path = fuse.get("path")
        offset = fuse.get("offset")
        original = fuse.get("original")
        if (not isinstance(path, str) or not isinstance(offset, int) or not isinstance(original, int)
                or offset < 0 or not 0 <= original <= 255):
            logging.error("Invalid fuse metadata; cannot restore asar integrity validation")
            return False
        if not os.path.isfile(path):
            logging.warning(f"Fuse executable not found, skipping fuse restore: {path}")
            return True
        try:
            with open(path, "rb") as file:
                file.seek(offset)
                current = file.read(1)
        except OSError as e:
            logging.error(f"Cannot read fuse executable {path}: {e}")
            return False
        if current == bytes([original]):
            return True
        if len(current) != 1:
            logging.error(f"Cannot read fuse byte at offset {offset} in {path}")
            return False
        expected_exe_hash = fuse.get("executable_sha256")
        if expected_exe_hash:
            try:
                current_exe_hash = self._file_sha256(path)
            except OSError as e:
                logging.error(f"Cannot hash fuse executable {path}: {e}")
                return False
            if current_exe_hash != expected_exe_hash:
                logging.warning(
                    "Termius executable changed since patching; leaving asar integrity "
                    "validation disabled instead of restoring a mismatched fuse"
                )
                return True
        try:
            write_file_atomic(path, offsets={offset: bytes([original])})
        except OSError as e:
            logging.error(f"Failed to restore fuse byte in {path}: {e}")
            return False
        logging.info("Asar integrity validation fuse restored")
        return True

    def create_backup(self):
        """创建初始备份（仅在备份不存在时）"""
        if os.path.exists(self._backup_path):
            self._ensure_backup_metadata()
            return
        meta = self._read_backup_meta()
        if meta.get("patched_sha256") or meta.get("fuse"):
            logging.error(
                "app.asar.bak is missing but metadata indicates a previous patch; "
                "refusing to use the current app.asar as the original backup"
            )
            raise SystemExit(1)
        if meta:
            logging.warning("Discarding stale backup metadata for missing app.asar.bak")
            os.remove(self._backup_meta_path)
        self._copy_file_atomic(self._original_path, self._backup_path)
        logging.info("Initial backup created")
        self._record_backup_metadata()

    def manage_workspace(self):
        """管理工作区：确认备份有效后创建/恢复备份"""
        if not self.ensure_backup_current():
            logging.error(
                "Refusing to overwrite the current app.asar because the backup state "
                "cannot be verified; see the message above"
            )
            raise SystemExit(1)
        self.create_backup()
        self.clean_workspace()

    def restore_changes(self, force=False):
        """完全还原：恢复 app.asar、macOS hash/fuse，然后删除备份"""
        if not self._restore_is_safe(force=force):
            return False
        had_backup = os.path.exists(self._backup_path)
        try:
            self.clean_workspace()
        except OSError as e:
            logging.error(
                f"Failed to restore app.asar: {e}. Make sure Termius is fully closed "
                "and you have write access to the resources directory."
            )
            return False
        from lang import is_macos

        if had_backup and is_macos():
            self.apply_macos_fix()
        if not self._restore_fuse():
            logging.error("app.asar was restored but the Electron fuse could not be restored")
            return False
        if os.path.exists(self._backup_path):
            os.remove(self._backup_path)
        if os.path.exists(self._backup_meta_path):
            os.remove(self._backup_meta_path)
        return True

    def _record_patch_metadata(self):
        """记录本次打包产物，供下次运行判断当前 app.asar 是否是自己生成的"""
        self._write_backup_meta(
            patched_sha256=self._file_sha256(self._original_path),
            patched_version=self._asar_version(self._original_path),
        )
