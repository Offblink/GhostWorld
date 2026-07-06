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

> 完整架构图见 [ARCHITECTURE.txt](ARCHITECTURE.txt)

## 安装

```bash
pip install git+https://github.com/Offblink/GhostWorld.git
```

需要 Python ≥ 3.10。依赖：`pygame`, `numpy`。编辑器额外需要 `PySide6`。

## 更新

```bash
pip cache purge && pip install --upgrade git+https://github.com/Offblink/GhostWorld.git
```

> ⛔ **开发禁令**：本项目**严禁使用 WebSocket、MCP、或任何异步网络通信**。
> Windows 上 WebSocket 存在未修复的严重 bug，曾导致项目崩溃、数据丢失。
> 所有模块通过同进程函数调用通信，不经过网络层。

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


### Agent 控制

向 `metaverse/agent_commands.jsonl` 写入 JSON 行指令，agent 每 0.3s 读取并执行：

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
python metaverse/listen.py --once       # 等5秒，打印玩家新消息
python metaverse/listen.py              # 持续监听
```

玩家在游戏里说的话 → `agent_output.jsonl` 的 `heard` 事件。AI Agent 应每 5 秒检查一次。

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
| `local_agent.py` | **Agent**。同进程运行，每 0.3s 检查 `agent_commands.jsonl` 并执行指令 |
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

112 个测试，覆盖引擎渲染、实体投影、碰撞检测、地图 I/O、WorldState、Server 协议、跨地图传送、传送门配对/取消/重配对、编辑器验证（越界清理/墙壁重叠）、Item 深拷贝隔离。
