# 项目全面评价报告

> 评价对象：制造业订单解析平台（`AGENT_project`）
> 评价基准：`MANUFACTURING_ORDER_PLATFORM_GOALS.md`、`MULTI_AGENT_DESIGN.md`、`PROJECT_ANALYSIS.md`
> 评价方式：全量 AST 静态核验 + 199 例自动化测试实跑 + 两家真实 API 端到端冒烟
> 评价日期：2026-09-29

---

## 0. 总评

| 维度 | 评级 | 一句话结论 |
| --- | --- | --- |
| 整体架构 | **优** | 零跨层违规，domain 层绝对纯净；架构纪律明显高于同规模项目 |
| 代码质量 | **良** | 零 TODO/FIXME，注释解释"为什么"而非"是什么"；两个模块偏重 |
| 功能完成度 | **良** | 设计文档核心机制已落地并有 V1–V7 验证；三个 P0 承诺未闭合 |
| 可维护性 | **良** | 依赖全量 pin、部署健康检查完备；依赖版本偏旧、声明式守卫未生效 |
| 运行风险 | **中偏高风险** | 默认生产路径零测试覆盖 + 持久化策略不一致 + 单 worker 串行 |

**核心判断**：这是一个**架构设计水平明显高于工程完成度**的项目。骨架（六边形分层 + 黑板式多智能体 + 对抗协议）立得很正，且有自动化验证兜底；但"最后一公里"——生产路径的测试覆盖、持久化一致性、并发容量——尚未收口。**当前状态可以正确运行，但不具备生产可靠性。**

---

## 1. 客观指标

### 1.1 代码规模

| 层 | 文件数 | 行数 | 占比 |
| --- | --- | --- | --- |
| `domain`（领域层） | 8 | 716 | 10% |
| `application`（应用层） | 31 | 4,878 | 70% |
| `infrastructure`（基础设施层） | 12 | 1,154 | 17% |
| `interfaces`（接口层） | 4 | 212 | 3% |
| **业务代码合计** | **55** | **6,960** | 100% |
| `tests`（测试） | 20 | 3,578 | — |
| `scripts`（工具） | 11 | 896 | — |
| `evaluation`（评测） | 5 | 1,698 | — |

**测试/业务代码比 = 0.51 : 1**，对含大量确定性规则的业务系统属健康区间（不是靠测试数量堆出来的）。

### 1.2 复杂度热点

仅 **4 个函数超过 60 行**，整体函数粒度控制良好：

| 行数 | 位置 | 说明 |
| --- | --- | --- |
| 144 | `interfaces/http/flask_app.py:23` `create_app` | 组合根，长属可接受 |
| 97 | `application/blackboard/slices.py:42` `build_slice` | 上下文切片构造，分支多 |
| 65 | `application/agents/disambiguator.py:55` `decide` | 消歧决策 |
| 64 | `application/pipeline/stages.py:46` `execute` | 节点执行器（含重试循环） |

最大模块（需关注职责集中度）：

| 行数 | 模块 |
| --- | --- |
| 568 | `application/agents/supervisor.py` |
| 476 | `application/services/order_manager.py` |
| 338 | `application/agents/extractor.py` |
| 320 | `application/orchestrators/order_processing.py` |
| 291 | `application/blackboard/blackboard.py` |

### 1.3 技术债标记

**`TODO` / `FIXME` / `HACK` / `XXX` = 0 处。** 仅有 23 处 `# noqa`（多数是 `# noqa: BLE001` 的 broad-except 显式标注，属有意为之）。

这是一个**双面信号**：好的一面是没有"以后再说"的隐性欠账；需警惕的一面是**问题可能都被写进了文档而不是代码**——本次评价中发现的持久化不一致、端口层错位等问题，代码里没有任何标记提示。

---

## 2. 整体架构评价

### 2.1 分层方向：零违规（全量 AST 核验）

对 `domain` / `application` / `infrastructure` / `interfaces` 四层全部 55 个模块做了导入图分析：

```
[OK] application    -> domain          63 次
[OK] application    -> infrastructure   9 次
[OK] infrastructure -> domain           9 次
[OK] interfaces     -> application      1 次
[OK] interfaces     -> domain           1 次

真实跨层违规：无
```

