# 从单 Agent 管道到 Multi-Agent 协作：架构分析与改造设计

> 对象：`/Users/cmh/Documents/AGENT_project` 制造业订单解析系统
> 前置阅读：`PROJECT_HISTORY.md`（项目历史纪录：自定目标、里程碑、风险清单与缺陷修复）

---

## 0. 先摆明一个前提

项目自定目标文档第八章把「为了"多 Agent"增加角色数量或自由对话」明确列入**暂不做**事项。这个约束是对的，不能被绕过。因此本设计的合法性前提是：

> **多 Agent 不是目标，而是达成目标文档三大目标的手段。** 每新增一个 Agent，必须能对应到下面三条中的至少一条，否则不许加。

| 目标文档的三大目标 | 多 Agent 能提供的机制 | 单 Agent 做不到的原因 |
| --- | --- | --- |
| **可靠执行** | 任务 DAG + 并行扇出 + 独立重试/降级 | 单体流水线只能串行推进，一处阻塞全单阻塞 |
| **可靠决策** | 生产者/验证者分离 + 证据化裁决 | 同一模型自检 = 自我确认，无法证伪自己 |
| **可靠评测** | 每个 Agent 独立可归因、可消融 | 单体内部决策不可拆解，无法归因到具体能力 |

**因此本设计拒绝的形态**：Agent 之间自由对话、Agent 数量竞赛、为拆而拆的"每个函数一个 Agent"。

---

## 1. 现状分析

### 1.1 当前"单 Agent"到底单在哪

用代码事实说话（已核对）：

1. **Agent 之间零通信。** 全仓库检索 `from application.agents import ...`，除 `orchestrator` 与 `container` 外，**没有任何 Agent 引用另一个 Agent**。四个"Agent"是四个被编排器顺序调用的函数对象，不是能互相发消息的自治体。

2. **只有一条 LLM 决策链。** 真正调用模型的只有 `ParserAgent`（主链）和 `ReviewAssistantAgent`（旁路）。匹配与风控是纯确定性代码。所以"决策智能"实际只有**一个模型调用点**。

3. **`ReviewAssistantAgent` 是装饰性的。** 它只在订单已进入 `NEEDS_CONFIRMATION` 后由独立端点 `/api/orders/{id}/review-suggestion` 触发，输出一段文本，**不回写任何状态、不参与任何决策**。它是唯一一个形态上像 Agent 的角色，却被排除在主流程之外。

4. **"自纠错"是自我确认，不是独立验证。** `ParserAgent._parse_with_self_correction()` 里，发现问题的人和修问题的人是同一个模型、同一套 Prompt（只多了一段 feedback）。目标文档要求"不靠模型自报置信度决定自动通过"，但自检机制本质上仍是模型给自己打分。

5. **无共享上下文，只有结果搬运。** `OrderProcessingContext` 是快照聚合体，每个阶段对它 `setattr` 一个最终结果（`parsed_order` / `matched_order` / `risk_result` / `final_result`）。中间没有"待裁决主张"、"证据"、"异议"这类协作媒介。

### 1.2 现有工作流程

`OrderProcessingOrchestrator._run_order_pipeline()` 是一条**硬编码线性链**，无分支、无并行、无回退：

```
parser_stage.execute()          # PARSING   ── LLM
  ↓ (success 才继续，否则 set_error → FAILED)
matching_stage.execute()        # MATCHING  ── 规则 + 向量，逐行串行
  ↓
matching_agent.get_reference_prices()
  ↓
risk_stage.execute()            # RISK_CHECKING ── 11 项规则逐项串行
  ↓
_finalize_order()               # if/else 三分类
  ↓
OrderManager.finalize_order()   # 状态机 → COMPLETED / NEEDS_CONFIRMATION
```

`AgentPipelineStage.execute()` 固定四步：状态前置校验 → 执行 → 诊断落库 → 结果落库。**这四步本身设计得不错**（诊断落库是可观测性的基础），问题在于它只能表达"线性阶段"，无法表达"依赖图"。

### 1.3 主要瓶颈

