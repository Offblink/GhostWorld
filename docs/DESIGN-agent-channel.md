# Design: Agent ↔ 世界 通道重写（事件唤醒 + 传送层替换）

> 状态：**已确认（2026-09-15）** —— 选定 **Option A**。实施计划见 `PLAN-agent-channel.md`。本文保留决策依据。

---

## 已确认的决策（2026-09-15）

| # | 决策 | 结论 |
|---|---|---|
| 1 | 传送层 | **Option A**：本地 TCP 真推送 + 游标事件缓存；HTTP 门面（Option B）留作以后的加法 |
| 2 | 唤醒源 | **只有玩家发言（chat）唤醒**。其余事件（靠近/看向、NPC 对话、世界被编辑）**仍作为可订阅事件存在**，只是 `kind=observation` 不唤醒 —— 将来要放开某一条，只改 EventBus 的一句 kind 策略，不动连接层 |
| 3 | 旧文件通道 | **保留为兼容层**：`agent_commands.jsonl` / `agent_output.jsonl` 的读写降级为 EventBus 的一个生产者/订阅者，Mnemenet 那条线与老工作流不受影响 |
| 4 | 开发禁令 | **改措辞**为：`禁止 WebSocket 协议与 asyncio 网络 I/O；允许 127.0.0.1 上的同步 socket + 线程向队列投递`（病因三条都不碰） |

**我替你定的次要项**（按最保守取值，不认可可以直接推翻）：
- 通信范围 = **只本机 `127.0.0.1`**，不做跨机；`.channel.json` 里的 token 用于防误连/串台，**不是安全边界**（同机进程读得到）。
- 端口 = **随机端口 + `metaverse/.channel.json`**（port/token/pid），避免占用冲突。
- 迁移 = **一次性切到新通道**，同时保留旧文件读写（决策 3）作为兼容层，不做长期双写。

---

## Problem

Agent 操控角色的通道现在靠两个 JSONL 文件 + 轮询：Agent 必须"主动去查"才可能看到玩家说了什么，
且这条通道有三个会造成**静默丢数据**的结构性缺陷。目标是把通道换成"事件唤醒 + 有游标的可靠投递"：
**玩家开口才唤醒 Agent，其余时间 Agent 完全 parked（不轮询、不烧 token、不烧 CPU）。**

---

## Context（读代码得到的事实，不是推测）

### 拓扑
单进程、单 asyncio 事件循环，三个 task：
- `metaverse/launch.py:98` `agent_task = asyncio.create_task(local_agent_loop(...))`
- 人类客户端 `local_client.py` 在同一循环里跑 pygame 帧循环
- **没有服务器线程**：`metaverse/server.py:693` 明写 "No network server — everything runs same-process"，
  客户端在帧循环里 inline 调 `_tick_loop_sync()`（`local_client.py:196-197`）与 `handle_message()`。
- 外部 AI Agent（omp / Claude Code 之类）是**另一个进程**，只能通过工具面（读/写文件、跑命令）与游戏交互。

### 现有通道
| 方向 | 载体 | 谁读 |
|---|---|---|
| 外部 Agent → 游戏 | `metaverse/agent_commands.jsonl` | `local_agent.py:89` 每 0.3s `read_commands()` |
| 游戏 → 外部 Agent | `metaverse/agent_output.jsonl`（append） | `metaverse/tools/listen.py`（5s 轮询）/ `tools/look.py` |

### 现有轮询点（"长期轮询"具体指什么）
- `metaverse/local_agent.py:67` `await asyncio.sleep(0.3)` —— 常驻任务永远醒着，每 0.3s 扫一次
  `ws.chat_log`、每 0.3s 构建一次全量 `_build_snapshot()`。
- `metaverse/tools/listen.py:30-59` —— `--once` 单次轮询；默认 `--interval 5` 持续轮询。
- `README.md` 原文要求："玩家在游戏里说的话 → `agent_output.jsonl` 的 `heard` 事件。
  **AI Agent 应每 5 秒检查一次**。"

### 三个会静默丢数据的缺陷（有据可查）
1. **命令读后即删，存在写/读竞态**：`local_agent.py:33-48` `read_commands()` 读完整个文件后 `os.remove(CMD_FILE)`。
   写入方是外部进程（非原子 append），读到半行 → 该命令解析失败被丢弃，而文件已经被删掉。丢失后无痕迹。
2. **日志从头截断 + 行号游标 → 索引失效**：`local_agent.py:11-29` 每 50 次写入把
   `agent_output.jsonl` 截到"最近 100 行"（`_MAX_LOG_LINES=200`）；而读者侧 `tools/listen.py:23-39`
   把进度存在 `listen_state.txt` 的**绝对行号**里。文件被截断、或进程重启时 `open(LOG_FILE,"w")` 清空日志
   （`local_agent.py:62`），行号立刻失真 → 丢事件或重放事件，两边都不报错。