**`domain` 层的外部依赖只有 `typing` / `enum` / `uuid` / `datetime` / `math` / `__future__` 与 `pydantic`。**
没有一条 `from application.*` 或 `from infrastructure.*`。这意味着领域模型与状态机可以脱离框架独立测试——这是六边形架构最容易被破坏、也最难修复的一条约束，本项目守住了。

### 2.2 问题一：端口归属层错位，"依赖倒置"只做了一半

仓储确实有抽象（4 个 ABC）：

```
infrastructure/repositories/order_repository.py      → class OrderRepository(ABC)
infrastructure/repositories/blackboard_repository.py → class BlackboardRepository(ABC)
infrastructure/repositories/message_repository.py    → class MessageRepository(ABC)
infrastructure/repositories/task_repository.py       → class TaskRepository(ABC)
```

**但抽象被定义在 `infrastructure` 层，而 `application` 层直接 import 了具体实现类：**

```python
# application/services/order_manager.py:12-22
from infrastructure.repositories import (
    BlackboardRepository, MessageRepository, OrderRepository,
    PostgresOrderRepository,          # ← 具体实现
    TaskRepository,
)
from infrastructure.repositories.memory import (
    InMemoryBlackboardRepository, InMemoryMessageRepository, InMemoryTaskRepository,
)
```

同类问题另有三处直达具体实现的依赖：

| 位置 | 依赖 |
| --- | --- |
| `application/agents/review_assistant.py:70` | `infrastructure.vector_store.faiss_manager` |
| `application/agents/semantic_matcher.py:32` | `infrastructure.vector_store.faiss_manager` |
| `application/orchestrators/order_processing.py:44` | `infrastructure.document_processing` |

**说明**：`application/container.py` 的 5 处 `infrastructure` 依赖是**合法**的——组合根（composition root）的职责就是知道具体实现并完成装配。上面 4 处不是。

**影响**：
- 应用层知道"存储是 Postgres"，换存储需要改应用层代码，而不是只换适配器；
- 应用层的单元测试必须知道 Postgres 类的存在，被迫 mock 基础设施细节；
- 设计文档承诺的 `application → infrastructure via abstract ports` 实际未达成。

**正确形态**：端口（ABC/Protocol）定义在 `application/ports/`，`infrastructure` 去实现它，`application` 只依赖端口。

### 2.3 问题二：持久化策略不一致（真实缺陷，非风格问题）

`application/services/order_manager.py:168-172`：

```python
self.repository           = repository or PostgresOrderRepository(self.config.database.url)  # 持久
self.blackboard_repository = blackboard_repository or InMemoryBlackboardRepository()          # 易失
self.task_repository       = task_repository or InMemoryTaskRepository()                      # 易失
self.message_repository    = message_repository or InMemoryMessageRepository()                # 易失
```

**订单快照落 Postgres，但黑板、任务图、消息记录全在进程内存。**

重启后会出现**状态错位**：

- 订单本身还在（`/api/orders/<id>` 正常返回）；
- 但它的任务图与消息全部丢失 → `/api/orders/<id>/tasks`、`/api/orders/<id>/trace` **静默返回空**；
- 订单状态显示"处理中"，而驱动它的任务已不存在 → **订单永久卡死，且没有任何报错**。

这类缺陷比崩溃更危险：崩溃会被发现，状态错位不会。而它恰好落在**没有任何测试覆盖**的两个端点上（见 §3.2）。

### 2.4 架构验证机制（亮点）

`tests/test_verification_v1_v7.py` 把架构约束**变成了可执行的断言**，而不是写在文档里的君子协定：

| 验证 | 内容 | 机制 |
| --- | --- | --- |
| V1 | 通信拓扑：Agent 零直接调用 | AST 扫描 `application/agents/*.py` |
| V2 | 调度顺序无关性 | 打乱就绪任务顺序，20 个随机种子结果一致 |
| V3 | 幻觉质疑召回率 | 对抗集 recall 1.0 |
| V4 | 上下文隔离消融 | 隔离 1.0 vs 泄漏 0.0 |
| V5 | 反事实归因 | 8 个 pipeline agent 无零贡献行 |
| V6 | 并行收益 | 分组并发 vs 串行对比 |
| V7 | 故障注入 | worker 崩溃重试 / 超时与 schema 分类 / 预算耗尽升级 / 并发确认 CAS |

