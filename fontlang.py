# -*- coding: utf-8 -*-
"""Termius 字体注入入口（叠加层脚本）

本文件是 fork 的 Python 叠加层入口，不修改上游 lang.py 的任何内容：
通过子类化 TermiusModifier，并在运行期间临时替换 lang 模块内的类引用实现注入，
因此上游对 lang.py 的更新可以直接合并，不会产生文本冲突。

用法与 lang.py 完全一致（参数解析与调度复用上游 main()）：
    python fontlang.py          # 汉化 + 字体（无参数时上游默认执行汉化）
    python fontlang.py -lk      # 汉化 + 跳过登录 + 字体
    python fontlang.py -b -l    # Beta 版汉化 + 字体

字体注入触发条件：脚本同级存在 fonts/ 目录（字体文件 + fonts.css 模板），
删除或移走 fonts/ 目录即可关闭字体功能；不需要字体的构建直接使用 lang.py。
字体注册规则来自 rules/font.txt，在 load_rules 阶段追加编译，沿用上游规则引擎。
OFL-1.1.txt 与 NOTICE.md 会随字体一起复制到 ui-process/assets，满足 OFL 的随附要求。
"""
import glob
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile

import lang


class FontTermiusModifier(lang.TermiusModifier):
    """在上游修改器基础上叠加自定义字体注入"""

    def __init__(self, termius_path, args):
        super().__init__(termius_path, args)
        self._patched_version = None

    @property
    def _fonts_dir(self):
        """自定义字体目录（fonts/ 目录存在即启用字体功能）"""
        return os.path.join(self._script_dir, "fonts")

    @property
    def _backup_meta_path(self):
        """备份元数据：记录上次打包产物的 hash，用于识别 Termius 自动更新"""
        return self._backup_path + ".json"

    @property
    def _report_path(self):
        """本次未命中规则报告（extract/ 已 gitignore）"""
        return os.path.join(self._script_dir, "extract", "unmatched-rules.txt")

    @staticmethod
    def _file_sha256(path):
        digest = hashlib.sha256()
        with open(path, "rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _read_backup_meta(self):
        try:
            with open(self._backup_meta_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, ValueError):
            return {}

    def _write_backup_meta(self):
        meta = {"patched_sha256": self._file_sha256(self._original_path)}
        lang.write_file_atomic(self._backup_meta_path, json.dumps(meta) + "\n")

    def _asar_version(self, asar_path):
        """读取 asar 内 package.json 的 version；asar CLI 不可用或文件损坏时返回 None"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                subprocess.run(
                    [lang.get_asar_cmd(), "extract-file", asar_path, "package.json"],
                    cwd=temp_dir, check=True, capture_output=True, text=True,
                )
                with open(os.path.join(temp_dir, "package.json"), "r", encoding="utf-8") as file:
                    return json.load(file).get("version")
        except (OSError, subprocess.CalledProcessError, ValueError):
            return None

    def _replace_backup(self):
        """用当前 app.asar 刷新备份，旧备份保留为 .old（只保留第一份）"""
        old_backup = self._backup_path + ".old"
        if not os.path.exists(old_backup):
            os.replace(self._backup_path, old_backup)
            logging.warning(f"Previous backup preserved at {old_backup}")
        else:
            os.remove(self._backup_path)
        shutil.copy2(self._original_path, self._backup_path)
        if os.path.exists(self._backup_meta_path):
            os.remove(self._backup_meta_path)

    def _refresh_stale_backup(self):
        """Termius 自动更新后 app.asar 会变新，而 .bak 仍是旧版本。

        直接 restore 会把旧版本打包回去，造成版本不匹配。优先比较 asar 内
        package.json 的版本号：版本不同才刷新备份。读不到版本时退回 hash 启发式：
        - 当前 asar 等于备份：未修改，正常；
        - 当前 asar 等于上次打包产物：是我们自己打的包，正常；
        - 其它情况且已有元数据：视为 Termius 已更新，刷新备份。
        没有元数据时保持原备份不动，避免首次升级时误删唯一一份原版。
        """
        if not (os.path.exists(self._backup_path) and os.path.exists(self._original_path)):
            return
        current_version = self._asar_version(self._original_path)
        backup_version = self._asar_version(self._backup_path)
        if current_version and backup_version:
            if current_version != backup_version:
                logging.warning(
                    f"Termius version changed ({backup_version} -> {current_version}); "
                    "refreshing app.asar.bak"
                )
                self._replace_backup()
            return

        current = self._file_sha256(self._original_path)
        backup = self._file_sha256(self._backup_path)
        meta = self._read_backup_meta()
        if current == backup:
            return
        if not meta:
            logging.warning(
                "app.asar differs from app.asar.bak and no backup metadata exists. "
                "If Termius was updated, delete app.asar.bak and rerun to create a fresh backup."
            )
            return
        if current == meta.get("patched_sha256"):
            return
        logging.warning(
            "app.asar does not match the backup or the last patched output; "
            "assuming Termius was updated and refreshing app.asar.bak"
        )
        self._replace_backup()

    def manage_workspace(self):
        """覆盖上游工作区管理：先识别 Termius 更新导致的过期备份"""
        self._refresh_stale_backup()
        super().manage_workspace()

    def pack_to_asar(self):
        """打包后记录产物 hash，供下次运行识别“当前 asar 是否是自己打的包”"""
        super().pack_to_asar()
        self._write_backup_meta()

    def restore_changes(self):
        """还原后一并清理备份元数据"""
        super().restore_changes()
        if os.path.exists(self._backup_meta_path):
            os.remove(self._backup_meta_path)

    def _write_unmatched_report(self):
        """把本次未命中的规则写到 extract/unmatched-rules.txt，便于 Termius 升级后排查"""
        total = [line for _, line, _, _ in self.compiled_rules]
        unmatched = [line for line in total if line not in self.applied_rules]
        os.makedirs(os.path.dirname(self._report_path), exist_ok=True)
        with open(self._report_path, "w", encoding="utf-8") as file:
            file.write(f"# Termius version: {self._patched_version or 'unknown'}\n")
            file.write(f"# unmatched rules: {len(unmatched)}/{len(total)}\n")
            if unmatched:
                file.write("\n".join(unmatched) + "\n")
        logging.info(f"Unmatched rules report: {self._report_path} ({len(unmatched)}/{len(total)})")

    def apply_changes(self):
        """上游修改流程完成后写未命中规则报告"""
        self._patched_version = self._asar_version(self._original_path)
        if self._patched_version:
            logging.info(f"Termius version: {self._patched_version}")
        super().apply_changes()
        self._write_unmatched_report()

    def _compile_font_rules(self):
        """读取并编译 rules/font.txt，追加到上游已编译规则列表尾部

        编译逻辑与上游 load_rules 保持一致；若上游调整 compiled_rules 的
        元组结构，此处需同步（CI 构建失败即提示）。
        """
        rules_path = os.path.join(self._rules_dir, "font.txt")
        if not os.path.isfile(rules_path):
            logging.warning(f"Font rules not found: {rules_path}")
            return
        try:
            for line in lang.read_file(rules_path):
                if lang.is_comment_line(line):
                    continue
                try:
                    old_val, new_val = lang.parse_replace_rule(line)
                    if lang.is_regex_pattern(old_val):
                        self.compiled_rules.append(("regex", line, re.compile(old_val[1:-1]), new_val))
                    else:
                        self.compiled_rules.append(("plain", line, old_val, new_val))
                except ValueError as e:
                    logging.warning(f"Skipping invalid font rule: {line} - {str(e)}")
                except re.error as e:
                    logging.warning(f"Regex compilation error in font rule: {line} - {str(e)}")
        except Exception as e:
            logging.error(f"Failed to load font rules: {e}")

    def apply_fonts(self):
        """注入自定义字体：复制字体文件到 ui-process/assets 并在主 CSS 追加 @font-face

        字体文件来自脚本同级 fonts/ 目录，@font-face 模板来自 fonts/fonts.css。
        幂等：CSS 中已含注入标记时自动跳过。
        """
        assets_dir = os.path.join(self._app_dir, "ui-process", "assets")
        if not os.path.isdir(assets_dir):
            logging.warning(f"ui-process/assets not found: {assets_dir}, skipping font injection")
            return

        # 1. 复制字体文件到 ui-process/assets（与官方内嵌 Nerd Font 同目录）
        copied = 0
        for fname in os.listdir(self._fonts_dir):
            if not fname.lower().endswith((".ttf", ".otf", ".woff2")):
                continue
            src = os.path.join(self._fonts_dir, fname)
            dst = os.path.join(assets_dir, fname)
            shutil.copy2(src, dst)
            logging.info(f"Copied font: {fname}")
            copied += 1
        logging.info(f"Font files copied: {copied}")

        # 2. 复制字体许可文件（OFL 要求随字体一起分发）
        for fname in ("OFL-1.1.txt", "NOTICE.md"):
            src = os.path.join(self._fonts_dir, fname)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(assets_dir, fname))
                logging.info(f"Copied font license: {fname}")

        # 3. 在主 CSS 追加 @font-face（main-*.css，含 xterm 样式特征）
        css_template = os.path.join(self._fonts_dir, "fonts.css")
        if not os.path.isfile(css_template):
            logging.warning("fonts.css template not found, skipping @font-face injection")
            return
        with open(css_template, "r", encoding="utf-8") as f:
            font_faces = f.read()

        injected = 0
        for css_file in glob.glob(os.path.join(assets_dir, "main-*.css")):
            content = lang.read_file(css_file, strip_empty=False)
            if "CodeNewRoman Nerd Font Mono" in content:
                logging.info(f"Fonts already injected in {os.path.basename(css_file)}, skipped")
                continue
            if ".xterm-viewport" not in content:
                logging.debug(f"Skipping non-terminal CSS: {os.path.basename(css_file)}")
                continue
            lang.write_file_atomic(css_file, content + "\n" + font_faces)
            logging.info(f"Injected @font-face into {os.path.basename(css_file)}")
            injected += 1
        if injected == 0:
            logging.warning("No suitable main-*.css found for @font-face injection")
        else:
            logging.info(f"@font-face injected into {injected} CSS file(s)")

    def load_rules(self):
        """上游规则加载完成后，追加编译字体规则并执行字体文件注入

        load_rules 在上游流程中位于解压之后、替换与打包之前，
        正好覆盖字体注入的两个需求：注册规则进引擎、字体文件进资源目录。
        """
        super().load_rules()
        if not os.path.isdir(self._fonts_dir):
            logging.info("fonts/ directory not found, font injection disabled")
            return
        self._compile_font_rules()
        self.apply_fonts()


def main():
    """复用上游 lang.main 的参数解析与调度，仅把修改器替换为字体增强版

    上游 main() 按模块全局名构造 TermiusModifier，运行期间临时替换该名字即可，
    上游 argparse 或调度流程的变更无需在本文件同步维护。
    """
    original = lang.TermiusModifier
    lang.TermiusModifier = FontTermiusModifier
    try:
        lang.main()
    finally:
        lang.TermiusModifier = original


if __name__ == "__main__":
    main()