3. **命令没有 ack**：`agent_commands.jsonl` 是单向的，写进去不知道成功与否；想知道结果必须再去读日志
   → 一次交互 = 2~3 次工具调用（写文件 + 读日志 + 可能再 `look`）。

另外 `ws.chat_log` 自身是 50 条的环形缓冲（`server.py:61-63`），Agent 离开超过 50 句就被覆盖——**没有持久游标**。

### 硬约束（决定了方案不能怎么写）
- **单线程协作世界**：`WorldState` 只被帧循环和 agent 的 asyncio task 就地修改，**没有锁**，
  靠同一事件循环 + `await asyncio.sleep(0)` 让出实现"不冲突"。
  → 任何新通道的线程**绝对不允许直接读写 WorldState**，必须把命令投进队列、由帧循环 drain 后调用。
  这是本设计的第一约束，也是（我判断）当年 WS 崩溃/丢数据的同类根因：第二个线程/第二个事件循环直接动了世界。
- **外部 Agent 只有工具面**：它不能持有长连接除非能起后台进程并等它的输出。
- **项目明确禁令**：`README.md:83-85` "严禁使用 WebSocket、MCP、或任何异步网络通信"。
- Windows、无 CI、112 个测试、单实例锁 `metaverse/.instance.lock`、`.gitignore` 已忽略两个 jsonl。
- 文档已漂移：README 写 `python metaverse/listen.py`，实际文件在 `metaverse/tools/listen.py`（本次顺手记下）。

### 参照实现：Fungi 的"后台"是怎么做的（本机已验证可行）
- `fungi/hub/relay.py`：每个目的地一个 `Inbox` = **单调 seq 游标 + `threading.Condition`**；
  `push()` 追加并去重（`_seen`），`after(cursor, timeout)` 阻塞等待新消息、`wake()` 主动唤醒。
- `fungi/hub/app.py:165-166`：`ThreadingHTTPServer` + `/api/join|send|poll|heartbeat`，`heartbeat_timeout=30`。
- `fungi/pending.py:58`：`threading.Event().wait(min(heartbeat_s, remaining))` —— **阻塞等待 + 心跳切片**，
  不是空转轮询。
- `fungi/clone/base.py:231-235`：每个 clone 一个 `queue.Queue` + 循环线程 + worker 线程 = 事件驱动唤醒。

**这三样合起来就是"后台"的定义**：常驻进程 + 游标缓冲 + Condition/Event 阻塞唤醒；跨进程用 HTTP 长轮询
（`poll(cursor, timeout)` 在服务端 Condition 上等，有消息立刻返回）。**全程没有 WebSocket。**

---

## Options

### Option A：常驻 watcher + 本地 TCP 行协议 + 游标事件缓存  ⭐推荐
**核心想法**：游戏进程内起一个 `127.0.0.1` 的同步 socket 服务（自定行分隔 JSON 协议），
外部 Agent 侧用一个常驻的 `ghostworld-wait` 进程**阻塞**在上面；玩家一说话，服务端立刻推一行，
watcher 打印 → harness 唤醒 Agent。命令用另一个 CLI `ghostworld-send` 一次往返拿到 ack。

**流程**
```
玩家 Enter ─→ handle_message(say) ─→ EventBus.publish({heard}) ─→ wake() ──┐
                                                                          ↓
                                        ghostworld-wait 阻塞在 socket recv ─┘
                                                                          ↓
                                            打印一行 JSON → harness 唤醒 Agent
Agent ─→ ghostworld-send '{"cmd":"say",...}' ─→ cmd_queue ─→ 帧循环 drain ─→ handle_message
                                             ←── ack（同一次工具调用内拿到）
Agent 处理完 ─→ 再次 ghostworld-wait（回到阻塞，零成本）
```
- **Pros**：真推送（无任何轮询语义）；游标 + 容量缓冲 → 三个丢数据缺陷一起消失；命令带 ack（一次工具调用完事）；
  传输线程只往 `queue.Queue` 投递，世界仍然只被帧循环改（守住第一约束）；纯 socket 无协议升级、无 WS、无 asyncio；
  换任何 harness/语言都能接（协议只是行分隔 JSON）。
- **Cons**：需要一个端口（loopback，一般不用放行防火墙，但极端环境会拦）；多一个常驻进程要管生命周期；
  要写两遍 CLI 入口；`wait` 依赖 harness 允许"起后台进程并等输出"。