**V1 在本次评价中真实发挥了作用**：我尝试把输出截断守卫放进 `extractor.py` 供 `review_assistant.py` 复用时，被 V1 的 AST 扫描直接拦下（禁止同层 Agent 互相引用），迫使守卫下沉到 `application/protocol/`。**一个能拦住开发者走捷径的测试，才是有效的架构约束。**

---

## 3. 代码质量与功能完成度

### 3.1 已实现（对照设计文档，有验证支撑）

| 设计承诺 | 落地位置 | 验证 |
| --- | --- | --- |
| 三层黑板（L3 控制态 / L2 主张与证据 / L1 订单事实） | `application/blackboard/` | 写入权限分离 |
| 结构化消息 + 7 种语用（REQUEST/INFORM/PROPOSE/CHALLENGE/VERDICT/REFUSE/ESCALATE） | `domain/messages.py`、`domain/agent_roles.py::ROLE_PERFORMATIVES` | 语用权限表强制 |
| 对抗协议 PROPOSE → CHALLENGE → VERDICT | `application/protocol/adversarial.py` | V3 |
| 任务 DAG + 并行扇出 + 独立重试 | `application/pipeline/`、`domain/tasks.py` | V2 / V6 |
| 上下文切片隔离（`FORBIDDEN_KEYS` / `READABLE_KEYS`） | `domain/agent_roles.py` | V4 |
| 预算与熔断（token / 调用 / 墙钟） | `application/protocol/budget.py` | V7 |
| 重试分类（瞬态 / 结构 / 截断） | `application/pipeline/stages.py:78-94` | V7 + `test_model_truncation.py` |
| 角色级多模型路由 | `config.py::model_for()` | `test_model_routing.py` |
| 多 Sheet Excel / PDF 分页 / 图像路由 | `infrastructure/document_processing/` | `test_excel_parsing.py` 等 |
| 编排器降级为薄适配层 | `application/orchestrators/order_processing.py` | 320 行 |

### 3.2 未完成 / 未闭合

**P0 — 影响设计承诺的完整性**

1. **`ReviewAssistant` 未接入 Supervisor 的 DAG。** 只接了"人工请求"这一半（`POST /review-suggestion` 直调 `suggest()`），**ESCALATE 那一半没接**——Supervisor 从未创建过 `REVIEW_ASSISTANT` 任务。
   → 后果：11 个角色里只有 `Extractor` 一个 LLM 角色真正参与自动流程。
2. **`Performative.REQUEST` / `ESCALATE` 声明了但从未发出。** Supervisor 直接构造 `Task` 而不写 `REQUEST` 消息；预算耗尽只写控制层 `escalation` 键。
   → 后果：`/trace` 看不到"谁被派了什么任务""为何升级"，可观测性有洞。
3. **设计文档 §4.3 的端到端对比矩阵（单 Agent 基线 vs Multi-Agent）未产出。** 且 `ParserAgent` 等基线代码已删除，要出基线需先复活或改用"关闭对抗协议"的消融配置。
   → 后果：**"多 Agent 比单 Agent 更好"这一核心论点目前没有量化证据。**

**P1 — 工程质量**

4. **端点测试覆盖不完整。** 实测覆盖情况：

| 端点 | 覆盖 |
| --- | --- |
| `/api/health`、`/api/ready` | 有 |
| `/api/upload`、`/api/upload_text` | 有 |
| `/api/orders`、`/api/orders/<id>` | 有 |
| `/review-suggestion` | 有 |
| `/api/orders/<id>/trace` | **无** |
| `/api/orders/<id>/tasks` | **无** |
| `/api/confirm/<id>` | **无** |

`/api/confirm` 是**唯一改变订单终态的关键写端点**，其 CAS（`expected_updated_at` 乐观锁）逻辑仅在服务层被 V7 覆盖，未走 HTTP 层。

