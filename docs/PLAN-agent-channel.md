# Implementation Plan: Agent ↔ 世界 通道重写（Option A）

## Design Reference
`DESIGN-agent-channel.md`（状态：已确认 2026-09-15，选定 Option A）

## Component Map

**NEW**
- `metaverse/channel.py` — `EventBus`：单调 seq + 有界缓冲 + `threading.Condition` + `kind` 过滤（纯逻辑，零 IO）
- `metaverse/channel_server.py` — `127.0.0.1` socket 服务、行协议、`cmd_queue`、`.channel.json` 生命周期
- `metaverse/cli_channel.py` — `ghostworld-send` / `ghostworld-wait` 两个入口的实现在此
- `tests/test_channel_bus.py`、`tests/test_channel_server.py`、`tests/test_channel_e2e.py`

**MODIFIED**
- `metaverse/server.py` — `say` 处发 `heard`；新增 `drain_agent_queue()`
- `metaverse/server.py:686` `_tick_loop_sync()` — 每 tick drain
- `metaverse/local_agent.py` — 事件发布改走 EventBus；`log_msg` 降级为订阅者
- `metaverse/launch.py`、`headless_agent.py` — 起信道服务 + 写/清 `.channel.json` + headless 的 drain 循环
- `metaverse/tools/listen.py`、`tools/look.py` — 用 seq 游标，退役 `listen_state.txt`
- `pyproject.toml` — 两个 `[project.scripts]`
- `README.md` — 禁令措辞、命令表、唤醒语义、修 `listen.py` 路径
- `.gitignore` — 加 `metaverse/.channel.json`

**DELETED**：无

---

## Interface Contracts（先说清楚，否则任务之间对不上）

### 1. 事件对象（既有词汇 + 两个新字段）
```json
{"seq": 12, "ts": 1757900000.123, "kind": "wake",
 "event": "heard", "from": "player", "message": "你好", "channel": "global", "tick": 4231}
```
`event` 取值**沿用 `_shared.py` 里既有的那套**（`heard` / `connected` / `see` / `goto_done` / `said` / `moving`
/ `position` / `inventory` / `navigating` / `picked_up` / `pickup_failed` / `entity_set` / `entity_deleted`
/ `cell_set` / `placed` / `gave` / `perception` / `dump_map` / `map_edit_sent` / `post_issue` / `tracking`
/ `untracked` / `cmd_error`），只新增 `seq` / `ts` / `kind`。
`kind = "wake"` 只有 `heard`（玩家发言）；其余一律 `"observation"`。

### 2. `EventBus` API（唯一允许被跨线程调用的对象）
```python
class EventBus:
    def __init__(self, capacity: int = 1000) -> None: ...
    def publish(self, evt: dict) -> int: ...      # 追加并唤醒等待者，返回 seq
    def wait(self, after: int | None, timeout: float,
             kinds: set[str] | None = None) -> tuple[list[dict], int, bool]: ...
    #                                               (events, cursor, gap)
    def cursor(self) -> int: ...
    def wake(self) -> None: ...                   # 无事件地放行等待者（超时/关闭用）
```
`after` 早于缓冲起点 → `gap=True` 且 `oldest` 可查（**明确报缺口，而不是静默丢**）。

### 3. wire 协议（行分隔 JSON over TCP `127.0.0.1`）
```
→ {"hello":{"token":"...","role":"wait","after":12,"kinds":["wake"],"timeout":25}}
← {"ok":true,"cursor":12,"protocol":1}

role="wait"：随后每行一个裸事件对象；超时 ← {"timeout":true,"cursor":12}
            游标过旧 ← {"gap":true,"oldest":37,"cursor":12}
role="send"：→ {"cmd":{"cmd":"say","message":"hi"}}
            ← {"ack":{...},"cursor":13}
```
一次连接只做一次动作（CLI 每次调用新建连接），服务端不必维护会话状态。

### 4. `metaverse/.channel.json`
```json
{"protocol": 1, "port": 51234, "token": "<hex32>", "pid": 24264, "started": 1757900000.0}
```
由 `launch.py` / `headless_agent.py` 启动时写、正常退出时删；`.gitignore` 忽略。

### 5. CLI 退出码
`ghostworld-send`：`0` 收到 ack ｜ `1` 连接被接受但无 ack ｜ `2` 连不上（游戏没在跑）
`ghostworld-wait`：`0` 有事件（已打印）｜ `2` 连不上 ｜ `3` 超时

---

## Tasks

### Phase 1 — 纯逻辑（T1、T2 相互独立，可并行）

**Task 1：`EventBus`**
**What:** 实现有界事件缓冲：单调 seq、`publish` 唤醒、`wait(after,timeout,kinds)`、gap 信号。
**Files:** `metaverse/channel.py`（新建）
**Acceptance:**
- [ ] `publish` 返回的 seq 严格单调递增
- [ ] 容量满时从头部淘汰，`wait` 传入被淘汰的游标时返回 `gap=True`
- [ ] `wait` 在 `publish` 后立即返回（不轮询）
- [ ] `kinds={"wake"}` 时只返回 `heard`，observation 事件留在缓冲里
**Depends on:** none

