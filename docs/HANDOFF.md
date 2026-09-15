# HANDOFF — 现状与待办

> 更新：2026-09-15。上一版 HANDOFF（根目录的「Agent 操控指南」）已删除——它的内容已被
> README 的 `## Agent 控制` 段覆盖，不需要第二份。

## 仓库现状（2026-09-15）

- **文档已归位**：`ARCHITECTURE.txt` / `SPEC.md` / `DESIGN-agent-channel.md` / `PLAN-agent-channel.md` /
  `GhostWorld_知乎文章.txt` 全部迁入 `docs/`（tracked 的走 `git mv`，历史保留）；根目录只剩 `README.md`，
  README 里加了文档索引表。
- **`.gitignore` 已补**：`build/` `dist/` `.venv/` `venv/` `.mypy_cache/`，以及
  `metaverse/.channel.json`（通道方案的运行期产物，先占位）。
- 根目录空的 `dist/`（构建残留）已删。
- 测试基线：`PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch` → **112 collected**。
- ⚠ **以上改动全部在工作区，没有任何 commit。**

---

## 待办 1：把 `examples/` 里的测试夹具搬到 `tests/fixtures/`

### 问题
`examples/` 里混着 4 个**只有测试在用**的地图，它们不是示例地图：

- `examples/_test_A.json`、`examples/_test_B.json`
- `examples/_test_portal_A.json`、`examples/_test_portal_B.json`

两个副作用：
1. 编辑器的地图列表会把它们当示例地图列出来——编辑器加载项目目录下**所有** `.json`
   （`editor/window.py:414` 原文："编辑器自动加载同目录下所有 `.json` 地图"）。
2. `tests/test_window_detect.py:28-30` 还会往 `examples/` **写**一个 `_test_window.json`，
   跑完测试在仓库里留垃圾。

### 硬约束：两个文件必须成对同目录
`_test_A.json` 的传送门里写着 `portal_target.map = "_test_B.json"`，而 `WorldState.maps` 只预加载
**与当前地图同目录**的 `.json`；测试里有 `assert "_test_portal_B.json" in ws.maps`。
所以搬动必须**成对搬进同一个目录**，不能只搬一个。

### 要改的引用（全仓扫描结果：3 处读 + 1 处写盘）

| 文件 | 位置 | 改法 |
|---|---|---|
| `tests/test_teleport_e2e.py` | 11–13 行 `EXAMPLES = os.path.join(ROOT, "examples")` / `MAP_A` / `MAP_B` | 指向 `tests/fixtures/` |
| `tests/test_portal_pairing_e2e.py` | 22 行 `os.path.join(ROOT, "examples", "_test_portal_A.json")` | 指向 `tests/fixtures/` |
| `tests/test_window_detect.py` | 28–30 行：把生成的 `_test_window.json` 写进 `examples/` | 改用 `tempfile.mkdtemp()` |
| `tests/test_window_detect2.py` | 23 行硬编码 `C:\tmp\ghostengine\examples` | 同样改临时目录（这行本就是机器残留） |

搬动命令（tracked 文件用 `git mv` 保历史）：

```bash
mkdir -p tests/fixtures
git mv examples/_test_A.json examples/_test_B.json \
       examples/_test_portal_A.json examples/_test_portal_B.json tests/fixtures/
```

### 验收
- [ ] `PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch` 全绿（112）
- [ ] 跑完测试后 `git status` 里 `examples/` 不再冒出新文件
- [ ] 编辑器打开项目时地图列表里不再有 `_test_*`
- [ ] `examples/` 只剩 `demo_metaverse.json` / `0707.json` / `untitled.json` / `states/`

### 为什么单独一次提交
它同时是「文件搬家 + 测试代码改动 + 消除写盘副作用」三件事，和文档归位放一起会让 review 与回退都变难。

---

## 待办 2：Agent ↔ 世界 通道重写（方案已批准，代码零改动）

- `docs/DESIGN-agent-channel.md` —— 脑暴、三个方案的取舍、4 条已确认决策（选 Option A）
- `docs/PLAN-agent-channel.md` —— 14 个任务 / 5 阶段 / 3 检查点 / 红线与接口契约

恢复点：PLAN 的 **Task 1**（`metaverse/channel.py` 的 `EventBus`）。开工前需先改 README 的禁令措辞
（PLAN Task 12 已写明改成什么）。

---

## 环境备忘

- 单实例锁：`metaverse/.instance.lock`（启动时杀旧实例再抢锁，见 `metaverse/launch.py:_acquire_lock`）
- 全程不产生 `.pyc`：入口设 `sys.dont_write_bytecode = True`；清理残留用 `./pyclean`
- 测试：`PYTHONIOENCODING=utf-8 python -m pytest tests -q --ignore=tests/scratch`
- 已知文档漂移：README 写 `python metaverse/listen.py`，实际文件在 `metaverse/tools/listen.py`
  （PLAN Task 12 会一并修）
