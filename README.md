# GhostWorld

Raycasting 3D engine + metaverse server + map editor + AI Agent platform.

从 2D 网格地图渲染第一人称视角。提供引擎库、地图编辑器、多人元宇宙、AI Agent 平台。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GhostEngine Metaverse v2                         │
│                    同进程架构 · 无网络 · 共享 WorldState                  │
└─────────────────────────────────────────────────────────────────────────┘

                              ┌───────────────┐
                              │  地图编辑器    │
                              │  (PySide6)    │
                              │               │
                              │ 传送门全地图扫描│
                              │ 跨图即时双向配对│
                              │ 墙壁-实体互斥  │
                              │ 定时自动保存   │
                              │ 越界幽灵清理   │
                              └──────┬────────┘
                                     │ save/load + validate
                                     ▼
                           ┌─────────────────┐
                           │   .json 地图文件 │
                           │ examples/*.json │
                           └────────┬────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
   │   launch.py      │  │   runner.pyw     │  │ headless_agent.py│
   │   launcher.py    │  │ 单机预览(Ctrl+R)  │  │   无头调试模式    │
   └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
            │                     │                     │
            └─────────────────────┼─────────────────────┘
                                  │
                                  ▼
   ┌──────────────────────────────────────────────────────────────────────┐
   │                         metaverse 核心                               │
   │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────────┐  │
   │  │local_client │  │local_agent  │  │          server.py           │  │
   │  │  (pygame)   │  │  (omp)      │  │   say/move/goto/turn/pos     │  │
   │  │ 跨图深拷贝   │  │ 0.3s 轮询   │  │   pickup/place/give/look     │  │
   │  └──────┬──────┘  └──────┬──────┘  │  set_entity/edit_map/set_cell│  │
   │         └────────┬───────┘         │   传送门坐标越界保护           │  │
   │                  ▼                 └──────────────┬───────────────┘  │
   │           ┌──────────────────┐                    │                  │
   │           │    WorldState    │ ← 唯一权威数据源    │                  │
   │           │ grid/items/maps  │   碰撞检测 · A*寻路 │                  │
   │           │ avatars/inv      │   传送门 · 拾取     │                  │
   │           │ 深拷贝隔离Item    │   越界幽灵自动清理  │                  │
   │           └──────────────────┘                    │                  │
   └───────────────────────────────────────────────────┼──────────────────┘
                                                       │
   ┌───────────────────────────────────────────────────┼──────────────────┐
   │                       ghostengine 渲染引擎         │                  │
   │  ┌────────────┐  ┌────────────┐  ┌────────────┐   │  ┌────────────┐  │
   │  │ renderer   │  │ entity     │  │ animation  │   │  │ minimap    │  │
   │  │ 7阶段管线   │  │ 投影数学   │  │ 悬浮/脉动   │   │  │ 小地图渲染  │  │
   │  │ 射线投射    │  │ 遮挡裁剪   │  │ 旋转/GIF    │   │  │            │  │
   │  └────────────┘  └────────────┘  └────────────┘   │  └────────────┘  │
   └──────────────────────────────────────────────────────────────────────┘
```

> 完整架构图见 [docs/ARCHITECTURE.txt](docs/ARCHITECTURE.txt)

| 文档 | 内容 |
|---|---|
| [docs/HANDOFF.md](docs/HANDOFF.md) | 现状与待办（接手先看这份） |
| [docs/ARCHITECTURE.txt](docs/ARCHITECTURE.txt) | 完整架构图、数据流、命令通道 |
| [docs/SPEC.md](docs/SPEC.md) | 需求对照（v2 完成项） |
| [docs/PROTOCOL-agent-channel.md](docs/PROTOCOL-agent-channel.md) | Agent 通道协议（给别的程序接入用） |
| [docs/DESIGN-agent-channel.md](docs/DESIGN-agent-channel.md) | Agent 通道重写设计（已确认） |
| [docs/PLAN-agent-channel.md](docs/PLAN-agent-channel.md) | Agent 通道重写实施计划（14 个任务已完成） |

## 安装

**环境要求：Python 3.10 – 3.13。Python 3.14 暂不支持**（pygame 尚无预编译包）。

```bash
pip install git+https://github.com/Offblink/GhostWorld.git
```

依赖：`pygame`, `numpy`。编辑器额外需要 `PySide6`（`pip install ghostworld[editor]`）。

### 常见安装问题

| 症状 | 原因 | 解决 |
|---|---|---|
| `ModuleNotFoundError: No module named 'distutils.msvccompiler'` | Python 3.14 移除了 distutils，pygame 尚未适配 | 降级到 Python 3.12 或 3.13 |
| `SSL: UNEXPECTED_EOF_WHILE_READING` | 中国大陆网络无法直连 GitHub / SDL 下载源 | 设置代理 `set HTTPS_PROXY=http://127.0.0.1:7890` 后重试 |
| `pygame.error: No available video device` | 无头环境（SSH / Docker / WSL 无桌面） | 确认有图形环境；纯命令行使用需装 `pygame` 后调用引擎 API 不创建窗口 |
| pygame 源码编译失败 | 缺少 Visual Studio Build Tools | 先 `pip install pygame` 安装预编译 wheel，或安装 VS Build Tools |

> **中国大陆用户建议**：如 `pip install git+https://` 速度极慢或超时，先设置代理再执行安装命令。

## 更新

```bash
pip cache purge && pip install --upgrade git+https://github.com/Offblink/GhostWorld.git
```

> ⛔ **开发禁令**：**禁止 WebSocket 协议与 asyncio 网络 I/O**；允许 `127.0.0.1` 上的同步 socket + 线程向队列投递。
> Windows 上 WebSocket 存在未修复的严重 bug，曾导致项目崩溃、数据丢失；MCP 同样禁用。
> 病因是「Windows WS + 异步网络 + 跨线程改世界」，所以还有一条硬约束：**`WorldState` 只在帧循环
> 线程里被修改**，通道线程只能把命令投进 `cmd_queue`、把事件投进 `EventBus`。

### 缓存策略

启动时 `launch.py` 设置 `sys.dont_write_bytecode = True`，**全程不产生 `.pyc` 文件**。
每次运行从 `.py` 源码直接编译，彻底杜绝 `__pycache__` 导致的旧代码污染。
如需手动清理历史残留，运行 `pyclean`（项目附带）。


### 一键启动元宇宙

```bash
python -m metaverse.launch                        # 默认地图
python -m metaverse.launch my_map.json             # 指定地图
python launcher.py                                 # GUI 启动器（需 PySide6）
```


### Agent 控制（通道）

Agent（`omp`、别的 harness、任何 bot）通过本机通道驱动自己的角色：游戏进程内起一个
`127.0.0.1` 的 socket 服务，端口与 token 落在 `metaverse/.channel.json`。命令不用轮询，
发一条拿一个 ack；等唤醒是**阻塞**的：

```bash
ghostworld-send '{"cmd":"pos"}'                    # 打印 ack JSON，退出码 0
ghostworld-send '{"cmd":"say","message":"来了"}'
ghostworld-wait --timeout 25                       # 阻塞：玩家一发言就打印一行事件 JSON
ghostworld-wait --all --follow                     # 常驻观察者（含 see/goto_done 等非唤醒事件）
```

**唤醒语义**：Agent 常驻 `ghostworld-wait`，玩家发言即被唤醒；不发言时零开销（阻塞在 socket 上，
不轮询、不烧 CPU、不烧 token）。思考期间玩家说的第二句会在通道里排队，下次 `wait` 一次性拿到。

| 退出码 | `ghostworld-send` | `ghostworld-wait` |
|---|---|---|
| 0 | 收到 ack | 打印了事件 |
| 1 | 连上了但没有 ack（帧循环没在跑） | — |
| 2 | 连不上（游戏没在跑）／用法错误 | 同左 |
| 3 | — | 超时：期限内没有事件 |

命令的 JSON 与下面的文件通道完全一致（`cmd` + 参数）。**旧文件通道仍可用**：向
`metaverse/agent_commands.jsonl` 写一行 JSON，agent 每 0.3s 读一次并交给帧循环执行（兼容层，
写进去的命令不再有读后即删的竞态）。
```json
{"cmd":"say","message":"hello"}
{"cmd":"move","x":10,"y":3}
{"cmd":"goto","x":5,"y":5}
{"cmd":"turn","x":10,"y":5}
{"cmd":"pos"}
{"cmd":"inv"}
{"cmd":"look"}
{"cmd":"pickup"}
{"cmd":"place","item_id":"gem_B","x":3.5,"y":3.5}
{"cmd":"give","target":"player","item_id":"token"}
{"cmd":"edit_map","operations":[
  {"op":"set_cell","x":5,"y":5,"wall":1},
  {"op":"set_grid","x":0,"y":0,"grid":[[0,0],[0,0]]},
  {"op":"set_color","key":"sky_top","rgb":[60,60,130]},
  {"op":"set_entity","id":"portal_north","prop":"portal_target","value":{"x":10,"y":7}},
  {"op":"delete_entity","id":"old_portal"},
  {"op":"reload_maps"},
]}
{"cmd":"post_issue","caption":"screenshot","filepath":"snapshots/omp_1234567890.png"}
{"cmd":"snapshot","caption":"view"}
{"cmd":"dump_map"}
```

`dump_map` 输出当前地图的完整状态：网格矩阵、items、avatars、预加载地图列表。适合调试跨地图传送。

### 监听玩家消息

```bash
python metaverse/tools/listen.py --once       # 单次扫描，打印玩家新消息
python metaverse/tools/listen.py              # 持续 tail（默认每 5 秒）
```

玩家在游戏里说的话 → `agent_output.jsonl` 的 `heard` 事件（`kind=wake`）。
**推荐**直接用 `ghostworld-wait` 阻塞等唤醒——那是零轮询的，`listen.py` 留给 grep/看日志的场景。
`listen.py` 的进度按事件 `seq` 记在 `tools/listen_cursor.json`（不再用行号），
日志被轮转或被新进程重启都不会丢事件、也不会重放。

### 按键（人类客户端）

| 按键 | 功能 |
|---|---|
| `W` `S` | 前进 / 后退 |
| `A` `D` | 左 / 右平移 |
| `←` `→` | 左右转向 |
| 鼠标 | 转动视角 |
| `M` | 小地图开关 |
| `F` | 全屏切换 |
| `Enter` | 打开聊天输入框 |
| `L` | Agent 手电筒开关（小地图绿色锥形光照，默认开） |
| `Esc` | 退出 |

## 引擎 API

```python
from ghostengine import Frame, PlayerView, EntityView, ColorConfig, render
import numpy as np

frame = Frame(
    player=PlayerView(x=5, y=5, angle=0, pitch=0),
    walls=np.zeros((10, 10), dtype=int),
    entities=[],
    colors=ColorConfig(),
)
surface = pygame.display.set_mode((800, 600))
render(frame, surface)
```

主要导出：

| 符号 | 说明 |
|---|---|
| `render(frame, dst)` | 核心渲染函数，无状态，每帧调用一次 |
| `Frame` / `PlayerView` / `EntityView` | 一帧的完整世界描述 |
| `ColorConfig` / `WallDef` / `FogConfig` | 天空、地板、墙壁颜色和雾效配置 |
| `FirstPersonController` | 第一人称控制器，含碰撞检测 |
| `AnimState` / `compute_animation()` | 动画引擎（悬浮 / 脉动 / 旋转 / GIF 帧） |
| `TextureLoader` | 纹理加载器，带 LRU 缓存 |
| `load_raw()` / `save_raw()` | 地图 JSON 读写 |
| `draw_minimap()` | 小地图渲染 |

## 地图编辑器

```bash
python editor.py [项目目录]
```

### 左侧栏
- **地图列表**：列出项目 `.json` 地图，双击加载，Delete 删除
- **场景颜色**：天空顶部/底部、地板取色器

### 右侧栏（互斥显示）
- **墙壁属性**：墙壁类型（1–8）+ 颜色/贴图
- **物品属性**：可拾取、拾取标签、动画（悬浮/脉动/旋转）、贴图、遮挡模式
- **精灵属性**：名称、归属、朝向贴图（四向选择）
- **传送门属性**：ID 显示 + **目标传送门下拉框**（扫描项目全部地图的全部传送门，格式 `[地图名] ID`）；已配对灰显标注；跨图点击即双向配对；换目标自动断旧配对

### 画布图例

| 颜色 | 实体类型 |
|---|---|
| 🟣 紫色 | 传送门 |
| 🟡 金色 | 物品 |
| 🔵 蓝色 | NPC / 精灵 |
| ⚪ 青色圆点 + 白线 | 玩家出生点朝向 |

### 操作
- 左键 = 当前工具主操作；右键 = 擦除墙壁+实体；拖拽 = 连续放置/擦除
- 墙壁与实体互斥：有墙处不能放实体，有实体处不覆盖（提示"位置已被占用"）
- 加载时自动检测越界幽灵实体并清理
- Ctrl+Z/Y 撤销/重做；Delete 删除选中；Ctrl+S 保存（未命名弹出对话框）；Ctrl+Shift+S 另存为
- Ctrl+R 用预览器打开；编辑器启动时恢复上次地图
- 每 3 秒自动保存已命名地图
### 地图 JSON 格式 (v3)

```json
{
  "version": 3,
  "grid": [[0,1,0,1,0], …],
  "player_spawn": {"x": 7.5, "y": 7.5, "angle": 0.0},
  "entities": [
    {
      "x": 10.0, "y": 7.0,
      "kind": "avatar", "name": "", "owner": "",
      "facing": 0.0,
      "use_facing": false, "textures": {},
      "size_3d": 800, "width_3d": 0.8,
      "anim": {"float": {"speed": 0.003, "amp": 0.05}},
      "occlusion": "per_column", "texture": "",
      "capture_for": "", "portal_target": null,
      "metadata": {}
    },
    {
      "x": 7.5, "y": 7.5,
      "kind": "item", "pickup": true, "pickup_label": "卷轴",
      "size_3d": 140, "width_3d": 0.1,
      "occlusion": "center", "texture": "",
      "capture_for": ""
    },
    {
      "x": 14.5, "y": 7.5,
      "kind": "portal", "id": "portal_0",
      "portal_target": {"portal_id": "portal_1", "map": "other.json"},
      "size_3d": 150, "width_3d": 0.2,
      "occlusion": "center"
    }
  ],
```


## 元宇宙模块

### 文件

|文件|作用|
|---|---|
| `launch.py` | **一键启动**。同时启动服务器、人类客户端、agent |
| `local_client.py` | **人类客户端**。pygame 渲染第一人称视角，WASD 移动，Enter 聊天，Space 暂停，M 小地图 |
| `channel.py` | **事件总线**：单调 seq + 有界缓冲 + `Condition`；零 IO，跨线程唯一入口 |
| `channel_server.py` | **通道服务**：`127.0.0.1` 行 JSON socket；线程只碰 `cmd_queue` 与 `EventBus` |
| `channel_client.py` | **通道客户端**：纯 stdlib、可整文件拷走给别的项目用 |
| `cli_channel.py` | 两个 CLI 入口（`ghostworld-send` / `ghostworld-wait`）与退出码 |
| `local_agent.py` | **Agent**。同进程运行：读 `agent_commands.jsonl`（兼容层）投队列；事件走 EventBus，由 FileSink 落 `agent_output.jsonl` |
| `launch_config.json` | 启动配置：玩家名、agent 名、贴图路径 |

### 命令

| 命令 | 说明 |
|---|---|
| `say` | 发言（global channel） |
| `move` | 移动到指定坐标，服务器校验碰撞 |
| `goto` | A* 自动导航到目标 |
| `turn` | 转向面对指定坐标（一次性） |
| `track` | 持续面向目标 avatar/item |
| `pos` | 查询当前位置和所在地图 |
| `pickup` | 远程拾取：`x`,`y`（必填），可选 `item_id` |
| `place` | 从背包取出物品放到指定坐标 |
| `give` | 从背包取出物品丢脚下，设 capture_for |
| `snapshot` | 拍照存 snapshots/ 目录 |
| `post_issue` | 拍照并发 GitHub Issue（需设 `GHOSTENGINE_REPO` 环境变量） |
| `dump_map` | **调试**：矩阵格式输出完整地图状态 |
| `edit_map` | 批量编辑：`set_cell` / `set_grid` / `set_color` / `reload_maps` |
| `set_entity` | 创建/修改/删除实体：`id`,`x`,`y`,`kind`,`pickup`,`pickup_label`,`visible`,`delete` |
| `set_cell` | 修改单个墙壁：`x`,`y`,`wall` |

`set_entity` 示例：
```json
{"cmd":"set_entity","id":"gem_1","x":5.5,"y":5.5,"kind":"item","pickup":true,"pickup_label":"宝石"}
{"cmd":"set_entity","id":"gem_1","prop":"pickup_label","value":"新名字"}
{"cmd":"set_entity","id":"gem_1","delete":true}
```

`pickup` 远程拾取：
```json
{"cmd":"pickup","x":7.0,"y":5.5}
{"cmd":"pickup","x":7.0,"y":5.5,"item_id":"test_gem"}
```

## 已知限制

| 问题 | 说明 |
|---|---|
| 不要发表情 | pygame 字体不支持 emoji，显示乱码 |

## 测试

```bash
pytest tests/ -q --ignore=tests/scratch
```

137 个测试，覆盖引擎渲染、实体投影、碰撞检测、地图 I/O、WorldState、Server 协议、跨地图传送、传送门配对/取消/重配对、编辑器验证（越界清理/墙壁重叠）、Item 深拷贝隔离，以及 Agent 通道（事件总线游标/容量/并发、服务端线程边界、端到端唤醒与排队、旧文件通道兼容、listen 游标轮转/重启）。

```bash
ruff check .                    # 代码门禁（配置在 pyproject.toml）
```