5. **Postgres 路径从未在本地/CI 跑过。** 7 个被跳过的用例正是 Postgres 集成测试（需 `TEST_DATABASE_URL` 与 `RUN_EMBEDDING_INTEGRATION=1`）：

```
tests/test_order_storage.py:148      @unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), ...)
tests/test_runtime_integration.py:11 @unittest.skipUnless(RUN_EMBEDDING_INTEGRATION=="1" and TEST_DATABASE_URL, ...)
```

而 §2.3 已确认**默认仓储就是 Postgres**。**结论：CI 全绿 ≠ 生产可用。**

6. **任务租约与崩溃恢复未测试。** `recover_orphan_tasks(ttl_seconds=180)` 存在且在容器启动时调用，但无任何用例覆盖"租约过期 → 任务被重新接管"。

7. **"声明即代码"的三处缺口**——定义了但没有任何调用方：

| 声明 | 实际承担者 |
| --- | --- |
| `domain/agent_roles.py::is_readable()` | `slices.py::build_slice` 是手写字典，未调用它 |
| `application/protocol/budget.py::RetryBudget` | 重试计数实际由 `Task.attempts` 承担 |
| `application/agents/base_agent.py::assert_no_agent_references()` | V1 用自己的 AST 扫描，未调用它 |

这三处的共同风险：**改了一处忘了另一处**，且读代码的人会误以为约束已强制。

**P2 — 口径与细节**

8. V3/V4 的"单 Agent 自检基线"是**建模值 0.0**，不是实测值。
9. V5 仅用 6 个人工构造场景，非评测集全量。
10. 前端未改动，`frontend/src/main.tsx` 仍是巨型 JSX（历史问题）。

### 3.3 本轮修复的真实缺陷（作为代码质量佐证）

评价过程中通过真实接口实测发现并修复了 3 个缺陷，均属"不崩溃但会静默出错"类型：

| 缺陷 | 根因 | 影响 |
| --- | --- | --- |
| 输出截断被误判为结构错误 | 推理模型的"思考"与"正文"共享 `max_tokens`；预算耗尽时返回 HTTP 200 + `finish_reason='length'` + `content=''` | 空串被当成"JSON 格式错误"，带着无关的字段级反馈重抽，既误导模型又掩盖根因；`ReviewAssistant` 原 `max_tokens=1024` 低于实测 reasoning 消耗（1158–1982），是稳定截断点 |
| 用量重复计数 | `Extractor.last_usage` 跨 `handle()` 累积，每条 INFORM 携带累计快照，Supervisor 汇总时把 2 次调用算成 3 次 | token 记账失真 |
| 诊断信息丢失类型 | 节点记录只存 `str(error)` | 无法区分 `TimeoutError` 与业务错误 |

修复方式：新增 `ModelTruncationException`（可重试、**不带**结构反馈）+ `application/protocol/model_output.py::assert_not_truncated()`；输出上限提到 `16384` / `4096`。

---

## 4. 可维护性与潜在风险

### 4.1 做得好的地方

- **依赖全量精确 pin**：`requirements.txt` 中 `langchain==0.1.12`、`pydantic==2.6.4`、`numpy==1.26.4` 等均为 `==`，构建可复现。
- **部署编排完备**：`compose.yaml` 有 postgres healthcheck（`pg_isready`）、api 依赖 `service_healthy`、api 自身 `/api/ready` healthcheck（`start_period: 60s` 给模型加载留时间）、web 依赖 api healthy。这套编排质量高于多数同规模项目。
- **仓库卫生规范**：`.gitignore` 正确排除 `node_modules/`、`frontend/dist/`、`.venv`、`__pycache__`，且对 `datasets/self_built/*` 用了"先忽略目录再白名单子目录"的正确写法（注释还解释了为什么不能直接忽略目录本身）。回归夹具随内容哈希一起入库，设计合理。
- **注释解释"为什么"**：例如 `domain/agent_roles.py` 中 `FORBIDDEN_KEYS` 的注释明确写出"一旦 GroundingVerifier 读到它们，对抗协议就退化为自我确认"——这是有效注释，而非复述代码。

### 4.2 风险清单

