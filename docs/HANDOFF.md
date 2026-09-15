# HANDOFF — 现状与待办

> 更新：2026-09-15（通道重写完成）。上一版的两个待办——测试地图搬家、Agent 通道重写——都做完了。
> 本文现在是"当前是什么状态 + 怎么验 + 还剩什么"。

## 这次做完的三件事（3 个提交）

1. **测试地图搬出 `examples/`**（`chore(tests)`）：4 个只有测试在用的地图 `git mv` 进 `tests/fixtures/`
   （R100，历史保留）；4 个测试文件改指新位置；两个 window-detect 诊断改用 `tempfile.mkdtemp()`，
   测试不再往仓库里写 `_test_window.json`。顺手清掉 `tests/test_props_panel.py` / `tests/test_qtbot_diag.py`
   里硬编码的 `C:\tmp\ghostengine`（qtbot 那个还补了 `st.project_dir = tmpdir`，否则属性面板会去扫 cwd，
   在别的目录下跑会崩）。
2. **引入 ruff 门禁**（`chore(lint)`）：配置在 `pyproject.toml`，`ruff check .` 全绿。
   只选**缺陷类**规则；项目的房规故意不进规则——一行两条语句（`a = 1; b = 2`）、手排 import、
   清理路径的 `except: pass`、长数据行；`tests/scratch/` 排除在外。
   ruff 顺带修掉的真实问题：`ghostengine/renderer.py` 的 `FogConfig` 是未定义注解、
   `metaverse/server.py` 里 `_post_to_github` 重复 `import json`（遮蔽模块级）、10 处未使用局部变量、
   `tests/test_controller.py` 的 `pytest.raises(Exception)` 收窄成 `FrozenInstanceError`。
3. **Agent 通道重写**（`feat(channel)`，即 DESIGN/PLAN 的 Option A，14 个任务）——见下。

## 通道现在的形状

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
| `metaverse/channel_client.py` | **纯 stdlib、可整文件拷走**的客户端（给别的程序接） |
| `metaverse/cli_channel.py` | 两个 CLI 入口（退出码 0/1/2/3） |
| `docs/PROTOCOL-agent-channel.md` | 对外契约：线协议 / 发现文件 / 事件对象 / 游标 / 退出码 |

- **唤醒源只有玩家发言**（`kind=wake`）；`connected`/`see`/`goto_done`/`said` 等是 `kind=observation`，
  不唤醒、但可订阅（`--all` / `--kinds observation`），要放开某类只改一句 kind 策略。
- **红线**：通道线程只碰 `cmd_queue` 与 `EventBus`，**永不改 `WorldState`**；世界只被帧循环改。
  `tests/test_channel_server.py` 拿"碰一下就抛异常的假世界对象"把这条钉住（Boom 哨兵 + 线程 excepthook）。
- **旧文件通道是兼容层**：`agent_commands.jsonl` 仍被执行（agent 每 0.3s 读一次→投队列，
  改成先 move 再读，不再有"读后即删"竞态；解析失败的行报 `read_err` 而不是消失）；
  `agent_output.jsonl` 由 `FileSink` 这个订阅者写，事件带 `seq`，`listen.py` 按 seq 记游标。
- 三个丢数据缺陷都消失了：命令有 ack、日志按 seq 而非行号、`heard` 不再受 `chat_log` 50 条环形缓冲限制。

## 怎么验

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch   # 137 passed
ruff check .                                                             # All checks passed!
python headless_agent.py examples/demo_metaverse.json                     # 起无头游戏（自带帧循环）
ghostworld-send '{"cmd":"pos"}'        # → ack JSON，退出 0
ghostworld-wait --timeout 25           # → 阻塞；玩家说话才打印一行事件 JSON
```

真机实测（2026-09-15，headless + `pip install -e .` 后的 console script）：
`send pos` 0.48s 拿到 `{"type":"position","x":7.5,...}`；`wait --timeout 2` 阻塞 2.29s 后退出 3；
`wait --all` 把**连上之前就已发布**的 3 条事件一次交出（无丢失），紧接着第二次调用退出 3（**不重放**）；
`Ctrl+C` 后 `.channel.json` 被删除。

## 还剩什么 / 已知偏差

- **GUI 路径没真机手测**：`python -m metaverse.launch` 要真窗口，本次只验了 headless + 进程内 e2e。
  "玩家说话→唤醒"这条用真 socket 的进程内用例覆盖（`tests/test_channel_e2e.py`，断言 <50ms）。
- **一条通道 = 一个角色**：`hello` 里加 `as` 字段（一条通道驱动多个角色）刻意没实现，是留的加法点；
  现在是驱动游戏里那个 agent 角色（默认名 `omp`）。
- **Option B（HTTP 门面）**没做：同一个 `EventBus` 上再挂 `ThreadingHTTPServer` 即可，对现有代码零侵入。
- `docs/ARCHITECTURE.txt` 仍是旧的"文件通道"叙述（历史文档，未改）。
- `README` 的「已知限制」里那条 emoji 限制仍在。

## 环境备忘

- 测试：`PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch`
- 门禁：`ruff check .`（配置 `[tool.ruff]` 在 pyproject；显式传路径会绕过 `extend-exclude`）
- CLI：console script（`pip install -e .` 后 `ghostworld-send` / `ghostworld-wait`），
  没装也能用 `python -m metaverse.cli_channel send|wait`
- 单实例锁 `metaverse/.instance.lock`；全程不产生 `.pyc`（入口设 `sys.dont_write_bytecode`），
  清理残留用 `./pyclean`
- 运行期产物（均已 gitignore）：`metaverse/.channel.json`、`metaverse/.wait_cursor.json`、
  `metaverse/agent_output.jsonl`、`metaverse/tools/listen_cursor.json`