| # | 瓶颈 | 代码定位 | 后果 |
| --- | --- | --- | --- |
| B1 | **异质错误共用一条反馈通道** | `ParserAgent._detect_extraction_problems()` 把"明细为空/名称缺失/行数不一致/名称无法定位/Excel 单元格不符"全部塞进同一个 `problems` 列表，整体回灌重抽 | 幻觉类错误与漏行类错误互相干扰，改一个错一个 |
| B2 | **自检缺乏独立性** | `_parse_with_self_correction()` 同一模型自问自答 | 无法证伪自身幻觉；置信度不可信 |
| B3 | **匹配完全串行** | `MatchingAgent.run()` L323 `for item in parsed_order.items: self._match_item(item)` | N 行明细 = N 次串行 FAISS 检索；明细多的订单线性劣化 |
| B4 | **匹配两条路径是"兜底"而非"并行取证"** | `_match_item()`：先 `_match_by_catalog_key()`，为 `None` 才走 `self.faiss_manager.search()` | 精确路径的"唯一候选"判断**不会**与向量召回交叉验证；向量信息在精确命中时被丢弃 |
| B5 | **能力边界全部塞进单类** | `MatchingAgent` 一个类承担归一化/单位别名/名称兼容索引/目录匹配/向量召回/规格冲突/歧义/参考价共 8 项职责；`RiskControlAgent._validate_item()` 串起 11 项检查 | 无法独立配置、独立测试、独立替换、独立并行 |
| B6 | **无仲裁机制，只有一票否决** | `RiskControlAgent.run()`：`needs_confirmation = any(severity == HIGH)`；`_decide_business_action()`：`if needs_confirmation → MANUAL_REVIEW` | 抽取说 0.95、匹配说规格冲突、风控说价格超政策——三个信号之间没有协商、没有权重、没有证据强度概念 |
| B7 | **风控决策依赖模型自报置信度且可静默失效** | `_check_parsing_confidence()` 读 `item.confidence_score`，该字段 `Optional`，为 `None` 时检查直接跳过 | 目标文档明令反对的做法仍在生效 |
| B8 | **无 agent 级可观测性** | `processing_diagnostics` 只到"阶段"粒度（latency/success/usage） | 无法回答"这个决策是谁提出的、谁反对过、依据是什么" |

### 1.4 根因归纳

瓶颈 B1–B8 收敛到**三个结构性缺失**：

1. **缺失协作媒介** → 没有黑板，只有结果搬运（B1、B6、B8）
2. **缺失独立验证者** → 生产与验证同源（B2、B7）
3. **缺失依赖图** → 线性硬编码导致无法并行、无法动态调度（B3、B4、B5）

这三点正好一一对应目标文档的"可靠决策 / 可靠决策 / 可靠执行"。**改造方向因此是被推导出来的，不是被指定的。**

---

## 2. 目标架构设计

### 2.1 设计原则（Agent 准入三条件）

一个角色只有在满足**至少一条**时才允许存在：

- **P1 独立工具集**：它拥有别人没有的工具（如向量检索、原文定位、参考价查询）。
- **P2 目标冲突**：它与其他角色的优化目标天然对立（如"召回得全" vs "拒得准"）。
- **P3 独立可验证**：它能产出可被第三方复核的证据，而不是自然语言断言。

**推论：把 `MatchingAgent` 拆成 `CatalogMatcher` + `SemanticMatcher` 是合法的**（P1：一个用别名索引，一个用 FAISS）。**把 `_check_quantity` 拆成一个 Agent 是违法的**（无独立工具、无冲突目标、产出不可验证），它应该留在风险 Agent 内部作为一条规则。

### 2.2 角色划分与职责

#### 业务 Agent（10 个）

| # | Agent | 类型 | 独立工具集 | 冲突关系 | 对应瓶颈 |
| --- | --- | --- | --- | --- | --- |
| 1 | **StructureScout**<br>结构侦察 | 侦察 | 文档结构解析、sheet/页/区域探测、扫描页可用性判定 | — | B5、阶段三缺口 |
| 2 | **Extractor**<br>抽取者 | 生产者 | LLM 结构化抽取（可多实例，按区域并行） | ← 被 #3 挑战 | B1、B3 |
| 3 | **GroundingVerifier**<br>溯源验证者 | 验证者 | 原文检索、单元格比对、区间定位 | → 挑战 #2 | B1、B2 |
| 4 | **CatalogMatcher**<br>目录匹配 | 生产者 | 归一化、别名索引、规格精确约束 | ← 被 #6 裁决 | B4、B5 |
| 5 | **SemanticMatcher**<br>语义召回 | 生产者 | FAISS 向量检索 | ← 被 #6 裁决 | B3、B4 |
| 6 | **Disambiguator**<br>消歧裁决者 | 裁决者 | 候选合并、规格冲突判定、候选分差 | → 裁决 #4/#5 | B6 |
| 7 | **PolicyRisk**<br>价格政策风险 | 风控 | 参考价精确查询、价格政策、金额一致性 | ← 被 #9 汇总 | B5 |
| 8 | **ScheduleRisk**<br>交期风险 | 风控 | 时点基准、交期解析与时效判定 | ← 被 #9 汇总 | B5 |
| 9 | **Adjudicator**<br>终裁者 | 终裁 | 证据加权、理由链生成 | → 汇总全部 | B6、B7 |
| 10 | **ReviewAssistant**<br>审核协助 | 协助 | 只读 RAG | — | 从装饰变为参与者 |

