# P0 缺陷修复报告

> 范围：`PROJECT_EVALUATION.md` §5.2 中标记为 P0 的四项。
> 原则：最小改动、定位根因、可复现验证。每项均给出「根因 → 最小修复 → 受影响模块 → 验证方式」。
> 验证基线：`Ran 209 tests, OK`（0 skipped），较修复前的 199 项增加 10 项。

---

## 总览

| 编号 | 问题 | 性质 | 改动文件 | 生产代码改动 |
|------|------|------|----------|--------------|
| P0-1 | 订单仓储与协作状态仓储后端不一致 | **潜在陷阱**（生产路径不可达） | `order_manager.py` | 是 |
| P0-2 | 7 个集成测试在 CI 中被永久跳过 | **真实缺口**（绿灯无意义） | `.github/workflows/ci.yml` | 否（CI 配置） |
| P0-3 | 3 个端点零测试覆盖 | **真实缺口** | `tests/test_http_api.py` | 否（仅测试） |
| P0-4 | `ESCALATE` 从不发出、`ReviewAssistant` 游离于任务 DAG 之外 | **真实缺陷**（设计与实现不符） | `supervisor.py`、`tests/support.py`、`tests/test_review_assistant.py` | 是 |

**诚实说明**：P0-1 在生产路径上不可达（详见该节「根因」），属于拆除陷阱而非修复线上故障。P0-2/P0-3 是验证能力缺口，不是运行时故障。**只有 P0-4 是会导致设计承诺落空的真实功能缺陷。**

---

## P0-1 仓储后端不一致

### 根因

`OrderManager.__init__` 对四个仓储采用了**互相矛盾**的默认值：

```python
self.repository = repository or PostgresOrderRepository(self.config.database.url)  # 持久
self.blackboard_repository = blackboard_repository or InMemoryBlackboardRepository()  # 易失
self.task_repository = task_repository or InMemoryTaskRepository()                   # 易失
self.message_repository = message_repository or InMemoryMessageRepository()          # 易失
```

订单快照落 PostgreSQL，而黑板 / 任务图 / 消息轨迹落进程内存。任何**不经过 `ApplicationContainer`** 的构造路径都会得到「脑裂」存储：重启后订单还在、处于 `PARSING`/`MATCHING` 等中间态，但任务图与消息轨迹已消失，且**不报任何错**——订单永久卡死。

**为何此前未爆发**：`application/container.py:47-52` 显式注入了全部三个 PostgreSQL 协作仓储，且所有 `OrderProcessingOrchestrator(...)` 调用点都传入 `order_manager`，因此不一致的默认值在生产路径上**不可达**。此外 `PostgresOrderRepository.__init__` 会立即 `_initialize_schema()` 建立连接，混用默认值会**大声失败**而非静默失败。因此这是陷阱，不是故障。

### 最小修复

让三个协作仓储**跟随订单仓储的后端与连接目标**；显式注入的仓储优先级不变。

```python
url = getattr(self.repository, "database_url", self.config.database.url)
in_memory = isinstance(self.repository, InMemoryOrderRepository)
self.blackboard_repository = blackboard_repository or (
    InMemoryBlackboardRepository() if in_memory else PostgresBlackboardRepository(url))
self.task_repository = task_repository or (
    InMemoryTaskRepository() if in_memory else PostgresTaskRepository(url))
self.message_repository = message_repository or (
    InMemoryMessageRepository() if in_memory else PostgresMessageRepository(url))
```

两处关键细节：

1. `getattr(self.repository, "database_url", ...)` 而非 `self.config.database.url`。测试会向订单仓储注入**隔离 schema** 的连接串（`tests/test_order_storage.py:155` 的 `make_conninfo(url, options="-c search_path=...")`），若直接用全局配置，协作仓储会写到 schema 之外，测试之间互相污染。
2. `isinstance(..., InMemoryOrderRepository)` 决定内存 / Postgres 分支，而非看配置——判断依据是**实际使用的适配器**，不是意图。

### 受影响模块

- `application/services/order_manager.py`（唯一生产代码改动）
- 间接：`application/container.py`（注入路径不变，行为不变）、`application/orchestrators/order_processing.py`
- 测试：`tests/test_order_storage.py`（`StorageContract` 对两种适配器跑同一套契约）

