# Termius 中文汉化及功能增强脚本

## 🎉 简介与说明

- [Termius][termius] 汉化脚本。
- 大家可以在官方[功能请求][consideration]进行反馈，让官方尽快支持[中文][localization]。

## ✨ 功能特性

- **一键汉化** - 自动化界面汉化
- **试用功能激活** - 解锁高级特性
- **自定义字体注入** - 内置 CodeNewRoman Nerd Font Mono（英文）+ Resource Han Rounded CN（中文）
- **多平台支持** - Windows/macOS/Linux
- **安全机制** - 自动备份

## 🚀 快速开始

### 📦 前置要求

- Python
- Node.js (用于安装asar)

```bash
npm install -g @electron/asar
```

### 🧑‍💻 基础使用

```bash
# 默认执行汉化操作
python lang.py

# 操作 Beta 版（与正式版 asar 不可混用）
python lang.py -bl
```

### 🪄 高级功能

```bash
# 汉化+试用+样式修改
python lang.py --localize --trial --style

# 汉化+自定义字体注入（CodeNewRoman Nerd Font Mono + Resource Han Rounded CN）
# 字体功能由 fontlang.py 提供：fonts/ 目录存在即自动注入，无需额外参数
python fontlang.py --localize

# 仅激活试用功能
python lang.py --trial

# 还原到初始状态（需要 asar CLI）
python lang.py --restore

# 仅还原 app.asar（不依赖 asar CLI，适合 asar 未安装时回滚）
python tools/restore.py

# 打补丁前只读体检（不修改 Termius，结果写入 extract/rule-report.txt）
python tools/report_rules.py

# 查看当前安装状态（版本/是否已打补丁/备份/字体/最近报告）
python tools/status.py

# 打补丁后自检（asar 可读/版本一致/字体与许可已打包/CSS 标记存在）
python tools/verify_asar.py

# 搜索特定字符串
python lang.py --find "term1" "term2"

# 提取所有字符串
python lang.py --extract
```

## 🔬 参数详解

| 参数                | 简写   | 功能说明       | 示例                                  |
|-------------------|------|------------|-------------------------------------|
| `--beta`          | `-b` | 操作 Beta 版（默认操作正式版，两者 asar 不可混用） | `python lang.py -bl`               |
| `--localize`      | `-l` | 汉化操作(默认)   | `python lang.py`                    |
| `--trial`         | `-t` | 激活试用功能     | `python lang.py -lt`                |
| `--skip-login`    | `-k` | 跳过登录验证     | `python lang.py -lk`                |
| `--style`         | `-s` | 样式修改       | `python lang.py -ls`                |
| `--restore`       | `-r` | 还原操作       | `python lang.py -r`                 |
| `--find <关键词...>` | `-f` | 多条件联合搜索    | `python lang.py -f "term1" "term2"` |
| `--extract`       | `-e` | 提取所有可能的字符串 | `python lang.py -e`                 |
| `--verbose`       | `-v` | 设置日志级别     | `python lang.py -v DEBUG`           |

> **自定义字体**：`fontlang.py` 用法与 `lang.py` 完全一致，运行时若存在 `fonts/` 目录则自动注入字体（默认终端字体改为 CodeNewRoman Nerd Font Mono，字体列表追加 CodeNewRoman + Resource Han Rounded CN）；不需要字体的构建直接使用 `lang.py`。

> **字体许可**：`fonts/` 内字体均为 SIL OFL 1.1。`fonts/NOTICE.md` 记录版权与来源，`fonts/OFL-1.1.txt` 是完整许可文本；`fontlang.py` 会把两者一起复制进 `ui-process/assets/`，随 asar 分发。

> **关于 `installer/`**：该目录来自上游，脚本内的仓库地址指向上游，安装的是**不含字体**的版本。需要字体请使用 `fontlang.py` 或本仓库 Releases 中的 `*-font.asar`。

## 📂 相关文件结构

```markdown
rules/
├── trial.txt       # 试用功能规则(-t/--trial时加载)
├── localize.txt    # 汉化规则(-l/--localize时加载)
├── skip_login.txt  # 登录跳过规则(-k/--skip-login时加载)
├── style.txt       # 样式修改规则(-s/--style时加载)
└── font.txt        # 自定义字体规则(fontlang.py 自动加载)
fonts/
├── CodeNewRomanNerdFontMono-Regular.otf   # 英文字体（Nerd Font）
├── CodeNewRomanNerdFontMono-Bold.otf
├── CodeNewRomanNerdFontMono-Italic.otf
├── ResourceHanRoundedCN-Regular.ttf       # 中文字体（思源圆体简体）
├── fonts.css                               # @font-face 注入模板
├── NOTICE.md                               # 字体版权与来源
└── OFL-1.1.txt                             # SIL OFL 1.1 许可全文
tools/
├── lint_rules.py   # 规则静态检查（格式/正则/顺序不变式）
├── report_rules.py # 打补丁前只读体检（不修改 Termius）
├── status.py       # 当前安装/补丁/备份/字体状态
├── verify_asar.py  # 打补丁后自检（版本/字体/许可/CSS）
└── restore.py      # 仅还原 app.asar（不依赖 asar CLI）
tests/              # pytest 测试
extract/
├── app.asar.unpack      # 解包出的所有文件
├── allstring.txt        # 所有可能的字符串
└── unmatched-rules.txt  # 本次未命中的规则（每次补丁后生成）
```

