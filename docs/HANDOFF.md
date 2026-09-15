# HANDOFF — 现状与待办

> 更新：2026-09-15（通道重写 + Fungi 接入）。接手先看这份；协议细节在
> `docs/PROTOCOL-agent-channel.md`。

## 这次做完的事

1. **测试地图搬出 `examples/`**（`405336a`）：4 个只有测试在用的地图进 `tests/fixtures/`，两个
   window-detect 诊断改用临时目录；清了硬编码的 `C:\tmp\ghostengine`。
2. **引入 ruff 门禁**（`25ce4bb`）：`[tool.ruff]` 在 pyproject，只选缺陷类规则；修掉它找到的真问题
   （`renderer.py` 的 `FogConfig` 未定义注解、`server.py` 重复 import、10 处未使用局部变量…）。
   注意：`ruff format` 会重写 **43 个**既有文件（仓库是用旧版 ruff 格式化过的），所以格式一律不碰。
3. **Agent 通道重写**（`8c7f38b` + `8725bf3` merge + `eb9e16e` + `e9440f6` + `97595ae`）：见下。
4. **Fungi 侧的接入**（Fungi 仓库 `55464bc`，**未推**）：`fungi/tools/ghostworld.py`。

## 通道的形状

```
玩家 Enter → handle_message(say) → EventBus.publish({heard, kind=wake}) ─┐
                                                                        ↓
外部 Agent ── ghostworld-wait（阻塞 recv）←── 127.0.0.1 socket ←─────────┘
Agent ── ghostworld-send '{"cmd":...}' → cmd_queue → 帧循环 drain → handle_message → ack 原路返回
```

| 文件 | 作用 |
|---|---|
| `metaverse/channel.py` | `EventBus`（单调 seq + 有界缓冲 + `Condition`，零 IO）、`PendingCommand`、`FileSink` |
| `metaverse/channel_server.py` | 回环 socket、行 JSON、`.channel.json` 读写与清理 |
| `metaverse/channel_client.py` | 纯 stdlib、可整文件拷走的客户端 |
| `metaverse/cli_channel.py` | 两个 CLI（退出码 0/1/2/3） |
| `docs/PROTOCOL-agent-channel.md` | 对外契约：线协议 / 发现文件 / 事件对象 / 游标 / 退出码 |

红线：通道线程只碰 `cmd_queue` 与 `EventBus`，**永不改 `WorldState`**（`tests/test_channel_server.py`
用"碰一下就抛异常的假世界对象"钉住）。旧 jsonl 通道是兼容层（命令先 move 再读；`agent_output.jsonl` 由
总线订阅者写、每行带 seq；`listen.py` 按 seq 记游标）。

## 起 metaverse 指南（详细）

### 0. 前置（本机已满足）

- Python ≥ 3.10（本机 3.13.7）；`pip install -e . --no-deps`（已做过 → `import metaverse` 走仓库源码）
- 依赖 `pygame` `numpy`（GUI 用）；无头模式不需要开窗
- 两个 CLI 已装成 console script：`ghostworld-send` / `ghostworld-wait`
  （没装也能用 `python -m metaverse.cli_channel send|wait`）
- 单实例锁 `metaverse/.instance.lock`：`launch.py` 启动时会**杀掉旧实例**再抢锁——别同时开两份 GUI
- 全程不产生 `.pyc`（入口设 `sys.dont_write_bytecode`）；清残留用 `./pyclean`

### 1. 起游戏（三选一）

```bash
# ① GUI 正常玩（自己也能打字）
python -m metaverse.launch                              # 默认地图（记得 examples/.last_map）
python -m metaverse.launch examples/demo_metaverse.json  # 指定地图
python launcher.py                                       # GUI 启动器（需 PySide6）

# ② 联调夹具（推荐给 Agent 场景）：无头 + 一个会说活的玩家
python headless_player.py
python headless_player.py examples/demo_metaverse.json --say 你好 --after 3

# ③ 无头 + agent（没有人类玩家）
python headless_agent.py examples/demo_metaverse.json
```

启动会打印 `Channel on 127.0.0.1:<port>`，并把 port/token/pid 写进 `metaverse/.channel.json`；
退出（Ctrl+C 或正常结束）时会删掉它。CLI 就是读这个文件找游戏的。

### 2. 通道是否活着（不用装东西）