### 验证方式

```bash
# 内存分支（默认，无需数据库）
.venv/bin/python -m unittest tests.test_order_storage -v
# → Ran 12 tests, OK

# Postgres 分支（需真实数据库，见 P0-2 的启动方式）
TEST_DATABASE_URL="postgresql://orders@localhost:55432/orders_test" \
  .venv/bin/python -m unittest tests.test_order_storage -v
# → Ran 12 tests, OK（修复前该 6 项被 skip）
```

`StorageContract` 覆盖的正是本次要保护的不变量：CAS 陈旧写拒绝、独立客户端不丢更新、重启只回收过期在途单、并发 confirm/reject 单赢家、归档保留最新历史。

---

## P0-2 集成测试在 CI 中被永久跳过

### 根因

两个测试类用环境变量做开关：

- `tests/test_order_storage.py:148` — `@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), ...)` → 6 项
- `tests/test_runtime_integration.py:11` — `@unittest.skipUnless(os.getenv("RUN_EMBEDDING_INTEGRATION") == "1" and os.getenv("TEST_DATABASE_URL"), ...)` → 1 项

而 `.github/workflows/ci.yml` 既没有 `services:` 块，也从未设置这两个变量。后果：**每次 CI 绿灯，实际上有 7 项测试从未执行**。存储契约（并发 CAS、schema 隔离、重启回收）与端到端就绪检查（真实 Postgres + 真实 FAISS 索引构建）在 CI 中完全没有被验证——绿灯不构成任何关于持久化的证据。

### 最小修复

在 `backend-test` job 上加 PostgreSQL 服务容器 + job 级环境变量 + 嵌入模型缓存：

```yaml
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: orders
          POSTGRES_PASSWORD: orders
          POSTGRES_DB: orders_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U orders"
          --health-interval 10s --health-timeout 5s --health-retries 10
    env:
      TEST_DATABASE_URL: postgresql://orders:orders@localhost:5432/orders_test
      RUN_EMBEDDING_INTEGRATION: "1"
      HF_HOME: ${{ github.workspace }}/.cache/huggingface
```

外加一个 `actions/cache@v4` 步骤缓存 `HF_HOME`，避免每次 CI 重新下载 `all-MiniLM-L6-v2`。健康检查是必需的——否则测试可能在 Postgres 就绪前启动。

### 受影响模块

- `.github/workflows/ci.yml`（`backend-test` job）
- 激活的测试：`tests/test_order_storage.py::PostgresStorageTests`（6 项）、`tests/test_runtime_integration.py`（1 项）

### 验证方式

本地起一个临时 Postgres，然后**逐字执行 CI 的命令**：

```bash
# 一次性准备（验证用，已停止）
initdb -D /tmp/pgtest_data -U orders --auth=trust
pg_ctl -D /tmp/pgtest_data -o "-p 55432 -k /tmp" start
createdb -h localhost -p 55432 -U orders orders_test

# 等价于 CI 的 "Run unittest suite"
cd /Users/cmh/Documents/AGENT_project
TEST_DATABASE_URL="postgresql://orders@localhost:55432/orders_test" \
RUN_EMBEDDING_INTEGRATION=1 \
  .venv/bin/python -m unittest discover -s tests
```

实测结果：

| 状态 | 结果 |
|------|------|
| 修复前（无环境变量） | `Ran 199 tests`，`OK (skipped=7)` → 实际执行 192 项 |
| 修复后（含环境变量） | `Ran 209 tests`，`OK` → 实际执行 209 项，**0 skip** |

YAML 结构已用 `yaml.safe_load` 校验：`services: ['postgres']`、两个环境变量、6 个步骤顺序正确。

### 残余风险

`RUN_EMBEDDING_INTEGRATION=1` 让 CI 首次运行依赖 HuggingFace 网络下载。已用 `actions/cache` 缓解，但**缓存冷启动 + 网络受限的 runner 会导致该单项失败**。若不接受此依赖，可将该变量从 job 级下沉到单独一个「允许失败」的 job——这是刻意的取舍，不是遗漏。

---

## P0-3 三个端点零测试覆盖

### 根因

