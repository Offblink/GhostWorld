# GhostWorld — Agent 操控指南

> **你是 AI Agent，这是你的操作手册。下一个实例读完就能上手。**

> # ⛔ 严重警告 — 所有 Agent 必读
>
> **本项目严禁使用 WebSocket 和 MCP。**
> 本项目是同进程架构，通过直接函数调用通信。保持这个设计。
> **违反此规则的改动将被回退。**
---

## 启动

```bash
ghostworld                        # 启动元宇宙（默认地图 + Agent omp）
ghostworld my_map.json            # 指定地图
ghostworld-editor                 # 启动编辑器
python runner.pyw my_map.json     # 单机预览
python headless_agent.py map.json # 无头调试
```

---

## Agent 命令

Agent 名默认 `omp`。写 `metaverse/agent_commands.jsonl`（每行一个 JSON），agent 每 0.3s 读取。

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

### 传送门配对 (v3)

传送门通过 `portal_target: {portal_id, map}` 配对。编辑器即时双向配对，换目标自动断旧配对。

### NPC 对话

精灵（avatar）可设置 `dialogue` 字段。玩家靠近 + 面向精灵时：
- 显示 **"按 E 对话"** 提示
- 按 E 弹出对话，**3 秒后自动消失**
- 编辑器：精灵属性面板 → "对话" 输入框
- runner / metaverse 均支持

### 批量编辑

`edit_map`：`set_cell` / `set_grid` / `set_color` / `set_entity` / `delete_entity` / `reload_maps`

---

## 跨地图传送

- 传送门配对格式：`portal_target: {"portal_id":"portal_0","map":"other.json"}`
- `WorldState.maps` 预加载同目录所有 JSON 地图
- 穿门 → 坐标越界保护（回退出生点）

## 物品交换

- `give` 命令：从背包取出物品放地上，设 `capture_for`
- 玩家用 `/give omp item_name` 聊天命令丢给 agent

## 已知问题

| 状态 | 说明 |
|---|---|
| ✅ | 112 tests 全部通过 |
| ✅ | 跨图往返 + 深拷贝隔离 |
| ✅ | 传送门双向配对 + 坐标保护 |
| ✅ | 墙壁-实体互斥 + 越界清理 |
| ✅ | NPC 对话系统（E 键交互） |
| ⚠️ | 贴图 `convert_alpha()` 在无头渲染时崩溃 |