#### 编排 Agent（1 个）

| # | Agent | 职责 |
| --- | --- | --- |
| 11 | **Supervisor** | DAG 拆解、任务分配、并行调度、预算控制、重试与降级、超时处置。**唯一有权决定"谁在什么时候跑"的角色** |

#### 权限边界（关键）

- **只有 `Adjudicator` 能改变订单终态**（`COMPLETED` / `NEEDS_CONFIRMATION`）。其他 Agent 只能往黑板上写"主张"和"证据"。
- **只有 `Supervisor` 能创建/取消任务**。Agent 不能自己决定调用别的 Agent。
- **`GroundingVerifier` 与 `Disambiguator` 禁止提出新值**，只能 `INFORM` / `CHALLENGE` / `REFUSE`。这是防止"验证者变成第二个生产者"的关键约束。

#### 最小可用集（如果嫌 11 个太多）

可合并为 **7 个**：`StructureScout`、`Extractor`、`GroundingVerifier`、`Matcher`（#4+#5 合并）、`Disambiguator`、`RiskPanel`（#7+#8 合并为两个内部 specialist）、`Adjudicator`，加 `Supervisor`。
**但 `Extractor` / `GroundingVerifier` / `Adjudicator` 三者不可合并**——它们是多 Agent 的价值所在。

### 2.3 协作与通信机制

#### 通信范式：黑板 + 结构化消息（**不是自由对话**）

选择黑板模式（Blackboard Architecture）的三个理由：

1. 项目已有成熟的 Pydantic 领域模型，天然适合结构化消息。
2. 自由对话不可复现、不可测、token 成本不可控——目标文档明确反对。
3. 黑板是"共享数据结构 + 独立知识源 + 控制组件"的经典多 Agent 范式，`Supervisor` 天然对应其中的控制组件。

#### 消息契约

```python
class Performative(str, Enum):
    REQUEST  = "request"    # 请求执行任务（仅 Supervisor 可发）
    INFORM   = "inform"     # 陈述事实/证据，不带主张
    PROPOSE  = "propose"    # 主张某个值（仅生产者可发）
    CHALLENGE= "challenge"  # 反对，必须附反证（仅验证者/裁决者可发）
    VERDICT  = "verdict"    # 裁决结论（仅 Adjudicator 可发）
    REFUSE   = "refuse"     # 明确拒识/无法判断（允许"不知道"）
    ESCALATE = "escalate"   # 升级（预算耗尽/证据不可调和）

class Evidence(BaseModel):
    kind: str                      # source_span | cell_ref | catalog_row | rule_id | vector_hit
    locator: dict                  # 可复现的定位信息（sheet/行/列 或 page/bbox 或 sku_code）
    value: Any | None
    reproducible: bool             # 第三方能否用 locator 复现这条证据

class AgentMessage(BaseModel):
    message_id: str
    order_id: str
    task_id: str
    sender: str
    recipient: str | None          # None = 广播到黑板
    performative: Performative
    in_reply_to: str | None        # 形成可追溯的对话链
    subject: dict                  # 针对哪个 item/field/region
    payload: dict                  # 领域模型序列化
    evidence: list[Evidence] = []
    cost: dict = {}                # tokens / latency_ms
```

**要点**：`evidence.reproducible` 与 `evidence.locator` 是"真协同"的载体。一条无法复现的证据，`Adjudicator` 有权不予采信。

#### 对抗协议（Adversarial Protocol）

这是把 B2（自我确认）彻底修掉的核心机制：