```bash
ghostworld-send '{"cmd":"pos"}'      # → {"type":"position","x":7.5,"y":1.5,...}，退出 0（~0.5s）
ghostworld-send '{"cmd":"say","message":"你好"}'
ghostworld-wait --timeout 5          # 阻塞；玩家说话才打印一行 JSON；没事件则退出 3
ghostworld-wait --all --follow       # 常驻观察者（连 observation 一起打印）
```

退出码：`send` 0/1/2（1 = 通道在但帧循环没跑，2 = 游戏没在跑）；`wait` 0/2/3（3 = 超时）。

### 3. Fungi 怎么接上（本次已配好）

1. **config.json 已写**：`"ghostworld": true`、`"ghostworld_dir": "<GhostWorld 仓库绝对路径>"`。
   开关是**许可**：关 = 工具不进工具面、监视器不 arm、没有子进程；开着时工具每次调用还会再查一次，
   所以关掉立刻生效。设置页在**「拓展」**一节（不是「实验性」——判据见 spec §43：VidSense 与 GhostWorld
   都是独立项目），右上角开关即时写盘。
2. **起 Fungi（房间模式：托盘 / WebUI）**。被叫醒的是**本机 Agent**（Fungi 里那个你直接对话的 Agent）。
3. 玩家在游戏里打字 → Agent 被叫醒，读到的输入长这样：
   `[GhostWorld] 玩家（player）说：…` → 它用 `ghostworld` 工具回话/走动/拾取。
4. 看它有没有真的动：直接看游戏画面；或在另一端 `ghostworld-wait --all --follow` 看事件流。

⚠ **游标是共享的**：`metaverse/.wait_cursor.json` 只有一个，所有消费者（Fungi 的监视器、你手工跑的
`ghostworld-wait`）共用它 → **同时用会让两边互相吃掉事件**。调试时只留一边。

### 4. 排查

| 症状 | 原因 / 处理 |
|---|---|
| `channel not found — 游戏没在跑？` | `.channel.json` 不存在：游戏没起、或已退出 |
| `no ack`（退出 1） | 通道在，但帧循环没跑（GUI 卡住；无头忘了 ticker） |
| 玩家打字但 Agent 不动 | ① 开关（config / 设置页）；② `ghostworld_dir` 是否指向游戏仓库；③ 上一节那个游标冲突 |
| 游戏关掉又开 | 不用管：Fungi 的监视器 30s 内自己重连，且**不丢事件**（游标在游戏侧，按 seq 续） |
| 想自己写客户端 | 读 `docs/PROTOCOL-agent-channel.md`；或把 `metaverse/channel_client.py` 整文件拷走（纯 stdlib） |

## 还剩什么

- **Fungi 的提交没推**（`55464bc`，Fungi `main` ahead 1）——按规矩 push 要你说。
- **真机 LLM 回合没跑**（要 API key）：GhostWorld 侧与 Fungi 侧的契约都测了，但"Agent 真的边玩边回话"
  这件事没人看过。跑一次就知道提示词够不够。
- 一条通道 = 一个角色：`hello` 加 `as` 字段（多角色）刻意没做，是留的加法点。
- Option B（HTTP 门面）没做：同一个 `EventBus` 上挂 `ThreadingHTTPServer` 即可，零侵入。
- `README` 的「已知限制」里那条 emoji 限制仍在。

## 验证证据（本机实测）

- `PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch` → **139 passed**；`ruff check .` 全绿
- 真机（无 LLM）：`send pos` 0.48s 回 ack；`wait --timeout 2` 阻塞 2.29s 后退出 3；`wait --all` 把
  **连上之前就已发布**的事件一次交出，第二次调用退出 3（不重放）；Ctrl+C 后 `.channel.json` 被删。
- **Fungi 侧真机**（`headless_player.py` 起游戏 + 直接调 `fungi.tools.ghostworld`）：
  `send_command(pos)` 拿到真 ack、`look` 拿到 perception；`arm()` 后 **0.4s** 收到玩家真实发言
  （`seq=1, kind=wake, from=player`，且发表于连上之前 → 没丢）；`disarm()` 后监视器与子进程都不剩。
- Fungi 门禁：`pytest tests -q` → **582 passed**；`ruff check .` / `ruff check fungi tests` 全绿
  （`shots/` 是 scratch，已进 `extend-exclude`）。

## 环境备忘

- 测试：`PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch`
- 门禁：`ruff check .`（配置在 pyproject；显式传路径会绕过 `extend-exclude`）；格式不要动（见上）
- 运行期产物（均已 gitignore）：`metaverse/.channel.json`、`metaverse/.wait_cursor.json`、
  `metaverse/agent_output.jsonl`、`metaverse/tools/listen_cursor.json`