- **Risk**：harness 若对单条命令有硬超时（Claude Code 的 Bash 有上限），阻塞式 `wait` 会被砍 →
  退路是 Option B 的长轮询（每次唤醒一次短请求），或 `wait --timeout 25` 循环。

### Option B：HTTP 长轮询门面（Fungi 同构）
**核心想法**：同样的 EventBus，外面套一个 `ThreadingHTTPServer`：
`GET /events?after=<seq>&timeout=25`（服务端在 Condition 上阻塞，有事件立刻返回，超时返回空）、
`POST /command`（返回 ack）、`GET /state`（快照）。响应体用 NDJSON（要浏览器面板就换 `text/event-stream`）。

- **Pros**：**与 Fungi 完全同构**（同一套游标+Condition 心智，调试经验可迁移）；客户端零安装——`curl` 就能当客户端，
  甚至不需要给 CLI 起新入口；未来做浏览器观察面板/给别的 agent 接入几乎免费；本机已有 Fungi 证明这条路在 Windows 上稳。
- **Cons**：要写 HTTP 解析（stdlib 够）；每连接一线程；长轮询超时/重连参数要调；
  "长轮询"这个词与你要摆脱的"轮询"同名，需要靠语义区分清楚（服务端阻塞+事件缓存 vs 5s 空转）。
- **Risk**：`ThreadingHTTPServer` 的线程若图省事直接改 WorldState，就会重演旧的崩溃模式 —— 队列边界必须写死并有测试。

### Option C：文件通道最小改造（fs 事件 + 每命令一文件 + 游标）
**核心想法**：不引入端口。日志改成只追加 + 每条事件带 `seq`（不再从头截断），读者存 `seq` 而不是行号；
命令改成"每条命令一个文件写入 `commands/` 再原子 rename"（消掉 read-then-remove 竞态）；
用 Windows `ReadDirectoryChangesW`（`watchdog`）替代 5s 轮询来唤醒。

- **Pros**：改动最小、无端口、无新进程；保持"文件即接口"（Agent 用现成的 Read/Write 工具就能玩，不需要装 CLI）。
- **Cons**：**新依赖** `watchdog`；Windows 文件事件有合并/丢失的历史坑，做不到"必达"；
  命令仍无 ack（要读结果就得多一次工具调用）；目录被清/多实例仍会丢；
  本质上是"用文件系统事件模拟消息队列"，比 A/B 更脆。
- **Risk**：fs 事件不可靠时退化成"回退轮询"，等于白改。

### 已考虑并否决
- **D1 进程内 Agent 回合**（游戏进程自己调 LLM，像 Fungi 的 room）：最彻底、零 IPC，但会把 LLM 凭据/提示词/工具面
  搬进游戏，**丢掉 omp 的全部工具**（bash/文件/子代理/技能），Mnemenet 集成也要重写。除非你要的是一个独立小助手，
  否则不值得。
- **D2 WebRTC DataChannel / WebTransport**：同机进程间通信使用它们＝杀鸡用牛刀，且直接违反项目禁令的复杂度前提。
- **D3 MCP**：项目明令禁止；且 MCP 的 stdio 传输在 Windows 上另有坑（见本机 mcp-stdio-windows 经验）。

---

## Recommended: Option A

**为什么**：它把两件事同时解决——(1) 传送层换成"有游标、有 ack、事件驱动"的可靠通道；
(2) 唤醒模型从"每 5s 去查"变成"玩家开口才被叫醒"。
而 Option B 可以**叠在 A 上面**成为加法（同一个 EventBus 再挂一个 HTTP 门面），所以先做 A 不会堵死后路；
反过来先做 B、以后要真推送就得重写连接层。

### 实现大纲（10 步，不是代码）
1. `metaverse/channel.py`：`EventBus` = `deque`（容量可配）+ 单调 `seq` + `threading.Condition`；
   接口 `publish(evt)->seq` / `wait(after, timeout, kinds)->([evt], cursor)` / `wake()` / `snapshot()`。
   事件带 `kind`：`wake`（玩家消息，会唤醒）/ `observation`（see、goto_done，默认不唤醒）。
2. `metaverse/channel_server.py`：`socket` 监听 `127.0.0.1:0`；accept 线程 + 每连接一线程；
   线程**只做**两件事——把命令放进 `cmd_queue`、把 EventBus 的事件写回连接。**永不触碰 `WorldState`**。
3. `server.py`：新增 `drain_agent_queue(ctx, ws)`，在帧循环里（与 `_tick_loop_sync` 同处）消费 `cmd_queue`，
   调 `process_agent_command` 得到 resp，用 `threading.Event`/future 把 resp 交回连接线程。