```
① Extractor      PROPOSE(field=quantity, value=1000, evidence=[cell_ref: sheet1!C5])
② GroundingVerifier 读 source_span + claim（不含 Extractor 的推理过程）
     ├─ 能在 sheet1!C5 找到 "1000" → INFORM(verified)
     └─ 找不到 / 找到的是 "100"  → CHALLENGE(反证=[cell_ref: sheet1!C5 = "100"])
③ Supervisor 收到 CHALLENGE：
     ├─ 重试预算未尽 → 重新 REQUEST Extractor(带反证)
     └─ 预算耗尽     → 标记该字段为 disputed，交 Adjudicator
④ Adjudicator 面对 PROPOSE + CHALLENGE：
     必须显式裁决，并输出理由链；disputed 字段一律不得进入 AUTO_APPROVE
```

**同样的协议用于匹配**：

```
CatalogMatcher  PROPOSE(sku=SKU-001, basis=catalog_alias_spec_exact)
SemanticMatcher PROPOSE(candidates=[SKU-001, SKU-017], top1_score=0.83)
Disambiguator   裁决：
   ├─ 两路一致且规格唯一 → INFORM(accepted=SKU-001)
   ├─ 规格冲突           → REFUSE(reason=规格缺少区分属性)
   └─ 候选分差不足       → REFUSE(reason=存在多个同规格候选)
```

注意：`Disambiguator` 的输入是**结构化候选集**，不是两个 Matcher 的自然语言理由——避免被措辞说服。

#### 通信实现约束

- Agent **不得持有另一个 Agent 的引用**，不得直接调用。所有交互经黑板读写。
- 消息全部落库（`agent_messages` 表），形成可审计轨迹。
- Agent 必须是**近似纯函数**：`(context_slice) → (messages)`。这样才可重试、可重放、可单测。

### 2.4 任务分配与调度

#### 从线性流水线到依赖图

`Supervisor` 把订单处理编译成一张 **DAG**，而不是固定顺序：

```
StructureScout
   ├─→ Extract(region_1) ─┐
   ├─→ Extract(region_2) ─┤
   └─→ Extract(region_n) ─┴─→ GroundingVerify(field: item_i.field_j)  ← 按字段扇出
                                          ↓
                     ┌────────────────────┴────────────────────┐
              CatalogMatch(item_i)                      SemanticMatch(item_i)
                     └────────────────────┬────────────────────┘
                                   Disambiguate(item_i)
                                          ↓
                     ┌────────────────────┴────────────────────┐
              PolicyRisk(item_i)                      ScheduleRisk(item_i)
                     └────────────────────┬────────────────────┘
                                   Adjudicate(order)
                                          ↓
                          ESCALATE? → ReviewAssist → 人工
```

#### 任务模型

```python
class TaskStatus(str, Enum):
    BLOCKED = "blocked"      # 依赖未满足
    READY   = "ready"
    RUNNING = "running"
    DONE    = "done"
    FAILED  = "failed"       # 可重试
    FATAL   = "fatal"        # 不可重试
    CANCELLED = "cancelled"

class Task(BaseModel):
    task_id: str
    order_id: str
    agent: str                 # 目标角色
    slice_key: dict            # 上下文切片标识，如 {"item_index": 3}
    depends_on: list[str] = []
    priority: int = 0
    attempts: int = 0
    max_attempts: int = 2
    deadline_ms: int | None = None
    status: TaskStatus = TaskStatus.BLOCKED
    lease_owner: str | None = None   # 租约，防重复执行
    lease_expires_at: datetime | None = None
```

#### 调度策略

| 维度 | 策略 | 理由 |
| --- | --- | --- |
| **扇出粒度** | 按 `item_index` 扇出匹配与风控；按 `region` 扇出抽取 | 明细行之间无依赖，是最大并行度来源 |
| **优先级** | 阻断性验证（GroundingVerify）> 增强性分析（SemanticMatch）> 协助（ReviewAssist） | 先排除幻觉，再谈召回 |
| **并发上限** | LLM 任务独立限流（如 `asyncio.Semaphore(N)`），规则任务不限 | 成本与限流约束在模型调用上，不在 CPU 规则上 |
| **预算** | 订单级 token 预算 + 任务级超时；超限即 `ESCALATE` | 把"无限反思循环"从架构上排除 |
| **重试** | 仅对可重试错误（模型超时、限流）重试；结构校验失败属不可重试 | 对齐目标文档"模型超时触发有限重试；非法输入不重复重试" |
| **租约** | 任务带 `lease_owner` + `lease_expires_at`，过期可被重新领取 | 复用目标文档阶段二要求的"至少一次执行 + 幂等更新" |
| **降级** | 模型不可用 → 该单转人工，不静默通过 | 宁可多转人工，不可错误放行 |

