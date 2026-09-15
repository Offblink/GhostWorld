# Agent 通道协议（v1）

> 给**另一个程序**看的规范：让 omp、Fungi 的 clone、任何 bot 驱动 GhostWorld 里的一个角色。
> 实现细节见 `DESIGN-agent-channel.md`；这里只写对外契约——协议、文件、退出码。
> 状态：已实现（2026-09-15），代码在 `metaverse/channel*.py`。

## 为什么是这三样东西

| 契约 | 内容 | 为什么这样定 |
|---|---|---|
| 传送 | `127.0.0.1` 上的行分隔 JSON，一次连接做一次动作 | 不引 WebSocket / MCP / asyncio（项目禁令的病因是那三样）；纯 stdlib |
| 发现 | `<游戏目录>/metaverse/.channel.json` | 端口随机，避免占用冲突；进程一退就删 |
| 唤醒 | 事件带单调 `seq`，客户端存游标 | 不轮询；丢事件会被**报出来**（`gap`），不静默 |

## 1. 发现文件

游戏启动时写，正常退出时删（`metaverse/.channel.json`）：

```json
{"protocol": 1, "port": 51234, "token": "<32 hex>", "pid": 24264, "started": 1757900000.0}
```

- `port`：`127.0.0.1` 上监听的端口，每次启动随机。
- `token`：握手必须带上。作用是**防误连/串台**（同机另一次运行、另一个 harness），
  **不是安全边界**——同机进程都读得到这个文件。
- 文件不存在 = 游戏没在跑；CLI 会给退出码 2。

## 2. 线协议

- TCP，`127.0.0.1`，**一行一个 JSON**（`\n` 结尾，UTF-8）。
- **一次连接只做一次动作**，之后服务端关闭连接（客户端不需要维护会话状态，CLI 每次调用都新建连接）。
- 客户端先发 `hello`，服务端回 `ok`（或 `error` 后断开）。

### 2.1 被唤醒（`role="wait"`）

```jsonc
// →
{"hello": {"token": "<token>", "role": "wait", "after": 12, "kinds": ["wake"], "timeout": 25}}
// ←
{"ok": true, "cursor": 12, "protocol": 1}
```

之后服务端**阻塞**在服务端的事件缓冲上，直到有事件或超时：

```jsonc
// 一批事件：每行一个裸事件对象，随后关连接
{"seq": 13, "ts": 1789436846.28, "kind": "wake", "event": "heard", "from": "player", "message": "在吗", "channel": "global", "tick": 4231}
// 或者超时：
{"timeout": true, "cursor": 12}
// 或者游标太旧（缓冲里那段时间的事件已经淘汰）：
{"gap": true, "oldest": 37, "cursor": 36}
```

- `after` 省略 = 只要「从现在起」的事件；传 `0` = 从缓冲区最老的开始（新进程 `seq` 从 1 重新开始，
  此时旧游标必须换成 0，见 §4）。
- `kinds` 省略 = 所有事件。`["wake"]` = 只有玩家发言会放行（Agent 的默认姿势）。
- **`gap` 之后仍会继续给还能取到的事件**，所以先收到 `gap` 再收到事件是正常的。
- 一次 `wait` 返回**一批**：思考期间玩家说的 N 句会一起到手（天然批处理，不会两个回合互相打断）。

### 2.2 执行命令（`role="send"`）

```jsonc
// →
{"hello": {"token": "<token>", "role": "send"}}
// ←
{"ok": true, "cursor": 0, "protocol": 1}
// →
{"cmd": {"cmd": "say", "message": "hi"}}
// ←                            （命令由游戏的帧循环执行后回填）
{"ack": {"type": "said", "from": "omp", "message": "hi", "channel": "global"}, "cursor": 14}
// 连上了但帧循环没跑（无头/卡住）：
{"error": "no ack", "cursor": 14}
```

`ack` 就是游戏 `handle_message` 的返回值（`{"type": ...}`），命令抛异常时是
`{"event": "cmd_error", "error": "..."}`。命令词表见 README 的「命令」表（与文件通道完全一致）。

### 2.3 失败

| 行 | 含义 |
|---|---|
| `{"error": "bad token"}` | token 不匹配，断开 |
| `{"error": "bad hello"}` | 第一条不是合法的 `hello` |
| `{"error": "missing cmd"}` | `role="send"` 但没给 `cmd` |
| `{"error": "unknown role: x"}` | `role` 不是 `wait`/`send` |

## 3. 事件对象

```json
{"seq": 13, "ts": 1789436846.28, "kind": "wake", "event": "heard", "from": "player", "message": "在吗", "channel": "global", "tick": 4231}
```