4. 事件产生点改造：`server.py:61` 记录聊天后 `publish({"event":"heard","kind":"wake",...})`；
   `local_agent.py` 的 `see`/`goto_done` 改为 `kind=observation`（可在 `wait` 或 ack 里带走，不单独唤醒）。
5. 端口与 token 落盘 `metaverse/.channel.json`（port/token/pid/started_at），CLI 读它连接；
   与 `.instance.lock` 的生命周期绑定（旧实例被杀时一起失效）。token 校验照 Fungi 的口径。
6. 两个 CLI 进 `pyproject.toml [project.scripts]`：
   `ghostworld-send`（一条命令 → 打印 JSON ack → 退出，退出码区分成功/失败）、
   `ghostworld-wait`（`--after <seq> --timeout 25 [--kinds wake]` → 阻塞 → 打印事件 JSONL；退出码 0=有事件 / 2=超时）。
7. 兼容层：保留 `agent_commands.jsonl` / `agent_output.jsonl` 的读写，但把它们实现成 EventBus 的**订阅者/生产者**
   （文件写入 = 一个订阅者；`read_commands` 仍可被 `--legacy-files` 打开），老工作流不炸、Mnemenet 那条线不受影响。
8. 顺手修掉丢数据缺陷：统一用 `seq` 游标（`listen_state.txt` 的行号机制退役）；日志文件只追加，
   按 seq 边界轮转而不是按行号截断。
9. 唤醒策略：**单回合 token**——一个 turn 进行中时，新玩家消息在 EventBus 排队，
   `ghostworld-wait` 期间不返回（或返回 `{"event":"queued","pending":N}`），
   回复结束后下一次 `wait` 一次性拿到（天然的批处理 + 不会两个回合互相打断）。
10. 文档与测试：更新 README/HANDOFF 的命令表与唤醒语义（顺手修 `metaverse/listen.py` 的路径错误）；
    测试 = EventBus 单元（游标/容量/并发/重复 ID）+ channel 线程边界（试图从连接线程直改 WorldState 的用例必须失败）+
    端到端（headless 起服务 → `send` 收 ack → `wait` 在 `publish` 后 <50ms 被唤醒）。

### 禁令措辞（已获批准）
`README.md:83-85` 改为：**"禁止 WebSocket 协议与 asyncio 网络 I/O；允许 `127.0.0.1` 上的同步 socket + 线程向队列投递"**。
理由：禁令针对的病因是"Windows WS + 异步网络 + 跨线程动世界"，本方案三条都不碰。

---

## Open Questions → 已结（2026-09-15）

| # | 问题 | 结论 |
|---|---|---|
| 1 | 游戏里的 Agent 是谁、它的 bash 能否"起后台进程并等输出" | **omp**；其长前台命令会自动转后台并投递输出（`hub start` + `logs follow`），**A 可行**。若某天换到带硬超时的 harness，退路是 Option B 的 25s 长轮询循环，唤醒语义不变 |
| 2 | 唤醒源范围 | **只有玩家 chat**（提问未勾选，按最保守取）；其余事件以 `kind=observation` 保留，可一行放开 |
| 3 | 旧文件通道去留 | **保留为兼容层**（读写都还能走文件） |
| 4 | 通信范围 | 只本机 `127.0.0.1`（我定，见"次要项"） |
| 5 | 观察事件是否唤醒 | **不唤醒**，只在 `wait --kinds observation` 或命令 ack 里捎带 |
| 6 | 端口策略 | 随机端口 + `.channel.json`（我定） |
| 7 | 迁移节奏 | 一次切到新通道 + 文件兼容层（我定） |

### 实现时发现的一个简化（推翻了原大纲第 9 条的一半）
原设想需要 Fungi 那样的"单回合 token"表（`_ACTIVE_TURNS`）来防两个回合互相打断。
**实际不需要**：Agent 在思考（发命令、生成回复）期间**根本不在 `wait` 上**，玩家这时说的第二句
只会安静地留在 EventBus 里；Agent 下一次 `wait` 立刻拿到（天然的排队 + 批处理）。
所以"排队"是缓冲的副作用，不是要额外实现的机制 —— 少一张全局状态表。


---

## Self-Review
- [x] 三个选项都直击 Problem（丢数据 + 轮询 → 唤醒）
- [x] Cons 不是装饰：A 的 harness 超时风险、B 的线程边界风险、C 的 fs 事件不可靠都写实了
- [x] 推荐 A 的依据是代码约束与 Fungi 的实测形状，不是偏好
- [x] Open Questions 都是真的需要他定的（尤其 Q1 决定 A/B）