**与现有代码的衔接**：`OrderManager._update()` 已有的 `expected_updated_at` CAS 机制可以**直接复用为任务级并发控制**，无需引入新中间件。这符合目标文档"先利用现有 PostgreSQL 评估实现一个边界清晰的任务队列，不同时引入多个消息中间件"。

### 2.5 共享状态与上下文管理

#### 黑板三层结构

```
┌─ Layer 3: Control State（控制层）─────────────────────┐
│  任务 DAG 状态 · 已分配任务 · 重试计数 · 预算消耗      │
│  写入者：仅 Supervisor                                │
├─ Layer 2: Claims & Evidence（主张与证据层）★新增★     │
│  待裁决主张 · 证据 · 异议 · 裁决记录 · 理由链          │
│  写入者：所有业务 Agent（只能追加，不能改写他人主张）  │
├─ Layer 1: Order Facts（订单事实层）───────────────────┤
│  源文档 IR · 已裁决的字段值 · 已接受的 SKU · 最终动作  │
│  写入者：仅 Adjudicator（经 Supervisor 落库）          │
└──────────────────────────────────────────────────────┘
```

**Layer 1 对应现有 `OrderProcessingContext`**（可平滑演进）；**Layer 2 是当前完全缺失的层**，也是多 Agent 的核心价值载体。

#### 上下文切片（Context Slice）—— 防止角色污染

Agent **不读整个黑板**，只读被授权的切片。这是防止上下文爆炸和"验证者被生产者说服"的关键：

| Agent | 可读 | **明确不可读** |
| --- | --- | --- |
| StructureScout | 原始文档字节/结构 | 任何业务主张 |
| Extractor | `document_ir[region]` + schema | 其他 region 的抽取结果 |
| GroundingVerifier | `document_ir[region]` + `claim.locator` | **Extractor 的推理过程与置信度** |
| CatalogMatcher | `item` 原始字段 + 物料目录 | 语义召回的候选 |
| SemanticMatcher | `item` 原始字段 + FAISS | 目录匹配的结果 |
| Disambiguator | 两路**结构化候选集** + 规格约束 | 两路的自然语言理由与置信度措辞 |
| PolicyRisk / ScheduleRisk | `matched_item` + 参考价/时点基准 | 抽取置信度（避免被污染） |
| Adjudicator | **全部**（唯一全局视图） | — |

**最后一行是设计的关键**：只有终裁者需要全局视图，其余角色必须在信息上被隔离。**如果 `GroundingVerifier` 能看到 `Extractor` 的推理链，那"独立验证"就是假的**——这一点必须用测试断言固化（见 §4.2 验证 V4）。

#### 持久化

新增三张表（复用现有 PostgreSQL，不引入新中间件）：

```sql
order_blackboard (order_id, layer, key, value JSONB, version, updated_at)
agent_tasks      (task_id, order_id, agent, slice_key JSONB, status,
                  depends_on JSONB, attempts, lease_owner, lease_expires_at, ...)
agent_messages   (message_id, order_id, task_id, sender, recipient,
                  performative, in_reply_to, subject JSONB, payload JSONB,
                  evidence JSONB, cost JSONB, created_at)
```

`order_blackboard` 的 `version` 字段支持乐观并发，与现有 `updated_at` CAS 同一套思路。

---

## 3. 改造步骤与核心模块

### 3.1 新增模块