**Task 2：`EventBus` 单元测试**
**What:** 覆盖游标/容量/并发/唤醒/过滤。
**Files:** `tests/test_channel_bus.py`（新建）
**Acceptance:**
- [ ] 8 个用例：seq 单调、淘汰+gap、append-only 顺序、并发 publish（4 线程 × 250 次 = 1000 个唯一 seq）、
      `wait` 被 `publish` 唤醒（断言 <50ms）、`wake()` 空放行、kinds 过滤、容量边界（0 与 1）
- [ ] `python -m pytest tests/test_channel_bus.py -q` 全绿
**Depends on:** Task 1

### Phase 2 — 服务端（CHECKPOINT 1）

**Task 3：socket 服务 + 行协议**
**What:** `127.0.0.1` 随机端口监听、hello/token 校验、每连接一线程、命令投进 `cmd_queue`、事件推回连接。
**Files:** `metaverse/channel_server.py`（新建）
**Acceptance:**
- [ ] 错误 token → 收到 `{"error":"bad token"}` 并断开
- [ ] 服务端**不出现任何对 `ws` 的引用**（只有 `cmd_queue` 与 `EventBus`）
- [ ] 模块暴露 `start(bus, cmd_queue) -> ChannelServer`（`port` 属性）与 `stop()`
**Depends on:** Task 1

**Task 4：服务端边界与协议测试**
**What:** 用假 WorldState 证明线程边界没被破。
**Files:** `tests/test_channel_server.py`（新建）
**Acceptance:**
- [ ] **边界用例**：传一个"任何属性访问都抛异常"的假对象给 `channel_server`，跑完 hello/send/wait 全流程后断言异常从未触发
- [ ] `send` 的 cmd 出现在 `cmd_queue` 里；`wait` 在 `bus.publish` 后 <50ms 收到事件行
- [ ] token 错误、超时、gap 三种应答各一例
- [ ] `python -m pytest tests/test_channel_server.py -q` 全绿
**Depends on:** Task 3

### Phase 3 — 接入世界（T5→T6→T7 顺序；T8 依赖 T5）

**Task 5：命令 drain 与 ack 回填**
**What:** 帧循环内消费 `cmd_queue`，调 `process_agent_command`，把 resp 交回连接线程。
**Files:** `metaverse/server.py` — 新增 `drain_agent_queue(bus, ws, agent_name)`；`server.py:686` `_tick_loop_sync()` 内调用
**Acceptance:**
- [ ] 每 tick 最多消费 N 条（默认 32），不阻塞帧循环
- [ ] `send {"cmd":"pos"}` 拿到含 `x`/`y` 的 ack
- [ ] 命令抛异常时 ack 为 `{"event":"cmd_error","error":"..."}`，帧循环不崩
**Depends on:** Task 3

**Task 6：`heard` 事件（唯一的唤醒源）**
**What:** 记录聊天后发一条 `kind="wake"` 事件。
**Files:** `metaverse/server.py:61-63`（`ws.chat_log.append` 之后）
**Acceptance:**
- [ ] 玩家发言 → 一条 `{"kind":"wake","event":"heard","from":"player",...}`
- [ ] Agent 自己发言**不**产生 wake（沿用现在 `local_agent` 的 `from != name` 判断）
**Depends on:** Task 1

**Task 7：`local_agent.py` 改接 EventBus**
**What:** `connected` / `see` / `goto_done` / 命令回声一律 `kind="observation"`；`log_msg` 降级为订阅者。
**Files:** `metaverse/local_agent.py`
**Acceptance:**
- [ ] `agent_output.jsonl` 内容格式与现在**逐字段一致**（除新增的 `seq`/`ts`/`kind`）
- [ ] 移除 `_log_write_count % 50` 的头部截断（改由 EventBus 的容量与 seq 边界管）
- [ ] 文件写入失败不影响世界推进（沿用现有 try/except）
**Depends on:** Task 1

**Task 8：启动接线**
**What:** 起信道服务、写 `.channel.json`、退出清理；headless 也有 drain 循环。
**Files:** `metaverse/launch.py`、`headless_agent.py`
**Acceptance:**
- [ ] `python -m metaverse.launch` 后 `.channel.json` 存在且端口可连
- [ ] `python headless_agent.py`（无 pygame）也能被 `ghostworld-send pos` 拿到 ack
- [ ] Ctrl+C / 正常退出后 `.channel.json` 被删除
**Depends on:** Task 5

### Phase 4 — 客户端（T9→T10；T11 依赖两者）

