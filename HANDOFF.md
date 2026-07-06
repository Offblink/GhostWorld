# GhostEngine Metaverse — Agent 操控指南

> **你是 AI Agent，这是你的操作手册。下一个实例读完就能上手。**


> # ⛔ 严重警告 — 所有 Agent 必读
>
> **本项目严禁使用 WebSocket 和 MCP。**
>
> 原因：Windows 上 WebSocket 存在一个严重 bug，至今未被发现和修复。
> 2026-06-24，某 agent 添加 WebSocket + MCP 后导致整个项目崩溃，所有改动丢失，
> 不得不从 GitHub 回退。MCP 同样会触发不可预知的系统级问题。
>
> **任何 agent 的改动均不可涉及：**
> - `websockets` 库
> - `ws://` / `wss://` 协议
> - MCP (Model Context Protocol) 服务端/客户端
> - 任何形式的异步网络服务器
>
> 本项目是同进程架构：`server.py` + `local_client.py` + `local_agent.py` 共享 `WorldState`，
> 通过直接函数调用通信，不经过任何网络层。保持这个设计。
>
> **违反此规则的改动将被回退。**
---

## 启动

```bash
cd C:\tmp\ghostengine
python -m metaverse.launch my_map.json              # 指定地图
python -m metaverse.launch                           # 默认读取 .last_map → demo_metaverse
python launcher.py                                   # GUI 启动器
python runner.pyw my_map.json                        # 单机预览
```

### 无头调试

```bash
python headless_agent.py examples/new_test_map.json
```

仅服务器+Agent，无 GUI。适合快速测试命令，不干扰玩家。

自动杀旧端口，无需手动关。无 `.pyc` 污染，放心改代码。

小地图和 Agent 手电筒默认开启，`M`/`L` 可切换。

---

## Agent 命令

Agent 名默认 `omp`（在 `launch_config.json` 配置）。写 `metaverse/agent_commands.jsonl`（每行一个 JSON），agent 每 0.3s 读取并删除。

### 基础命令

```json
{"cmd":"say","message":"hello"}
{"cmd":"move","x":4.0,"y":1.5}
{"cmd":"goto","x":5.5,"y":5.5}
{"cmd":"turn","x":10,"y":5}
{"cmd":"track","target":"player"}
{"cmd":"pos"}
{"cmd":"inv"}
{"cmd":"look"}
{"cmd":"pickup","x":7.0,"y":5.5}
{"cmd":"place","item_id":"gem_B","x":3.5,"y":3.5}
{"cmd":"give","target":"player","item_id":"agent_token"}
{"cmd":"snapshot","caption":"view"}
{"cmd":"post_issue","caption":"view","filepath":"snapshots/omp_1234567890.png"}
```

`pickup` 必须带 `x`,`y` 坐标（远程拾取）。`post_issue` 需要设环境变量 `GHOSTENGINE_REPO=Offblink/MnemeNet`。
旧命令 `delete_entity` 仍然可用（自动转换）。

### 传送门配对 (v3)

传送门成对工作，通过 `portal_target` 引用对方：

```json
// 地图 A 的传送门
{"kind": "portal", "id": "portal_0", "portal_target": {"portal_id": "portal_1", "map": "map_B.json"}}
// 地图 B 的传送门（保存时自动双向绑定）
{"kind": "portal", "id": "portal_1", "portal_target": {"portal_id": "portal_0", "map": "map_A.json"}}
```

- 编辑器保存时自动双向配对
- 传送门 ID 自动生成（`portal_0`, `portal_1`...）
- 走进传送门 → 服务器解析 `portal_id` → 查找目标传送门坐标 → 跳转
- 支持跨地图传送

### 批量编辑
---

## 读玩家消息和位置

### 方法 1：工具脚本（慢但省心）

```bash
python metaverse/tools/listen.py --once    # 等 5s，打印新消息
python metaverse/tools/look.py             # 打印 inventory + 全地图道具
```

### 方法 2：直接查日志（最快）

**日志会累积，`tail` 只看到 `see` 事件。必须用 `grep` 搜 `heard`。**

```bash
# 查最近消息
grep '"heard"' metaverse/agent_output.jsonl | tail -5

# 查玩家位置
grep '"avatars"' metaverse/agent_output.jsonl | tail -1

# 或一次性
python -c "
import json, sys
with open('metaverse/agent_output.jsonl','r',encoding='utf-8') as f:
    lines = f.readlines()
for l in lines[-100:]:  # 至少 100 行，see 事件太多
    d = json.loads(l)
    if d.get('event') == 'heard': print(f'[player] {d[\"message\"]}')
    elif d.get('event') == 'see':
        p = d.get('avatars',{}).get('player')
        if p: print(f'pos: ({p[0]:.1f},{p[1]:.1f})')
"

### 方法 3：perception 全量（知道自己在哪、有什么）

```bash
python metaverse/tools/look.py   # 或直接读 perception 事件
```

---

## 操作循环

```
1. 读 agent_output.jsonl 尾部 → 看到玩家消息 + 位置
2. 理解意图，写 agent_commands.jsonl
3. 等 2-3 秒让 agent 执行
4. 再读 → 看结果（look.py 或直接读 perception）
5. 重复
```

**不要每轮都重新开 bash 等 5 秒。** 用方法 2 的 3 秒直接读。

---

## 跨地图传送

玩家和 agent 可以各自在不同地图上，互不可见。

- 传送门配对格式：`portal_target: {"portal_id":"portal_0","map":"other.json"}`
- 服务器 `_resolve_portal_target` 解析 portal_id → 目标传送门坐标
- `WorldState.maps` 预加载同目录所有 JSON 地图
- 穿门 → `Avatar.current_map` 设为目标地图名
- `local_client` 检测 `current_map` 变化 → 切换 grid/items/colors
- `_build_snapshot` 按 `current_map` 过滤——只渲染同图 avatar
- **返回门**：目标传送门的 `portal_target` 指向原地图 → `ws.map_path` 更新 → 画面切回

---

## 物品交换

- `give` 命令：从背包取出物品放地上，设 `capture_for` 限制拾取人
- 玩家用 `/give omp item_name` 聊天命令丢给 agent
- `capture_for` 在 `check_pickups` 中校验
- HUD 左上角显示 inventory（按 label 合并计数）

---
## 已知问题 & 注意事项

| # | 状态 | 说明 |
|---|---|---|
| | ✅ | `sys.dont_write_bytecode = True`，不产生 `.pyc` |
| | ✅ | 跨图往返：`ws.maps` 预加载同目录所有 JSON |
| | ✅ | 传送门配对：v3 格式，`portal_target = {portal_id, map}`，编辑器即时双向配对、换目标断旧配对、删除断配对 |
| | ✅ | 编辑器 ↔ 预览器坐标一致（`.T` 转置全入口统一） |
| | ✅ | 跨图 Item 深拷贝隔离——地图数据互不污染 |
| | ✅ | 墙壁-实体互斥 + 越界幽灵自动清理 + 传送坐标越界保护 |
| | ⚠️ | `import os` 陷阱 — 函数内 import 会遮蔽全局 |
| | ⚠️ | 贴图 `convert_alpha()` 在无头渲染时崩溃 |
| | ⚠️ | state 文件持久化：grid 尺寸校验防污染，但 colors 不持久化 |

---

## 测试

112 tests。`pytest tests/ -q --ignore=tests/scratch`