```
domain/
  messages.py                  # Performative, Evidence, AgentMessage, Claim
  tasks.py                     # Task, TaskStatus, TaskGraph
  agent_roles.py               # 角色枚举 + 能力声明 + 权限边界表
application/
  blackboard/
    blackboard.py              # 三层黑板读写 + 追加语义 + 版本控制
    slices.py                  # 各角色的上下文切片定义（含"不可读"白名单）
  protocol/
    adversarial.py             # PROPOSE/CHALLENGE/VERDICT 协议执行器
    budget.py                  # token/时间预算与熔断
    arbitration.py             # 证据加权与理由链生成
  agents/
    structure_scout.py         # 新增角色
    grounding_verifier.py      # 新增角色（对抗核心）
    disambiguator.py           # 新增角色（对抗核心）
    catalog_matcher.py         # 从 matching_agent.py 拆出
    semantic_matcher.py        # 从 matching_agent.py 拆出
    policy_risk.py             # 从 risk_control_agent.py 拆出
    schedule_risk.py           # 从 risk_control_agent.py 拆出
    adjudicator.py             # 从 orchestrator._decide_business_action 升级
    supervisor.py              # 从 orchestrator 升级为 DAG 调度器
infrastructure/repositories/
  blackboard_repository.py     # 黑板持久化
  task_repository.py           # 任务队列 + 租约（复用 CAS）
  message_repository.py        # 消息审计轨迹
```

### 3.2 需修改模块

| 模块 | 改动 |
| --- | --- |
| `application/orchestrators/order_processing.py` | **降级为薄适配层**，只负责"HTTP 请求 → Supervisor 提交订单"，删除全部业务判定逻辑 |
| `application/agents/parser_agent.py` | 拆为 `extractor.py`（只抽） + `grounding_verifier.py`（只验）；删除 `_parse_with_self_correction` 的自我循环 |
| `application/agents/matching_agent.py` | 拆为 `catalog_matcher.py` + `semantic_matcher.py` + `disambiguator.py`；`get_reference_prices` 下沉到 `policy_risk.py` 并改字典索引 |
| `application/agents/risk_control_agent.py` | 拆为 `policy_risk.py` + `schedule_risk.py`；移除对 `item.confidence_score` 的依赖（改由 GroundingVerifier 的证据通过率替代） |
| `application/agents/review_assistant_agent.py` | 改为响应 `ESCALATE`，输出写入黑板 Layer 2 作为证据 |
| `application/pipeline/stages.py` | 由"线性阶段"升级为"节点执行器"：接受 `Task` → 产出 `AgentMessage`（保留原有的诊断落库能力） |
| `application/services/order_manager.py` | 扩展黑板/任务/消息的持久化与 CAS；状态机增加"任务级"前置条件 |
| `application/container.py` | 装配 Supervisor + 全部 Agent + 黑板仓储 |
| `interfaces/http/flask_app.py` | 新增 `GET /api/orders/{id}/trace`（协作轨迹）、`GET /api/orders/{id}/tasks` |
| `evaluation/` | 新增协作指标（见 §4） |

### 3.3 分步迁移路径（8 步，每步结束系统都可运行）

| 步骤 | 内容 | 完成标志 | 引入角色 |
| --- | --- | --- | --- |
| **S1** | 引入 `AgentMessage` + 三层黑板，把现有 4 个阶段改写为"读切片 → 发消息"。**行为完全不变** | 现有 16 个测试文件全绿 | — |
| **S2** | 拆分匹配：`CatalogMatcher` ∥ `SemanticMatcher` → `Disambiguator` | `datasets/` 上 SKU Top-1 不低于基线 | +3 |
| **S3** | 拆分风控：`PolicyRisk` ∥ `ScheduleRisk` | 风控用例回归全绿 | +2 |
| **S4** | **拆出 `GroundingVerifier`，把自检从 Extractor 移出，启用对抗协议** | 注入幻觉样本的挑战召回率显著 > 0 | +1 |
| **S5** | 引入 `StructureScout` + 多 sheet/区域路由 | 新增多 Sheet 回归样本通过 | +1 |
| **S6** | `Supervisor` 从线性升级为 DAG 调度 + 预算 + 重试 + 租约 | 并发订单互不阻塞；杀进程后可恢复 | 改造 |
| **S7** | `Adjudicator` 替代 `_decide_business_action`，引入证据加权 | 争议订单的裁决理由链可追溯 | +1 |
| **S8** | `ReviewAssistant` 接入黑板，响应 `ESCALATE` | 审核建议可引用具体证据 | 改造 |

**S1 是关键前提**：它证明"把管道换成黑板不会破坏语义"。如果 S1 无法保持测试全绿，说明抽象选错了，应立即停止而不是继续加 Agent。

**S4 是关键分水岭**：只有它落地，"多 Agent"才从架构重构变成能力提升。

### 3.4 关键契约（示意代码）