`tests/test_http_api.py` 覆盖了 `/api/upload`、`/api/upload_text`、`/api/orders`、`/api/orders/<id>`、`/api/orders/<id>/review-suggestion`、`/api/health`、`/api/ready`，但**完全没有**：

- `POST /api/confirm/<order_id>`（`flask_app.py:138`）——人工确认的**唯一写入口**
- `GET /api/orders/<id>/trace`（`:111`）
- `GET /api/orders/<id>/tasks`（`:119`）

后两者是**仅有的两个**把多 Agent 黑板（设计文档 §2.3 协作轨迹、§2.4 任务 DAG）暴露给运维的接口。未覆盖的分支包括：action 白名单校验、非字符串 comment 拒绝、未知订单的 404 分支、以及 trace/tasks 的响应体形状。

### 最小修复

在 `tests/test_http_api.py` 的 `FakeOrchestrator` 上补 `get_trace` / `get_tasks`，使路由经由**真实 Flask 层**被驱动，然后新增 9 项测试：

| 端点 | 新增断言 |
|------|----------|
| `/trace` | 200 + `messages[0].performative == "escalate"` + `verdicts` 透传；未知订单 404 |
| `/tasks` | 200 + `(agent, stage, status)` 三元组完整透传；未知订单 404 |
| `/confirm` | 正常委托并回传 `order_id`/`message`；非法 action 400；缺失 action 400；非字符串 comment 400；编排器失败 400 |

### 受影响模块

- `tests/test_http_api.py`（12 → 21 项测试）。**生产代码零改动**——本次修的是验证能力，不是行为。

### 验证方式

```bash
.venv/bin/python -m unittest tests.test_http_api -v
# → Ran 21 tests, OK
```

**变异测试（证明测试真的有效）**：把 `flask_app.py` 的 action 白名单从 `{"confirm","reject"}` 放宽为 `{"confirm","reject","maybe"}`：

```
FAIL: test_confirm_rejects_an_unknown_action (tests.test_http_api.HttpApiTests)
Ran 21 tests, FAILED (failures=1)
```

恢复后重新全绿。说明该测试确实锁住了校验逻辑，而非仅仅「跑过一行代码」。

---

## P0-4 `ESCALATE` 从不发出、`ReviewAssistant` 游离于 DAG 之外

### 根因

`Supervisor._run_adjudicate_stage` 收到 `Performative.VERDICT` 后**立即返回**：

```python
for message in messages:
    if message.performative == Performative.VERDICT:
        return dict(message.payload or {})   # ← 到此为止
```

当裁决携带 `needs_confirmation=True` 时，没有任何代码发出 `Performative.ESCALATE`；而 `ReviewAssistant` 只能通过**带外** HTTP 路由 `POST /api/orders/<id>/review-suggestion` 触达（`order_processing.py:285`）。四个后果：

1. `/trace` **答不出「为什么升级」**——升级事件根本不在消息轨迹里（与设计文档 §2.3「协作轨迹可审计」直接冲突）。
2. `/tasks` 看不到 assist 任务，任务 DAG 不完整（§2.4）。
3. 设计文档 §S8「`ReviewAssistant` 接入黑板，响应 `ESCALATE`」与 §3.3「从装饰变为参与者」**未实现**——这正是设计文档 §1 自我批评的第 3 条（"`ReviewAssistantAgent` 是装饰性的"）。
4. 审核参考只有**人工主动点击**才会生成。系统升级到人工，却不给人工任何材料。

### 最小修复

新增 `_escalate_and_assist(...)`，**仅在** `verdict["needs_confirmation"]` 为真时从 `_run_adjudicate_stage` 调用。它做四件事：

1. 广播 `ESCALATE`（sender=supervisor，`in_reply_to` 指向裁决消息），payload 携带 `action` / `reason` / `reason_chain`——让 `/trace` 能回答「为什么升级」。
2. 向任务图添加 `review_assistant` 任务，`stage="assist"`，slice key 为 `{matched_order, risk_result}`（复用既有的上下文切片机制，不新开旁路）。
3. 发送 `REQUEST` 给 `ReviewAssistant`（`ESCALATE` 是无收件人的广播声明，`REQUEST` 才是任务指派——符合 `domain/messages.py` 的 performative 语义）。
4. 执行该任务，并用 `try/except` 包裹：