| 级别 | 风险 | 证据 | 后果 |
| --- | --- | --- | --- |
| **高** | 默认生产路径（Postgres）零测试覆盖 | 7 个集成用例被 skip；`order_manager.py:168` 默认 Postgres | 上线后存储层故障无法提前发现 |
| **高** | 持久化策略不一致导致状态错位 | 订单持久 / 黑板·任务·消息易失 | 重启后订单卡死且无报错 |
| **高** | 单 worker 串行，吞吐受限 | `gunicorn.conf.py: workers=1`；`flask_app.py:180 threaded=False` | 实测单订单 2.73–8.19 s → 吞吐约 **0.12–0.37 单/秒**（约 440–1300 单/小时）；上传接口同步阻塞 |
| **中** | LLM 依赖版本陈旧 | `langchain==0.1.12`、`langchain-core==0.1.32`、`langchain-openai==0.0.8`（2024 年初） | 已实际导致 `AIMessage` 缺 `usage_metadata` 属性；无安全补丁；无法使用新模型特性 |
| **中** | 两个模块职责偏重 | `supervisor.py` 568 行、`order_manager.py` 476 行 | 修改成本高、冲突概率大 |
| **中** | 声明式守卫未生效 | `is_readable()` / `RetryBudget` / `assert_no_agent_references()` 无调用方 | 约束"看起来有、实际没有" |
| **低** | 前端未同步改造 | `frontend/src/main.tsx` 巨型 JSX | 维护成本 |
| **低** | `evaluation/` 与主链路耦合弱 | 1,698 行独立于业务代码 | 漂移风险 |

### 4.3 一致性观察

`RISK_CONFIDENCE_THRESHOLD=0.8` / `RISK_MATCH_THRESHOLD=0.8` 在 `.env` 与 `config.py` 中均有默认值。冒烟订单因 `5 个` 非包装倍数（`PACK_QUANTITY_MULTIPLE = 10`）触发 `NON_PACK_QUANTITY` 而落到 `manual_review`——属预期业务行为。

值得肯定的是，`PACK_QUANTITY_MULTIPLE` 定义在 `domain/constants.py:72` 而非埋进规则里，是规范的具名领域常量（`policy_risk.py` 只引用它），没有 magic number 问题。

**唯一的轻微不一致**：它与 `RISK_*` 系列口径不同——`RISK_*` 走环境变量可运行时调整，而包装倍数等业务常量改动需改代码重新部署。对"不同客户包装规格不同"的制造业场景，这类常量迟早需要外置；当前不算缺陷，但属可预见的需求缺口。

---

## 5. 关键问题与改进方向

### 5.1 优先级排序（按"风险 × 修复成本"）

**P0 — 必须修，否则不具备生产可靠性**

1. **统一持久化策略。** 二选一并写进文档与代码：
   - 方案 A（推荐）：黑板 / 任务 / 消息一并落 Postgres，`OrderManager` 的 4 个仓储默认值全部改为持久实现；
   - 方案 B：显式声明为易失，并在启动时清理"有订单、无任务图"的孤儿订单。
   当前"一半持久一半易失"是最坏的组合。
2. **让 CI 跑起 Postgres。** 用 `compose.yaml` 已有的 postgres 服务，注入 `TEST_DATABASE_URL` 与 `RUN_EMBEDDING_INTEGRATION=1`，把那 7 个用例从 skip 变成必过。这是"CI 绿≠可用"的唯一解法。
3. **给 `/api/confirm`、`/trace`、`/tasks` 补端点测试。** 尤其 `/api/confirm`——它是终态写入口，且当前 CAS 逻辑未经 HTTP 层验证。
4. **把 `ReviewAssistant` 接入 Supervisor DAG。** 补齐 ESCALATE 路径，让第二个 LLM 角色真正参与自动流程（同时顺带解决 P0-2 的 `ESCALATE` 未发出问题）。

**P1 — 架构与容量**