### 🎨 自定义字体说明

- 字体文件放在 `fonts/` 目录（.ttf/.otf/.woff2），运行 `fontlang.py` 时自动复制到 Termius 的 `ui-process/assets/` 内
- `fonts/fonts.css` 是 `@font-face` 注入模板，可自行修改（字体名、字重、来源文件需与 `fonts/` 内文件名一致）
- `rules/font.txt` 控制字体在 Termius 中的注册：默认终端字体、设置面板字体候选列表、字体常量映射
- 注入是幂等的：重复执行不会重复追加
- 字体均为开源 SIL OFL 协议，仅用于本地学习测试

## 🤷 手动汉化

如果没有相关环境，可以手动汉化。

1. 前往 [Releases][releases] 下载对应版本的 `app-xxx.asar` 文件。
2. 找到 Termius 安装目录，通常位置为:
  - **Windows**: `C:\Users\你的用户名\AppData\Local\Programs\Termius`。
  - **Linux**: `/opt/Termius`。
  - **MacOS**: `/Applications/Termius.app/Contents`。

  <details>
  <summary>对于 Beta 用户</summary>
      
  - **Windows**: `C:\Users\你的用户名\AppData\Local\Programs\Termius Beta`。
  - **Linux**: `/opt/Termius Beta`。
  - **MacOS**: `/Applications/Termius Beta.app/Contents`。
      
  </details>
  