```python
try:
    self._publish(board, {task.task_id: self._execute_task(task, budget)})
except Exception as exc:  # 审核助手是旁路，失败不得改变订单终态
    self._logger.warning("审核参考生成失败（不影响订单终态）: %s", exc)
```

第 4 点是刻意的：审核参考是**旁路**，生成失败绝不能把订单从 `NEEDS_CONFIRMATION` 拖走。

配套改动 `tests/support.py`：新增 `FixedReviewLLM` 作为审核助手的专用假模型。此前 `build_agents` 用 `llm=None` 构造 `ReviewAssistant`，会落到**真实客户端**上发起网络调用（曾导致测试进程被 SIGTERM，exit 137）；而若与抽取共用同一个载荷迭代器，审核助手会吃掉一条抽取载荷。

### 受影响模块

- `application/agents/supervisor.py`：import 补 `MatchedOrder`/`RiskCheckResult`；`_run_adjudicate_stage` 增加一个条件调用；新增 `_escalate_and_assist` 方法。
- `tests/support.py`：`FixedReviewLLM`、`REVIEW_SUMMARY`，`build_agents`/`build_harness` 增加 `review_llm` 参数。
- `tests/test_review_assistant.py`：新增回归测试。
- 间接：`application/blackboard/blackboard.py` 的 `record()` 已能把 `INFORM` 分发到 Layer 2（`append_evidence`），无需改动即满足 §S8。

### 验证方式

```bash
.venv/bin/python -m unittest tests.test_review_assistant -v
# → Ran 8 tests, OK
```

回归测试 `test_escalation_is_recorded_and_assist_task_is_dispatched` 断言四件事：

1. 轨迹中存在 `ESCALATE`，sender=supervisor，`payload.action == "manual_review"`
2. 轨迹中存在 `REQUEST`，recipient=review_assistant
3. 任务图中恰有一个 `stage="assist"` 任务，`agent=review_assistant`，`status=DONE`
4. ReviewAssistant 的 `INFORM` **携带 evidence** → 即设计 §S8 要求的「输出写入黑板 Layer 2 作为证据」

实测轨迹（截取末尾）：

```
     adjudicator verdict    -> None               ev=1
      supervisor escalate   -> None               ev=0
      supervisor request    -> review_assistant   ev=0
review_assistant inform     -> None               ev=1   ← Layer 2 证据
```

任务图末行：`review_assistant  stage=assist  status=done`。

**变异测试（证明测试真的锁住了缺陷）**：把 `_escalate_and_assist` 的调用替换为 `pass`：

```
AssertionError: 'escalate' not found in {'inform': [...], 'propose': [...],
  'refuse': [...], 'verdict': [...]}
Ran 1 test, FAILED (failures=1)
```

恢复后重新全绿。变异已确认完全回退（`git diff` 中无残留标记）。

---

## 汇总验证

```bash
cd /Users/cmh/Documents/AGENT_project
TEST_DATABASE_URL="postgresql://orders@localhost:55432/orders_test" \
RUN_EMBEDDING_INTEGRATION=1 \
  .venv/bin/python -m unittest discover -s tests
# → Ran 209 tests in 21.055s
# → OK
```

测试数量变化：199 → 209（+9 端点测试，+1 升级回归测试）；跳过数 7 → 0。

## 本次未提交的改动清单

```
.github/workflows/ci.yml                 P0-2
application/agents/supervisor.py         P0-4
application/services/order_manager.py    P0-1
tests/support.py                         P0-4（测试设施）
tests/test_http_api.py                   P0-3
tests/test_review_assistant.py           P0-4（回归测试）
tests/test_runtime_integration.py        修正失效引用（matching_agent → faiss_manager）
```

## 遗留事项（非 P0）

- `interfaces/http/flask_app.py:180` 的 `app.run(..., threaded=False)`：单线程开发服务器。生产走 gunicorn（`gunicorn.conf.py`），但该默认值容易误用。
- `RUN_EMBEDDING_INTEGRATION` 引入的 CI 网络依赖（见 P0-2 残余风险）。
- `PROJECT_EVALUATION.md` §5.2 中的 P1/P2 项尚未处理。
- `.workbuddy-ai/` 目前未提交，是否纳入版本控制待确认。
