# GhostWorld — Agent 操控指南

> ⚠ **启动后请切换为英文输入法，点击游戏窗口，再进行操作。**（中文输入法会拦截按键，无法修复。）
---

## 启动

```bash
ghostworld                        # 元宇宙（默认地图 + Agent omp）
ghostworld my_map.json            # 指定地图
ghostworld-editor                 # 编辑器
python runner.pyw my_map.json     # 单机预览
```

## Agent 命令

Agent 名默认 `omp`。写 `metaverse/agent_commands.jsonl`，每 0.3s 读取。

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

## 传送门配对

`portal_target: {portal_id, map}` — 编辑器即时双向配对，换目标自动断旧。

## NPC 对话

精灵设 `dialogue` 字段。靠近 + 面向 → **"按 E 对话"** → 按 E → 3s 自动消失。编辑器精灵面板有"对话"输入框。

## 批量编辑

`edit_map`: `set_cell` / `set_grid` / `set_color` / `set_entity` / `delete_entity` / `reload_maps`
`set_entity`: 创建/修改/删除实体，跨图搜索

## 跨地图传送

`WorldState.maps` 预加载同目录 JSON。穿门 → 坐标越界保护（回退出生点）。

## 已知问题

| 状态 | 说明 |
|---|---|
| ✅ | 112 tests |
| ✅ | 跨图往返 + 深拷贝隔离 |
| ✅ | 传送门双向配对 + 坐标保护 |
| ✅ | 墙壁-实体互斥 + 越界清理 |
| ✅ | NPC 对话（E 键交互） |
| ⚠ | 中文输入法拦截按键（切英文） |
| ⚠ | 贴图 `convert_alpha()` 无头崩溃 |