```python
# application/agents/base_agent.py（改造后）
class CollaborativeAgent(ABC):
    role: AgentRole
    readable: frozenset[str]     # 允许读取的黑板切片键
    forbidden: frozenset[str]    # 显式禁止读取（防止角色污染）

    def __init__(self, blackboard: Blackboard, budget: Budget): ...

    @abstractmethod
    def handle(self, task: Task) -> list[AgentMessage]:
        """纯函数语义：(上下文切片) -> (消息)。禁止调用其他 Agent。"""

    def read_slice(self, task: Task) -> ContextSlice:
        return self.blackboard.slice_for(self.role, task.slice_key)
```

```python
# application/blackboard/blackboard.py（追加语义，防止改写他人主张）
class Blackboard:
    def append_claim(self, msg: AgentMessage) -> None:
        """只允许追加。同一 subject 的多条主张共存，由 Adjudicator 裁决。"""

    def append_evidence(self, msg: AgentMessage) -> None:
        """证据不可删除；被推翻时追加一条 challenge 而非覆盖。"""

    def facts(self) -> OrderFacts:
        """只有 Adjudicator 裁决后，主张才晋升为事实。"""
```

---

## 4. 如何验证是"真协同"而非表面拆分

### 4.1 反模式判据（出现任一条即为表面拆分）

| 反模式 | 检测方式 |
| --- | --- |
| A1 Agent 之间直接函数调用 | AST 扫描：`application/agents/*.py` 中不得出现跨 Agent import 或属性持有 |
| A2 执行顺序被硬编码 | 打乱就绪任务顺序，结果应不变 |
| A3 删掉某 Agent 系统照常工作 | 反事实归因：禁用后终态无变化 → 该 Agent 是装饰性的 |
| A4 只传最终结果，不传证据/异议 | 检查 `agent_messages` 中 `evidence` 是否为空、`CHALLENGE` 是否恒为 0 |
| A5 验证者能看到生产者的推理过程 | 断言 `GroundingVerifier.forbidden` 包含 `extractor.rationale` |
| A6 无法回答"谁影响了谁" | 给定终态，必须能列出完整因果链 |

### 4.2 七类可执行验证

**V1 — 通信拓扑断言（自动化单测）**
```
扫描 application/agents/ 下所有模块，断言不存在跨 Agent 引用；
断言 CollaborativeAgent 子类不持有其他 Agent 实例。
```
这是最便宜、最先该写的测试。

**V2 — 调度顺序无关性（自动化单测）**
```
对同一订单，用固定模型替身，随机打乱就绪任务执行顺序 N=20 次；
断言最终 AgentMessage 集合与终态完全一致。
```
证明它真的是依赖驱动，而不是把 for 循环换了个名字。

**V3 — 对抗有效性：幻觉挑战召回率**
```
构造对抗集：把 Extractor 输出中的字段值替换为原文不存在的值（保持格式合法）。
指标：GroundingVerifier 对这些字段发出 CHALLENGE 的比例。
基线：当前自检机制（同一模型）在该集合上的召回率。
```
**若多 Agent 版本的召回率不高于当前基线，说明拆了个寂寞。**

**V4 — 独立性消融**
```
对照组 A：GroundingVerifier 只能读 source_span + claim.locator
对照组 B：额外把 Extractor 的推理过程与置信度也喂给它
比较两组的 CHALLENGE 率与误判率。
若 B 组挑战率显著下降 → 证明"上下文隔离"是有效的，独立验证不是摆设。
```
这条是**最有说服力的设计验证**，直接回答"为什么必须是两个 Agent 而不是一个"。

**V5 — 反事实贡献归因**
```
对每笔订单，逐个禁用非终裁 Agent，测量终态变化率与指标变化。
产出贡献矩阵：哪个 Agent 对哪个指标负责。
任何一行全为 0 的 Agent，应从设计中删除。
```
这既是验证，也是**防止架构腐化**的长期机制。

**V6 — 并行收益验证**
```
固定模型替身（消除模型抖动），对比线性流水线 vs DAG 的端到端延迟，
按明细行数分组统计（1 行 / 5 行 / 20 行）。
若并行版本延迟不随行数增长而摊薄，说明扇出没生效。
```

