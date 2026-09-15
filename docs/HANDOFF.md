# HANDOFF — 现状与待办

> 2026-09-15 · v0.3.1 · 接手先看这份。通道协议细节在 `docs/PROTOCOL-agent-channel.md`，
> 架构图在 `docs/ARCHITECTURE.txt`（保持 .txt，改 .md 会把 ASCII 图折叠掉）。

## 一、现在是什么状态

- **版本 0.3.1**，`master` 已推远端（`git@github.com:Offblink/GhostWorld.git`），tag `v0.3.1`。
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
- **两张 demo 图**（`examples/`，互相配对、门口传送）：
  - `demo_metaverse.json` = **元素样板图**：16×16 三进室内（每进之间一道墙 + 一个窄门），
    一进 8 种墙型各一块交错成两排，二进内柱 + 物品，三进深处才是门；实体 12 个（NPC 带 `dialogue`、
    10 个物品覆盖 `pickup_label`/三种动画/两种遮挡/`capture_for`/`metadata`/`invisible`、1 扇门）；
    配色是夜雾幽绿一套（天空 `[26,28,44]`→`[116,132,128]`，地板 `[58,66,60]`）。
  - `demo_metaverse2.json` = 明亮小房间：10×10 正方形、亮天蓝 + 亮草绿、**只有一扇回程门**（中心）。
- 测试基线：`PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch` → **159 collected**。
  门禁 `ruff check .`（配置在 pyproject）。**不要 `ruff format`**：它会重写 43 个既有文件。

## 二、待办

### 1. 给编辑器设计图标（用户点名的下一件事）
- 主题：**幽灵 👻** —— 把 emoji 渲染成 PNG（本机 PySide6 能渲彩色 emoji，PyQt5 不行；技能
  `app-icon-to-avatar-png` 记了公式与验证法）。
- 落点与验收（实测口径见技能 `qtgui-verify-this-box`）：
  - `QApplication.setWindowIcon(QIcon(...))` → 窗口 / Alt-Tab；
  - Windows **任务栏**分组要 `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Vendor.App")`，
    且必须在创建任何窗口之前调用，否则任务栏按 `python.exe` 归类、显示 python 的图标；
  - 三个编辑器入口都要覆盖：`editor.pyw`、`ghostworld-editor`（= `editor:main`）、`python -m editor`；
  - `.ico` 单档 64×64 就够，要高分屏更锐就塞 16/32/48/256。
- 仓库**没有 assets/ 目录**，要新建；加完文件跑门禁。

### 2. 发版 = 先出 exe，再打 tag（用户 2026-09-15 明确要求："我需要 exe 的 tag"）
- **口径**：tag 名 = 版本号，**tag 必须对应一个可下载的 exe**；只打源码 tag 不算发版。
  已存在的 `v0.3.1`（2026-09-15）就是"没带 exe"的那种，按新口径**不算发版**，别拿它当模板。
- 仓库现状：**没有任何打包脚手架**（无 `.github/`、无 `*.spec`、无 `tools/`、无 `dist/`、无图标资源），从零建。
- 必须覆盖的入口（`pyproject [project.scripts]` + `launcher.pyw`）：

  | 入口 | 用途 | 关键约束 |
  |---|---|---|
  | `ghostworld` = `metaverse.launch:main` | 游戏 | 窗口版（`--noconsole`）|
  | `ghostworld-editor` = `editor:main` | 编辑器 | 窗口版 + 图标 |
  | `launcher.pyw` | GUI 启动器（用户平时双击的）| 窗口版 |
  | `ghostworld-send` / `ghostworld-wait` | 通道 CLI，**Fungi 靠它驱动角色** | **必须保留控制台**，绝不能 `--noconsole` |

  → 一个 `--noconsole` 的单体 exe 会自废武功：Fungi 那条线用子进程调这两个 CLI。要么出两个二进制
  （窗口版 + 控制台版），要么单 exe 带子命令 + 一个控制台启动器。
- **冻结后的路径语义要改**（现在 `metaverse/_paths.py` 假设"代码旁边可写"）：PyInstaller 下
  `PACKAGE_DIR` 是解包出来的临时目录、`ROOT_DIR` 没有 pyproject（`version_string()` 会回落到元数据），
  而**运行时写入必须搬到用户目录**（如 `%LOCALAPPDATA%\GhostWorld\`）——否则装在 Program Files
  这种只读位置直接崩。`.channel.json` 要落在两个进程都能找到的地方，Fungi 侧的发现逻辑跟着改。
- `_update_check` 现在给的更新命令是 `pip install --upgrade git+...`（`metaverse/_update_check.py:59`），
  exe 分发下要改成"下载新 exe"。它读的远端版本是 raw 上的 `pyproject.toml`，不依赖 GitHub release。
- 建议顺序：图标（待办 1）→ 打包脚本/CI → 出 exe 实测（含"Fungi 侧 CLI 仍然可用"）→ 打 tag + 把 exe
  挂到 release 资产。

### 3. 分清"跑的是哪一份"（实测于 2026-09-15 22:50）
- `site-packages/metaverse/` 里是一份**真副本**（不是 editable 壳）。`ghostworld` / `ghostworld-editor`
  这些 console script，以及在**检出目录之外**跑的 `python -m ...`，用的都是它；在检出根目录跑才用检出。
- 该副本当前是 **0.3.1 但只到 `e6ffd45`**：包含 `startup_lines()`，却也还有已删除的 `brief()` 和
  "不可写"劝告，即**不含** `a646d5e` 那次"只报路径"的简化。用户此前看到的重复横幅就出自它的旧形态。
- 改了代码后要重装（`pip install -e .` 最省事，之后跑的就是检出）否则看到的是副本的行为。
- 运行期文件（`.channel.json`、`.instance.lock`、两个 jsonl）也写在**副本目录里**（22:49 有实例在跑），
  所以重装前先确认没有游戏实例，免得把正在写入的目录换掉。

### 4. `world.load_state` 会污染新地图（真 bug，未修）
grid 形状不匹配时它会 `ignoring` 掉旧网格，但**照旧恢复实体**——我重建 #1 时被塞进来过旧 20×20 的坐标，
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
5. 运行期产物（已 gitignore，别提交）：`metaverse/.channel.json`、`.wait_cursor.json`、
   `agent_commands.jsonl`、`agent_output.jsonl`、`examples/states/*_state.json`、`launcher_config.json`、
   `examples/.last_map`、`snapshots/`、`build/`、`*.egg-info/`。
   `ghostworld.egg-info/` 是当前安装的活元数据，**别删**（删了 `_update_check` 会报错）。
6. 单实例锁 `metaverse/.instance.lock` 按 **pid + 进程创建时间**辨认（pid 会被系统复用，只认 pid 会误杀）。
7. git-bash 下 `curl -o /c/...` 会"成功但找不到文件"，用相对路径或 `C:/...`；SSH 偶发
   `Could not resolve hostname github.com`，重试一次通常就好，推不动时备援是
   `git -c credential.helper='!gh auth git-credential' -c http.proxy=http://127.0.0.1:7897 push https://github.com/Offblink/GhostWorld.git master:master`。

## 四、常用命令

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch   # 测试
ruff check .                                                              # 门禁（别 format）
python -m metaverse._paths                                                # 我在哪、我写哪
python -m metaverse.launch examples/demo_metaverse.json                   # 起游戏
python -m editor                                                          # 起编辑器
python headless_player.py examples/demo_metaverse.json --say 你好 --after 3  # 无头游戏 + 玩家（验通道）
```