- `seq`：本进程内**严格单调**，从 1 开始（重启后重新从 1 开始）。
- `ts`：epoch 秒。
- `kind`：**`wake`** 只有「非 agent 的角色发言」（即玩家说话）；其余一律 **`observation`**
  （`connected` / `see` / `goto_done` / `said` / `position` / `perception` / `map_edit_sent` …）。
  要放开某类事件去唤醒 Agent，只改服务端一句 kind 策略，不动协议。
- `event`：沿用项目既有词表，不发明新名字。

## 4. 游标（客户端唯一要持久化的东西）

- 存**最后收到的事件的 `seq`**；下次 `wait` 用它当 `after`。
- 与 `.channel.json` 里的 `token`（或 `pid`）一起存：**token 变了说明换了一次游戏进程，
  `seq` 会从 1 重来**，此时必须用 `after=0`，否则会把新事件当成「已经看过的」而漏掉。
  `metaverse/.wait_cursor.json` 就是这个约定的一种实现，CLI 用它。
- 收到 `gap` 就说明有事件在缓冲区里被淘汰了：可以照常继续（`cursor` 已经替你对齐），
  但要**知道**自己漏了东西。

## 5. 退出码（CLI）

| 退出码 | `ghostworld-send` | `ghostworld-wait` |
|---|---|---|
| 0 | 收到 ack | 打印了事件 |
| 1 | 连上了但没有 ack | — |
| 2 | 连不上（游戏没在跑）／用法或 JSON 错误 | 同左 |
| 3 | — | 超时 |

## 6. 两种接法（都与本仓库**零代码耦合**）

> **推荐 6.1**：把它当一个常驻子进程来管（`ghostworld-wait --all --follow` 一行一个事件 JSON），
> 崩溃/结束能通过退出码看见（2 = 游戏没了），阻塞落在别人的进程里，协议带版本号所以内部怎么改都不关你的事。
> 6.2 只在「必须在自己进程内、且不能另起进程」时用——代价是那份拷贝会随时间过期。

### 6.1 起进程（最省事，任何语言都行）

```bash
ghostworld-send '{"cmd":"say","message":"你好"}'    # 一行 ack JSON
ghostworld-wait --timeout 25                        # 阻塞，玩家说话后打印一行事件 JSON
ghostworld-wait --all --follow                      # 常驻观察者，持续打印
```

没有安装包时等价地用 `python -m metaverse.cli_channel send|wait ...`。
harness 只要能「起一个进程并等它的 stdout」，就能接。

真机实测过的监管语义（2026-09-15，headless 游戏 + 已安装的 console script）：

| 场景 | 看到什么 |
|---|---|
| 有事件 | 立刻打印一行 JSON，**不按间隔攒批**（三条相隔 1s 的命令 → 行间隔 1.37s） |
| 连上之前就已发布的事件 | **不丢**：游标归零时缓冲里的事件一次交出 |
| 长时间没人说话 | 不退出、不忙等（空转超时只是重新开始等） |
| 你 Ctrl+C 它 | 退出 **0** |
| **游戏退出** | stderr 打印 `ghostworld-wait: channel went away`，退出 **2** —— 这是给监管者的信号：该重启就重启 |

### 6.2 进程内直连（把 `metaverse/channel_client.py` 拷进你的项目）

适合：调用方在自己的事件循环里，不能接受每次唤醒都起一个进程。

那个文件**只用 stdlib**（`json/os/socket/time`）、不 import 本仓库任何东西，可以整文件拷走：

```python
from channel_client import ChannelClient          # 你拷过去的那份

client = ChannelClient.from_file("C:/.../GhostWorld/metaverse/.channel.json",
                                 cursor_file="C:/.../my_own_cursor.json")
ack = client.send({"cmd": "say", "message": "你好"})          # 一次往返
for batch in client.iter_events(timeout=25, kinds={"wake"}):  # 常驻：玩家说话才醒
    for evt in batch:
        print(evt["from"], evt["message"])
```

失败是异常：`ChannelUnavailable`（没游戏）/ `NoAck`（帧循环没跑）/ `ChannelTimeout`（期限内没事件）。

## 7. 明确的非目标

- 不做 WebSocket / MCP / asyncio 网络 I/O。
- 只监听 `127.0.0.1`，不开局域网（要跨机就自己套隧道，协议本身不挡）。
- 通道线程**永不改 `WorldState`**：它只能投 `cmd_queue`、读 `EventBus`；世界只被帧循环改。
- 一条通道对应**一个角色**（游戏里那个 agent avatar，默认名 `omp`）。
  「一条通道驱动多个角色」需要给 `hello` 加 `as` 字段并在 drain 处指定角色名——目前**未实现**，
  是刻意留的加法点，不是漏掉的东西。