3. 将下载的 `app-xxx.asar` 文件重命名为 `app.asar` 后覆盖 `resources` 文件夹下的 `app.asar` 文件。
  - **注意**，macOS 替换后需要运行 [osxfix.sh](macos/osxfix.sh) 重新计算文件 hash 后方可使用。
  - **注意**，新版 Termius 启用了 asar 完整性校验，Windows/Linux 需先关闭该熔丝方可启动（详见 [FAQ Q3](#q3-替换-appasar-后应用无法启动integrity-check-failed)）：
    ```bash
    npx @electron/fuses write --app "C:\Users\你的用户名\AppData\Local\Programs\Termius\Termius.exe" EnableEmbeddedAsarIntegrityValidation=off
    ```
    <details>
      <summary>Termius Beta 用户请执行此命令</summary>
      
      ``` shell
      npx @electron/fuses write --app "C:\Users\你的用户名\AppData\Local\Programs\Termius Beta\Termius Beta.exe" EnableEmbeddedAsarIntegrityValidation=off
      ```
    </details>

4. 如果你不想自动更新，请删除 `app-update.yml` 文件。
   - 每个平台的 Release 同时提供 `SHA256SUMS-<platform>.txt`，下载后在 asar 同目录执行 `sha256sum -c SHA256SUMS-<platform>.txt` 即可校验。
5. 最后，如果没有想要的版本，可在 [Fork][fork] 本项目后前往仓库的 **Settings > Secrets and variables > Actions > Variables** 页面定义变量:
  - **Name**: `RELEASE_LIST`
  - **Value**: `l`
  - 默认只发布 `app-*-localize-font.asar`（汉化+自定义字体）；如需其他变体可将值改为 `lt`（加试用）、`lk`（加跳过登录）或多组逗号分隔如 `l,lk,lt`（l=汉化，t=试用，k=跳过登录，所有产物均自动带字体）。
  - **注意**：本仓库的字体版发布由 `release-font.yml` 手动触发（Actions → Release Font Platforms → Run workflow）；若启用了上游的 `Release Platforms` / `Release Beta Platforms` workflow，它们会构建不含字体的版本并占用相同版本号，请在仓库的 **Actions** 页面将其禁用，只保留 `Release Font Platforms`。

## 🧪 开发与测试

规则是本项目的主体，修改 `rules/*.txt` 后请先跑静态检查和测试：

```bash
pip install -r requirements-dev.txt
python tools/lint_rules.py rules
python -m pytest -q
```

`lint_rules.py` 会检查：

- 规则格式、正则编译、空替换、重复项；
- **顺序不变式**：同一文件里，宽规则必须排在窄规则之后，否则窄规则永远不会命中；
- 跨文件遮蔽只告警（是否同时加载取决于 `-t/-k/-s` 组合）。

CI 在 push / PR 时自动执行同样的检查。

如果本机有 `make`，也可以用快捷入口：

```bash
make doctor   # 状态 + 自检 + lint + 测试
make status   # 查看当前安装/补丁状态
make report   # 只读体检当前 Termius
make verify   # 打补丁后自检
make patch    # 汉化 + 字体
make check    # lint + pytest
make restore  # 还原 app.asar
```

## 📱 关于安卓版

- 目前只有汉化功能，暂无其他功能。并且部分词条在源码中，暂未汉化。
- 由于手机端和桌面端版本号不同，因此安卓版本不会发布在 `Releases` 中，而是暂时托管在 [Actions][localize-android]。本 fork 已禁用该定时任务；如需 Android 汉化，可在 Actions 页面手动运行 `Localize Android`。注意，这个是需要**登录**才可以下载的。
- 若你计划 [Fork][fork] 此项目，请在 [Fork][fork] 后前往仓库的 **Settings > Secrets and variables > Actions > Secrets** 页面，点击 <kbd>New repository secret</kbd> 定义私密变量。
  - **Name**: `APK_SIGN_PROPERTIES`
  - **Value**: 填写 [apk.sign.properties.example](android/apk.sign.properties.example) 文件内容（请根据需要修改文件内容）

- 可选配置（`Github Action`）：
  - 添加自定义签名文件，可以覆盖安装 apk
  - 首先通过命令生成一个.jks签名文件
      ```bash
    # 然后通过命令编码成一个 Base64 的文件
    base64 -w 0 Termius_zh.jks > Termius_zh_base64.txt
      ```
  - 后前往仓库的 **Settings > Secrets and variables > Actions > Secrets** 页面，点击 <kbd>New repository secret</kbd> 定义私密变量。

  - **Name**: `SIGNING_KEY`
  - **Value**: 填写 [Termius_zh_base64.txt](Base64生成的文件) 文件内容（请根据需要修改文件内容）

### 🤖 关于脚本

- 安卓相关资源均存放在 [android](android) 目录下。
- 所需工具：
  - python（运行环境）
  - zipalign（对齐工具 `sudo apt install -y zipalign` 安装）
  - apksigner（签名工具 `sudo apt install -y apksigner` 安装）
  - keytool（密钥生成工具，集成在 JDK 中）
- 运行：
   ```bash
   # 进入安卓目录
   cd android
   # 配置签名信息（请自行修改内容）
   mv apk.sign.properties.example apk.sign.properties
   # 安装依赖
   pip install -r requirements.txt
   # 运行脚本
   python apktools.py
   ```

## 📖 常见问题

### Q1: ModuleNotFoundError: No module named 'tkinter'

**Q：** Python 缺少 tkinter 图形界面库。

> 现在只有需要弹出目录选择框时才依赖 tkinter；`tools/status.py`、`tools/report_rules.py`、`tools/verify_asar.py` 和 `tools/restore.py` 配合 `--path` 可以在无 tkinter 环境使用。

**A：**

- **Windows:** tkinter 通常随 Python 一起安装，如缺失请重新安装 Python 并勾选 "tcl/tk and IDLE" 选项。
- **macOS:** 使用 Homebrew 安装：`brew install python-tk`
- **Linux (Ubuntu/Debian):** `sudo apt-get install python3-tk`
- **Linux (Fedora):** `sudo dnf install python3-tkinter`

### Q2: PermissionError: Permission denied

**Q：** 没有足够的权限访问或修改 Termius 安装目录。

**A：**

- **Windows:** 以管理员身份运行终端（右键 → 以管理员身份运行）
- **macOS/Linux:** 在命令前添加 `sudo`，例如：`sudo python lang.py -l`
- 确保 Termius 已完全关闭，没有后台进程占用文件
- 请检查权限，确保当前用户有 `resources` 目录的写权限

### Q2.1: 脚本提示选择目录，但选完安装目录后报错找不到 app.asar

**Q：** 脚本实际需要的是安装目录下的 `resources` 子目录（`app.asar` 在其中），只提示“安装目录”容易让用户选错层级。

**A：** 现在两种选择都可以：

- 选安装根目录（如 `C:\Users\你的用户名\AppData\Local\Programs\Termius`），脚本会自动向下定位 `resources`。
- 直接选 `resources` 目录本身。
- macOS 选 `Termius.app` 或 `Contents` 也会自动定位到 `Contents/Resources`。
- 若所选目录下确实没有 `app.asar`，脚本会提示具体路径并重新弹出选择框，而不是直接退出。

### Q3: 替换 app.asar 后应用无法启动（Integrity check failed）

**Q：** 新版 Termius 启用了 Electron 的 asar 完整性校验（`EnableEmbeddedAsarIntegrityValidation`），替换后的 `app.asar` 因哈希不匹配而被阻止启动。

**A：**

- 使用脚本汉化：`lang.py` 会自动关闭该校验，无需额外操作。
- 手动汉化：需先用 `@electron/fuses` 关闭熔丝（以 Windows 为例，macOS/Linux 路径见上方手动汉化章节）：
  ```bash
  npx @electron/fuses write --app "C:\Users\你的用户名\AppData\Local\Programs\Termius\Termius.exe" EnableEmbeddedAsarIntegrityValidation=off
  ```

  <details>
      <summary>Termius Beta 用户请执行此命令</summary>
    
     ``` shell
      npx @electron/fuses write --app "C:\Users\你的用户名\AppData\Local\Programs\Termius Beta\Termius Beta.exe" EnableEmbeddedAsarIntegrityValidation=off
     ```
  </details>

- macOS 无需此操作，运行 [osxfix.sh](macos/osxfix.sh) 更新预期 hash 即可。

### Q4: 自动更新失败（Code signature did not pass validation）

**Q：** Termius 后台更新时报 `did not pass validation`，或更新后应用无法启动。

**A：**

- 这是替换 `app.asar` 破坏代码签名导致的，内置自动更新无法继续使用，请前往 [官网](https://termius.com) 手动下载安装新版。

### Q5: 替换 app.asar 后，软件异常

**Q：** 如登录态丢失，且无法重新登陆、软件 logo 错误等

**A：**

- 这是因为使用了与版本不匹配的 asar 导致的，请确保使用了对应版本的 asar，同时**正式版与 Beta 版的 asar 不可混用**

## 🛠️ 维护说明

- `README.md` 由本 fork 维护；`sync-upstream.yml` 合并上游时若 README 冲突，会保留本仓库版本；`.gitignore` 冲突会合并双方条目；其它文件冲突则直接失败并中止合并。
- `installer/` 是上游原样文件，脚本内的仓库地址指向上游，安装的是不含字体的版本。
- `lang.py` 有一处 fork 小改动：`tkinter` 改为在 `select_directory()` 内按需导入，便于无 GUI 环境使用 report/restore；上游若改到这段，同步会以冲突形式提示。
- 规则修改后请运行 `python tools/lint_rules.py rules && python -m pytest -q`，CI 也会在 push/PR 时执行。
- Termius 升级后，先运行 `python tools/report_rules.py` 做只读体检（不修改 Termius），再决定是否打补丁；补丁后未命中的规则也会写到 `extract/unmatched-rules.txt`。
- 不确定当前是否已打补丁时，先运行 `python tools/status.py`；`--json` 可输出机器可读结果。
- 打补丁后运行 `python tools/verify_asar.py`；`--strict` 会把备份缺失、CSS 标记缺失等 warning 也视为失败。
- Termius 自动更新后，脚本会优先比较 `app.asar` 与备份内 `package.json` 的版本号：版本不同会自动刷新备份，旧备份保留为 `app.asar.bak.old`。读不到版本时才退回 `app.asar.bak.json` 的 hash/元数据判断。
- `app.asar.bak.json` 只由 `fontlang.py` 维护；如果交替使用 `lang.py` 和 `fontlang.py`，切换前先运行 `python tools/restore.py`，避免元数据与实际产物不一致。

## 🔔 注意事项

- 该项目仅适用于本地学习和测试，不支持在线功能。
- 使用汉化包可能会影响 Termius 软件的正常更新。
- 在执行任何操作之前，请确保备份 Termius 的相关文件。

## 📜 免责声明

- 本仓库包括发布页内的所有文件仅供学习和交流，请勿用于任何非法用途，严禁二次出售，请在下载后的24小时内删除！如有侵权请联系删除！
- 用于测试和学习研究，禁止用于商业用途，不能保证其合法性、准确性、完整性和有效性，请根据情况自行判断。
- 本人对任何问题概不负责，包括但不限于由任何脚本错误导致的任何损失或损害，使用即表示知晓风险。
- 保留随时终止项目的权利。

<!-- LINK -->
[termius]: https://termius.com
[consideration]: https://ideas.termius.com/tabs/1-under-consideration
[localization]: https://ideas.termius.com/c/82-chinese-localization
[releases]: https://github.com/ArcSurge/Termius-Pro-zh_CN/releases
[fork]: https://github.com/ArcSurge/Termius-Pro-zh_CN/fork
[secrets]: https://github.com/ArcSurge/Termius-Pro-zh_CN/settings/secrets/actions
[variables]: https://github.com/ArcSurge/Termius-Pro-zh_CN/settings/variables/actions
[actions]: https://github.com/ArcSurge/Termius-Pro-zh_CN/actions
[localize-android]: https://github.com/ArcSurge/Termius-Pro-zh_CN/actions/workflows/localize-android.yml
