# HANDOFF — 现状与待办

> 2026-09-16 · v0.3.2 · 接手先看这份。通道协议细节在 `docs/PROTOCOL-agent-channel.md`，
> 架构图在 `docs/ARCHITECTURE.txt`（保持 .txt，改 .md 会把 ASCII 图折叠掉）。

## 一、现在是什么状态

- **版本 0.3.2**，`master` 已推远端（`git@github.com:Offblink/GhostWorld.git`），tag `v0.3.2`，
  该 tag 带 exe（release 资产里的 zip）——**这是第一次"真发版"**。旧的 tag `v0.3.1` 只有源码，按口径不算。
- **Agent 通道**（0.3.0 那批）：文件轮询 → 阻塞事件通道。游戏侧 `EventBus` + 回环 socket + CLI
  `ghostworld-send` / `ghostworld-wait`；Fungi 侧驱动这条线。硬规矩：通道线程只碰 `cmd_queue` +
  `EventBus`，**永不碰 WorldState**（`tests/test_channel_server.py` 用"碰一下就抛"的假世界钉住）。
- **启动即显示路径**：所有入口启动时都报"代码目录 / 安装根 / 每个运行时写入文件（✓可写）"。
  文本只有一份来源 `metaverse/_paths.startup_lines()`，四处消费：
  | 入口 | 显示位置 |
  |---|---|
  | `ghostworld`、`python -m metaverse.launch` | stdout，每行前缀 `[launcher]` |
  | `launcher.pyw`（GUI 启动器） | 窗口里「路径」组 |
  | `editor.pyw`、`ghostworld-editor`、`python -m editor` | 窗口状态栏右下角常驻 + 悬停给全量；CLI 另打印 |
  | `--where` / `python -m metaverse._paths` | 完整报告（含接 Fungi 的 config 行） |
  用户明确要求：**只说路径，不要附加说明**（不要"装了旧版/换用户级安装"这类劝告），也别把同一个
  目录报两遍——`brief()` 就是因此删掉的。
- **两张 demo 图**（`examples/`，互相配对、门口传送）：`demo_metaverse.json`（16×16 元素样板图）与
  `demo_metaverse2.json`（10×10 明亮小房间）。
- **图标两枚**（2026-09-16 起）：`assets/ghostworld.ico`（启动器/游戏，👻 在夜雾色圆角方块上，
  emoji 字形）与 `assets/ghostworld-editor.ico`（编辑器，**用 QPainter 画的**：编辑器自己那套墙壁调色板
  摆成 3×3、中心格空着套 `#0af` 选中框）。生成器 `tools/make_icon.py --app launcher|editor`，
  16/24/32/48/64/128/256 **逐档渲染**（16/24 px 另有简化画法）。
  任务栏身份也随之分开：`metaverse/_branding.py` 里 `APP_IDS = {launcher: Offblink.GhostWorld,
  editor: …Editor}`——**同一个 AUMID 会把两个窗口并成一个任务栏按钮**，那样两枚图标永远只看得见一枚。
- **打包**（2026-09-16 起）：`tools/build_exe.py --zip` → `dist/GhostWorld/`（`GhostWorld.exe` 启动器/游戏 +
  `GhostWorldEditor.exe` 编辑器 + `GhostWorldCLI.exe` 通道 CLI，共用 `_internal/`）与
  `dist/GhostWorld-<版本>-win64.zip`。见「二、待办 1」。
- 测试基线：`PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch` → **164 collected**。
  门禁 `ruff check .`（配置在 pyproject）。**不要 `ruff format`**：它会重写 43 个既有文件。

## 二、待办

### 1. 打包：本地已通，CI 还没做（用户口径："我需要 exe 的 tag"）
- **口径**：tag 名 = 版本号，**tag 必须对应一个可下载的 exe**；只打源码 tag 不算发版。
  `v0.3.2` 是第一个带 exe 的；`v0.3.1` 只有源码，按口径不算。
  已存在的 `v0.3.1`（2026-09-15）就是"没带 exe"的那种，按新口径**不算发版**，别拿它当模板。