**Task 9：两个 CLI + 入口**
**What:** `ghostworld-send` / `ghostworld-wait`。
**Files:** `metaverse/cli_channel.py`（新建）、`pyproject.toml`
**Acceptance:**
- [ ] `ghostworld-send '{"cmd":"pos"}'` 打印 ack JSON，退出码 0
- [ ] `ghostworld-wait --timeout 25` 阻塞直到 `heard` 出现，打印一行事件 JSON，退出码 0
- [ ] 游戏没跑时两者都打印明确错误（"channel not found — 游戏没在跑？"）且退出码 2
- [ ] `pip install -e .` 后两个命令名可用
**Depends on:** Task 3

**Task 10：文件兼容层**
**What:** 旧文件通道变成 EventBus 的生产者/订阅者，行为不变。
**Files:** `metaverse/local_agent.py`（`read_commands`）、`metaverse/channel.py`（一个 `FileSink` 订阅者）
**Acceptance:**
- [ ] 手写 `metaverse/agent_commands.jsonl` 仍被执行（老流程不炸）
- [ ] `agent_output.jsonl` 仍被追加写入（Mnemenet 那条线不受影响）
- [ ] `read_commands` 的读后即删行为保留（但有游标兜底，命令不会再静默消失）
**Depends on:** Task 7

**Task 11：端到端测试（CHECKPOINT 2）**
**What:** 真 socket 打通全链路。
**Files:** `tests/test_channel_e2e.py`（新建）
**Acceptance:**
- [ ] headless 起服务 → `send pos` 收 ack → 模拟玩家 say → `wait` **在 50ms 内**返回该消息
- [ ] 玩家在 Agent "思考" 期间连发 3 条 → 下一次 `wait` 一次性拿到 3 条（排队语义）
- [ ] Agent 被唤醒后未 `wait` 时，服务端不产生任何空转（断言无 busy loop：CPU/调用计数）
**Depends on:** Task 9、Task 10

### Phase 5 — 收尾

**Task 12：文档**
**What:** 禁令措辞、命令表、唤醒语义、修 `listen.py` 路径。
**Files:** `README.md:83-85`（禁令）、`## Agent 控制` 段、`### 监听玩家消息` 段
**Acceptance:**
- [ ] 禁令改为：`禁止 WebSocket 协议与 asyncio 网络 I/O；允许 127.0.0.1 上的同步 socket + 线程向队列投递`
- [ ] `python metaverse/listen.py` → `python metaverse/tools/listen.py`
- [ ] 新增一句唤醒语义："Agent 常驻 `ghostworld-wait`，玩家发言即被唤醒；不发言时零开销"
**Depends on:** Task 11

**Task 13：`listen.py` / `look.py` 改游标**
**What:** 退役行号游标。
**Files:** `metaverse/tools/listen.py`、`metaverse/tools/look.py`
**Acceptance:**
- [ ] 不再读写 `listen_state.txt`；改用 `seq`
- [ ] 日志被轮转/重启后不会丢事件或重放（两例断言）
**Depends on:** Task 10

**Task 14：全量回归 + 真机手测**
**What:** 收尾验证。
**Files:** 无（验证任务）
**Acceptance:**
- [ ] `python -m pytest tests/ -q --ignore=tests/scratch` 全绿（既有 112 + 新增）
- [ ] 真机：起游戏 → 玩家打字 → omp 被唤醒 → 回一句 → 再进入阻塞
- [ ] 真机：玩家不说话 5 分钟，Agent 侧无任何输出/无 CPU 占用
**Depends on:** Task 12、Task 13

---

## Execution Strategy
- **Parallel:** Phase 1 的 T1/T2 与其他阶段无关；T6 可与 T5 并行（都只依赖 T1）。
- **Sequential:** T3→T5→T8；T7→T10→T11→T13。
- **Checkpoints（停下给你看）**：CHECKPOINT 1 = T4 后（核心可测，未接线）；
  CHECKPOINT 2 = T11 后（端到端通，未动文档）；T12 之前再确认一次文档改动。

## Global Constraints

### Style
- 跟着既有模式走：`snake_case`、模块级 `_private`、`from __future__ import annotations`、`sys.dont_write_bytecode = True` 入口不破
- **不引任何第三方依赖**（只用 `socket` / `threading` / `queue` / `collections` / `json`）
- 事件名沿用 `_shared.py` 既有词汇，不发明新名字

### Boundaries（红线）
- **ALWAYS**：通道线程只经 `cmd_queue` 与 `EventBus`；`WorldState` 只有帧循环能改
- **ALWAYS**：每个任务后跑相关测试；不删既有测试
- **NEVER**：WebSocket 协议；用 asyncio 做网络 I/O；在通道线程里调 `handle_message`
- **ASK FIRST**：改 `_shared.py` 里的命令语义、改 `.channel.json` 的字段、动 Mnemenet 集成那部分

### Interface Contracts
见上文 §1–§5（事件对象 / EventBus API / wire 协议 / `.channel.json` / 退出码）。
跨任务共享的只有 `EventBus` 与 wire 协议两件东西，其余模块各自独立。
