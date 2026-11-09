# -*- coding: utf-8 -*-
"""Termius 字体注入入口（叠加层脚本）

本文件是 fork 的 Python 字体叠加层入口：字体注入通过子类化 TermiusModifier，
并在运行期间临时替换 lang 模块内的类引用实现，不复制上游业务逻辑。
备份/还原安全由 lang.py 混入 backup_guard.py 提供，与 fontlang.py 共用。

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
import logging
import os
import re
import shutil

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
    def _report_path(self):
        """本次未命中规则报告（extract/ 已 gitignore）"""
        return os.path.join(self._script_dir, "extract", "unmatched-rules.txt")

    def _refresh_stale_backup(self):
        """兼容旧调用：委托给 lang 的备份新鲜度检查"""
        return self.ensure_backup_current()

    def pack_to_asar(self):
        """打包后记录产物 hash；基类已记录时跳过重复写（兼容测试替换基类实现）"""
        super().pack_to_asar()
        if not self._read_backup_meta().get("patched_sha256"):
            self._record_patch_metadata()

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
        """读取并编译 rules/font.txt，插到已编译规则列表最前面

        字体规则必须最先执行：style.txt 里的 ``CircularXX`` 宽替换会先把
        ``fontFamily:"CircularXX, sans-serif"`` 等字体锚点改掉，字体规则若
        追加在尾部就再也匹配不到。编译逻辑与上游 load_rules 保持一致；若上游
        调整 compiled_rules 的元组结构，此处需同步（CI 构建失败即提示）。
        """
        rules_path = os.path.join(self._rules_dir, "font.txt")
        if not os.path.isfile(rules_path):
            logging.warning(f"Font rules not found: {rules_path}")
            return
        font_rules = []
        try:
            for line in lang.read_file(rules_path):
                if lang.is_comment_line(line):
                    continue
                try:
                    old_val, new_val = lang.parse_replace_rule(line)
                    if lang.is_regex_pattern(old_val):
                        font_rules.append(("regex", line, re.compile(old_val[1:-1]), new_val))
                    else:
                        font_rules.append(("plain", line, old_val, new_val))
                except ValueError as e:
                    logging.warning(f"Skipping invalid font rule: {line} - {str(e)}")
                except re.error as e:
                    logging.warning(f"Regex compilation error in font rule: {line} - {str(e)}")
        except Exception as e:
            logging.error(f"Failed to load font rules: {e}")
            return
        self.compiled_rules = font_rules + self.compiled_rules

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
        if copied == 0:
            logging.warning("No font files found in fonts/; the font build would have no custom fonts")

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