- **已经做完的**：`GhostWorld.spec` + `tools/build_exe.py`（构建后自检：三个 exe 都有图标、
  `GhostWorldCLI.exe where` 能跑且运行时目录可写）；冻结后的运行时写入搬到
  `%LOCALAPPDATA%\GhostWorld\`（`_paths.runtime_dir()`），首次启动把内置 demo 图**只补不改**地拷到用户目录；
  `_update_check` 对 exe 改口为"下载新 exe"；版本号从包内 `pyproject.toml` 读，不靠 pip 元数据。
- **还没做的**：
  - `.github/workflows/` 不存在——CI 构建 + 把 zip 挂到 release 资产，从零建；
  - 打 tag 前先 bump `pyproject.toml`（只有这一处写版本），tag 只指向带 exe 的那次提交。
- **三个 exe 不能合并**：Fungi 用子进程跑通道 CLI 读 stdout，`--noconsole` 的窗口版没有 stdout，
  合进去那条线会静默失效；编辑器有自己的 exe（双击即开、图标独立），但 `GhostWorld.exe --editor` 仍然保留。
  构建脚本会逐个自检：三个都有图标、两个窗口版能活着起窗口、CLI 的 `where` 报的运行时目录可写。

### 2. Fungi 侧（已在 Fungi 工作区实现并实测，**未提交**：那边 push 要用户发话）
打包版没有 `python -m metaverse.cli_channel`。Fungi 的 `fungi/tools/ghostworld.py` 现在按安装形状解析命令：
`<dir>/GhostWorldCLI.exe`（或 PATH 上的）优先，其次源码检出的 `-m` 形式，最后 console script；
发现文件也按形状找（发行包看 `%LOCALAPPDATA%\GhostWorld\.channel.json`，检出看 `<dir>/metaverse/.channel.json`）。
`GhostWorldCLI.exe where` 会把这行口径打出来；`ghostworld_dir` 指 exe 所在目录即可。

路径本身也别让用户懂 JSON 转义：设置页「拓展」下有「游戏目录」输入框（回车即写盘），粘进来的
"右键复制文件地址"原样（带引号 + 单反斜杠）会被规范化成正斜杠并在右上角提示；打开设置页时若发现
`config.json` 读不出来（单反斜杠是非法转义，会让整份配置连 api key 一起失效），当场改写成合法 JSON
（`fungi/config.py` 的 `normalize_dir` / `repair_config_file`）。

### 3. 分清"跑的是哪一份"（实测于 2026-09-15 22:50）
- `site-packages/metaverse/` 里是一份**真副本**（不是 editable 壳）。`ghostworld` / `ghostworld-editor`
  这些 console script，以及在**检出目录之外**跑的 `python -m ...`，用的都是它；在检出根目录跑才用检出。
- 该副本停在 0.3.1 / `e6ffd45`：**不含 2026-09-15/16 的任何改动**（图标、`_branding`、
  `launcher_gui`、冻结路径全没有）。改了代码要 `pip install -e .` 才同步，否则看到的是副本的行为。
- 运行期文件（`.channel.json`、`.instance.lock`、两个 jsonl）也写在**副本目录里**，所以重装前先确认
  没有游戏实例在跑。

### 4. `world.load_state` 会污染新地图（真 bug，未修）
grid 形状不匹配时它会 `ignoring` 掉旧网格，但**照旧恢复实体**——重建 #1 时被塞进来过旧 20×20 的坐标，
物品卡在墙里，可达性测试报出来才知道。修法一行：形状不匹配时跳过实体/物品恢复。
现场：`metaverse/world.py:213 load_state` 附近。

## 三、坑（都实测过，别重踩）

1. **地图文件的 grid 是行主序 `grid[y][x]`**。编辑器存盘写 `st.grid.T`、读盘再 `.T`，游戏也 `.T`。
   手工生成地图必须按行主序写；`validate_entities_on_walls` 要喂**转置后**（世界口径 `[x][y]`）的网格。
2. **引擎自带默认只给 1/2 号墙配色**（其余走 `fallback_wall_color` 压暗）。要 8 种墙型各自可辨，
   必须显式写 `colors.walls` 的 8 条（编辑器存盘会自动带上）。
3. **墙面在游戏里按朝向加阴影**，任何颜色都会变暗；地图的"明亮/阴暗"主要由 sky/floor 决定。
4. **`launcher.pyw` / `editor.pyw` 是 `.pyw`，没有控制台** → 任何 `print` 在那儿都看不见，信息必须进窗口。
   offscreen 平台截图会**丢字形**，验证 GUI 用真机平台 + `QTimer` 抓图。
   `.pyw` **不能被 import**（`import launcher` 找不到，`.pyw` 不在 import 机器的处理表里），所以对话框/逻辑
   要放在能 import 的模块里（启动器因此有了 `metaverse/launcher_gui.py`，`launcher.pyw` 只剩薄壳）。
5. **`python -m editor` 曾直接报 `No module named editor.__main__`**（包里没有 `__main__.py`，
   `__init__.py` 里的 `if __name__ == "__main__"` 永远不跑）。2026-09-16 补了 `editor/__main__.py`。
6. **任务栏图标要两条同时满足**：进程先 `SetCurrentProcessExplicitAppUserModelID`（早于任何窗口），
   窗口再 `setWindowIcon`；exe 侧还要 PyInstaller `--icon`（构建日志出现 `Copying icon to EXE` 才算数）。
   验证别靠肉眼截图——查窗口的 `WM_GETICON`/`GCLP_HICON`，或者像 `tests/test_branding.py` 那样比 pixmap。
7. **PyInstaller 会把 `pkg_resources` 拖进来**（`pygame.pkgdata` 的过时 shim），它的运行时钩子需要
   `jaraco.text`，冻结后 import 即崩。spec 里 `excludes=["pkg_resources", "setuptools", "jaraco", …]`，
   pygame 有 `ImportError` 兜底，安全。
8. **冻结后的 CLI 是管道进程**，Python 默认用 ANSI 代码页（cp936）写 stdout：`✓` 直接 `UnicodeEncodeError`，
   中文变 U+FFFD。`metaverse/_paths.utf8_stdio()` 是唯一实现，`cli_channel`、`launch`、`editor` 都在入口调它。
9. 运行期产物（已 gitignore，别提交）：`metaverse/.channel.json`、`.wait_cursor.json`、
   `agent_commands.jsonl`、`agent_output.jsonl`、`metaverse/builtin_maps/`、`examples/states/*_state.json`、
   `launcher_config.json`、`examples/.last_map`、`snapshots/`、`build/`、`dist/`、`*.egg-info/`。
   `ghostworld.egg-info/` 是当前安装的活元数据，**别删**。
10. 单实例锁 `metaverse/.instance.lock` 按 **pid + 进程创建时间**辨认（pid 会被系统复用，只认 pid 会误杀）。
11. git-bash 下 `curl -o /c/...` 会"成功但找不到文件"，用相对路径或 `C:/...`；SSH 偶发
    `Could not resolve hostname github.com`，重试一次通常就好，推不动时备援是
    `git -c credential.helper='!gh auth git-credential' -c http.proxy=http://127.0.0.1:7897 push https://github.com/Offblink/GhostWorld.git master:master`。
12. **别在构造函数里写配置文件**（Fungi 侧本轮真踩到）：GUI 测试的**模块级 window fixture 先于函数级的
    `CONFIG_PATH` 重定向建立**，构造期写盘会绕过重定向、直接改用户真实的 `config.json`。改成
    `showEvent`（页面真显示时才动盘）并加"真文件一字节不许动"的回归；改完用 sha256 核过一遍。
13. `FluentWindow.switchTo(page)` 传页面对象**静默无效**（注册的是 `_scroll(page, "cfgScroll")` 包装），
    要传 `win.findChild(QScrollArea, "cfgScroll")`。
14. `QIcon(...)` 必须在活着的 `QApplication` 里构造，否则**解释器硬崩**（在 pytest 里表现为"跑一个用例
    进程就没了"，没有 traceback）。

## 四、常用命令

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch   # 测试
ruff check .                                                              # 门禁（别 format）
python -m metaverse._paths                                                # 我在哪、我写哪
python -m metaverse.launch examples/demo_metaverse.json                   # 起游戏
python -m editor                                                          # 起编辑器
python headless_player.py examples/demo_metaverse.json --say 你好 --after 3  # 无头游戏 + 玩家（验通道）
python tools/make_icon.py --app launcher                                  # 重出 👻 图标
python tools/make_icon.py --app editor                                    # 重出编辑器图标
python tools/build_exe.py --zip                                           # 打包（dist/）
dist/GhostWorld/GhostWorldCLI.exe where                                   # 打包版自检
```