**V7 — 故障注入与恢复**
```
① 执行中强制杀掉某个 Agent 的 worker → Supervisor 应重试或降级，订单不得卡在中间态
② 模型超时 → 有限重试；结构校验失败 → 不重试
③ 预算耗尽 → ESCALATE 转人工，而非静默通过
④ 并发人工确认 → 只允许一次有效状态转换（复用现有 CAS，应有回归测试）
```

### 4.3 端到端对比（复用现有评测基础设施）

**好消息：验证基础设施已经存在。** `EvaluationAccumulator` 已具备所需指标，无需新造：

| 目标文档要求的口径 | 现有指标字段 |
| --- | --- |
| 字段准确率 | `order_level_accuracy` / `item_level_accuracy` |
| 明细召回率 | `item_count_exact_match` |
| SKU Top-1 准确率 | `sku_top1_accuracy` |
| 人工审核召回率 | `manual_review_recall` |
| 错误自动放行率 | `error_auto_release_rate` |
| 自动处理覆盖率 | `auto_handle_coverage` |
| 单订单耗时 / token | `avg_latency_ms` / `attempts.total_usage` |

**对比矩阵**（同一评测集、同一固定评测时点、同一物料索引指纹）：

| 版本 | 字段准确率 | SKU Top-1 | 人工审核召回 | 错误自动放行率 | 自动覆盖率 | 延迟 | token |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 单 Agent 基线 | 待测 | 待测 | 待测 | 待测 | 待测 | 待测 | 待测 |
| Multi-Agent | 待测 | 待测 | 待测 | 待测 | 待测 | 待测 | 待测 |

`build_run_identity()` 的运行身份指纹机制保证两组结果**代码/提示词/模型/索引/数据集可追溯**，不会混算。

### 4.4 验收标准与止损线

**验收（必须全部满足）**
1. V1 拓扑断言通过：Agent 之间零直接调用。
2. V2 顺序无关性通过。
3. V3 幻觉挑战召回率**严格高于**单 Agent 自检基线。
4. V4 消融显示上下文隔离对挑战率有显著正贡献。
5. V5 每个 Agent 的贡献非零，或已从设计删除。
6. V7 故障注入四项全部通过。
7. 端到端对比中，**错误自动放行率不高于基线**（安全不退化）。

**止损线（触发即回退）**
- 若 V3 挑战召回率不高于基线 → 说明独立验证没有价值，回退到 S1（黑板化）并停止加 Agent。
- 若 V5 显示超过半数 Agent 贡献为零 → 架构过度设计，收敛到最小可用集。
- 若延迟增长超过 2× 而错误自动放行率没有改善 → 多 Agent 是净亏损，回退。
- 若 token 成本增长超过 3× 而质量指标无显著提升 → 同上。

**最后一条，也是最诚实的一条**：
> 如果 Multi-Agent 版本在**所有维度**都不优于单 Agent 版本，那么正确答案就是**不上 Multi-Agent**，并把这次消融实验本身作为成果汇报——"我验证过它不值得"，在面试中比"我加了很多 Agent"更有说服力。

---

## 5. 风险与取舍

| 风险 | 表现 | 缓解 |
| --- | --- | --- |
| **成本翻倍** | 每单 LLM 调用从 1–2 次涨到 3–5 次 | 只有 Extractor 与 ReviewAssistant 调 LLM；验证与裁决全走确定性规则 |
| **延迟翻倍** | 串行验证引入额外往返 | 按 item/region 扇出并行；验证走规则不走模型 |
| **错误累积** | 上游错误被下游继承放大 | `Adjudicator` 必须显式处理 `disputed` 字段，不得放行 |
| **调试困难** | 出错不知在哪个 Agent | `agent_messages` 全量落库 + `/api/orders/{id}/trace` |
| **架构腐化** | 半年后 Agent 之间开始互相调用 | V1 拓扑断言作为 CI 门禁，长期守护 |
| **与目标文档冲突** | 被质疑"为多 Agent 而多 Agent" | 用 §0 的三条对应关系与 §4.3 的对比矩阵回应 |

### 落地建议

**先做 S1 + S2 + S4，即：黑板化 → 匹配拆分 → 独立验证者。** 这三步就能同时兑现目标文档的"可靠决策"与部分"可靠执行"，并且 V3/V4 两个实验足以支撑面试讲解。`StructureScout`（S5）与 DAG 调度（S6）建议紧随其后，因为它们顺带解决阶段二的异步化与阶段三的多 Sheet 缺口——**一份工作量，三个目标**。