5. **端口上移到 `application/ports/`。** 把 4 个仓储 ABC 移出 `infrastructure`，`infrastructure` 实现之；`order_manager` 只依赖抽象。同时消除 3 处对 `faiss_manager` / `document_processing` 的直达依赖。
6. **解除 HTTP 同步阻塞。** 上传接口改为"落库 + 返回任务 ID"，处理走后台；或至少 `workers>1` 并把 LLM 调用移出请求线程。当前 0.12–0.37 单/秒的吞吐是硬上限。
7. **升级 langchain 系列。** 顺带解决 `usage_metadata` 缺失，并可用上新版结构化输出能力。注意升级会牵动 `PydanticOutputParser` 用法，需配套回归。
8. **拆分 `supervisor.py`（568 行）。** 建议按"调度 / 重试与预算 / 消息汇总"三块拆开。

**P2 — 一致性收口**

9. **让声明式守卫真正生效**：`build_slice` 改为调用 `is_readable()`；重试计数统一走 `RetryBudget` 或删除它；V1 改为调用 `assert_no_agent_references()`。原则是**每个约束只有一个实现**。
10. **补齐 §4.3 对比矩阵**：用"关闭对抗协议"的消融配置作为单 Agent 基线，产出可复现的量化对比。当前"多 Agent 更优"缺证据，这是设计文档自己列的验收项。
11. **V3/V4 基线改实测**：把建模值 0.0 换成"同一模型自检"的实测召回率。
12. **业务常量外置**：`domain/constants.py` 中的 `PACK_QUANTITY_MULTIPLE` 等常量已是具名常量（无 magic number 问题），但与 `RISK_*` 不同不可运行时配置。若需支持"不同客户不同包装规格"，应将其纳入配置层。

### 5.2 建议的推进顺序

```
第 1 步  统一持久化 + CI 起 Postgres + 补 3 个端点测试   → 消除"静默错位"风险
第 2 步  ReviewAssistant 接入 DAG + 发 ESCALATE          → 闭合 P0 设计承诺
第 3 步  端口上移 application/ports/                     → 兑现分层承诺
第 4 步  HTTP 异步化 + workers>1                         → 解除吞吐硬上限
第 5 步  升级 langchain + 拆 supervisor                  → 偿还技术债
第 6 步  §4.3 对比矩阵 + V3/V4 实测基线                  → 补齐论证
```

第 1 步与第 2 步互不依赖，可并行。

---

## 6. 附：本次评价的复现命令

```bash
cd /Users/cmh/Documents/AGENT_project

# 全量测试（tests/ 无 __init__.py，unittest discover -s tests 会报不可导入；
# 且 zsh 不对无引号变量分词，故用 xargs）
ls tests/test_*.py | sed 's|/|.|; s|\.py$||' | xargs .venv/bin/python -m unittest

# 架构验证 V1–V7
.venv/bin/python -m unittest tests.test_verification_v1_v7 -v

# 真实 API 冒烟（消耗少量额度）
.venv/bin/python scripts/smoke_real_api.py

# 真实物料索引自检
.venv/bin/python -c "from infrastructure.vector_store import FAISSManager; s=FAISSManager('data/faiss_index'); print(len(s.metadata), s.index.ntotal)"
```

**本次评价的实测基线**：199 例通过 / 7 例跳过；三家真实 API（DeepSeek、阿里云百炼、双模型协作）全部 OK，累计花费远低于 ¥0.5；FAISS 索引 720 条。

---

## 7. 结论

**优点**：架构骨架立得正——六边形分层零违规、`domain` 层绝对纯净、黑板式多智能体有真实的对抗协议与证据隔离，且这些约束被 V1–V7 **变成了可执行断言**而非文档承诺。零 `TODO`/`FIXME`、依赖全量 pin、部署编排完备，工程卫生良好。

**短板**：工程收口不足。**默认生产路径（Postgres）零测试覆盖**、**持久化策略一半持久一半易失导致重启后订单静默卡死**、**单 worker 串行把吞吐锁在 0.12–0.37 单/秒**——这三项叠加意味着"能正确跑通"与"能可靠上线"之间还有明显距离。此外，`ReviewAssistant` 未接入 DAG、`REQUEST`/`ESCALATE` 未发出、§4.3 对比矩阵缺失，使设计承诺未完全闭合。

**总评**：**架构 A-，工程完成度 B，生产就绪度 C。** 按 §5.2 的顺序推进前四步，即可把生产就绪度提到 B+ 以上。
