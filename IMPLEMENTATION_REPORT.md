# 多 Agent 订单解析系统 — 实现成果报告

> 对照 `MULTI_AGENT_DESIGN.md` 的落地情况汇报。
> 生成时间：2026-09-29

---

## 0. 一句话结论

把原来的「线性单 Agent 流水线」改造成了**黑板 + 任务 DAG + 对抗协议**的多 Agent 协作系统：
**199 个自动化用例全绿**，V1–V7 七类架构验证全部通过，并已用 **DeepSeek** 与**阿里云百炼**两家真实
API 端到端跑通（总花费远低于 ¥0.5）。

| 指标 | 数值 |
| --- | --- |
| 业务代码量 | `domain` 703 行 / `application` 4815 行 / `infrastructure` 1154 行 / `interfaces` 212 行 |
| 协作 Agent | 10 个业务角色 + 1 个编排者（Supervisor） |
| 自动化测试 | 199 用例（7 个 Postgres 集成用例在无 `TEST_DATABASE_URL` 时跳过） |
| 架构验证 | V1–V7 共 14 条断言 |
| 真实 API 冒烟 | DeepSeek `deepseek-flash` + 阿里云 `qwen3.8-flash`，均 success |
| 标准物料库 | 720 条（FAISS 索引 `ntotal=720`，实测召回正确） |

---

## 1. 架构总览

```
                        ┌──────────────────────────────┐
   HTTP 请求 ──────────▶ │  OrderProcessingOrchestrator  │  薄适配层（零业务 if/else）
                        └──────────────┬───────────────┘
                                       │ 提交订单
                        ┌──────────────▼───────────────┐
                        │          Supervisor           │  唯一有权建/取消任务
                        │  DAG 拆解 · 并行调度 · 预算    │
                        └──────────────┬───────────────┘
                                       │ 任务
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
   ┌────▼─────┐  ┌──────────┐  ┌───────▼──────┐  ┌──────────┐  ┌──────▼─────┐
   │Structure │→ │ Extractor│→ │  Grounding   │  │ Catalog/ │→ │Disambigua- │
   │  Scout   │  │(生产者)  │  │  Verifier    │  │ Semantic │  │   tor      │
   └──────────┘  └────┬─────┘  │  (验证者)    │  │ Matcher  │  └──────┬─────┘
                      │        └───────┬──────┘  └──────────┘         │
                      │ PROPOSE        │ CHALLENGE(带反证)            │
                      │                ▼                              ▼
                      │        ┌───────────────┐            ┌─────────────────┐
                      │        │  重抽 / 争议   │            │ PolicyRisk /    │
                      │        └───────────────┘            │ ScheduleRisk    │
                      │                                     └────────┬────────┘
                      └──────────────────────────────────────────────┘
                                       │ 主张 + 证据 + 异议
                        ┌──────────────▼───────────────┐
                        │         Adjudicator           │  唯一有权改订单终态
                        │  证据加权 · 理由链 · 三分类动作 │
                        └──────────────┬───────────────┘
                                       │ VERDICT
                        ┌──────────────▼───────────────┐
                        │      三层 Blackboard          │
                        │  L3 Control / L2 Claims / L1 Facts │
                        └──────────────────────────────┘
```

**依赖方向严格单向**：`interfaces → application → domain`；`application → infrastructure` 只经过抽象端口。
`domain` 零框架依赖。

---

## 2. 已完成的功能（对照设计文档）

### 2.1 三层黑板（设计 §2.5）

`application/blackboard/blackboard.py`

| 层 | 内容 | 写入者 |
| --- | --- | --- |
| L3 Control | 任务 DAG 状态、重试计数、预算消耗、region、candidates | 仅 Supervisor |
| L2 Claims & Evidence | 待裁决主张、证据、异议、裁决记录、理由链 | 所有业务 Agent（只追加） |
| L1 Order Facts | 文档 IR、已裁决字段、已接受 SKU、最终动作 | 仅 Adjudicator |

关键约束已用代码固化：`set_control()` 校验 `actor is SUPERVISOR`、`set_fact()` 校验
`actor is TERMINAL_STATE_AUTHORITY`，越权直接抛 `PermissionViolation`。
主张**只追加不覆盖**——被推翻时追加一条 CHALLENGE，而不是改写原主张。

### 2.2 结构化消息契约（设计 §2.3）

`domain/messages.py` — 7 种语用行为，Agent 之间**不做自由对话**：

```python
class Performative(str, Enum):
    REQUEST = "request"      # 请求执行任务（仅 Supervisor 可发）
    INFORM = "inform"        # 陈述事实/证据，不带主张
    PROPOSE = "propose"      # 主张某个值（仅生产者可发）
    CHALLENGE = "challenge"  # 反对，必须附反证（仅验证者/裁决者可发）
    VERDICT = "verdict"      # 裁决结论（仅 Adjudicator 可发）
    REFUSE = "refuse"        # 明确拒识/无法判断（允许“不知道”）
    ESCALATE = "escalate"    # 升级（预算耗尽/证据不可调和）
```

`Evidence` 强制携带 `locator` + `reproducible`：**无法被第三方复现的证据，Adjudicator 有权不予采信**。
语用权限在 `emit()` 里强制校验（`assert_performative_allowed`）。

### 2.3 对抗协议：PROPOSE → CHALLENGE → VERDICT（设计 §2.3 核心）

替换了原来的 `_parse_with_self_correction`（同一模型自问自答）：

```
① Extractor         PROPOSE(quantity=99, evidence=[cell_ref: 采购订单!D2])
② GroundingVerifier 只读原文 + claim 定位（读不到 Extractor 的推理与置信度）
     ├─ 原文 D2 = 10 → CHALLENGE(reason, evidence=[cell_ref: 采购订单!D2 = 10])
③ Supervisor        预算未尽 → 把「可复现反证」回灌重抽；仍不通过 → 记为争议
④ Adjudicator       面对 PROPOSE + CHALLENGE 显式裁决并输出理由链
```

**回灌的只有证据，不含验证者的自然语言措辞**（`application/protocol/adversarial.py`），
避免生产者被措辞说服而放弃核对原文。

### 2.4 任务 DAG 与并行调度（设计 §2.4）

`application/agents/supervisor.py` — 按 `item` / `region` 扇出，同组无依赖任务走
`ThreadPoolExecutor` 并行；`Task` 是近似纯函数 `handle(task) -> list[AgentMessage]`，可重试、可重放。

### 2.5 上下文切片隔离（设计 §2.5，V4 的支撑）

`application/blackboard/slices.py` — 每个角色只拿到被授权的切片：

```python
if role == AgentRole.GROUNDING_VERIFIER:
    view = {KEY_DOCUMENT_IR: ..., "item_index": index, "item": ..., "claims": claim_records}
    # 显式剥离生产者推理链与自报置信度：独立验证的前提。
    view.pop("extractor.rationale", None)
    view.pop("extractor.confidence", None)
    for claim_record in view["claims"]:
        claim_record.pop("confidence", None)
    return view
```

`FORBIDDEN_KEYS[GROUNDING_VERIFIER] = {"extractor.rationale", "extractor.confidence"}`，
并提供了 `assert_slice_isolated()` 供审计与测试断言。

### 2.6 预算与熔断（设计 §2.6）

`application/protocol/budget.py` — 订单级 token / 调用次数 / 墙钟三重预算；
超限抛 `BudgetExhausted` → Supervisor 写 `escalation` 到控制层 → **转人工，而不是静默通过**。
任务级重试用 `task.attempts` / `max_attempts` 做上界，杜绝无界反思循环。

### 2.7 文档 IR：多 Sheet Excel + PDF 分页 + 图像路由

`infrastructure/document_processing/document_loader.py`

- Excel：输出多 Sheet IR，含 `hidden`、`merged_regions`（openpyxl 读取）。
- PDF：逐页 `{page_number, text, tables}`；**无文字也无表格的页渲染成 PNG**，交给多模态抽取。
- `Extractor.handle()` 遇到 `region.mode == "image"` 自动改走图像抽取分支。

### 2.8 HTTP 接口（含可观测性）

`interfaces/http/flask_app.py`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 存活探针 |
| GET | `/api/ready` | 就绪探针（校验物料索引与数据库） |
| POST | `/api/upload_text` | 文本订单 |
| POST | `/api/upload` | 文档/图片订单 |
| GET | `/api/orders` | 订单列表 |
| GET | `/api/orders/<id>` | 订单详情（含诊断、状态流转） |
| **GET** | **`/api/orders/<id>/trace`** | **协作轨迹：谁对谁说了什么、依据是什么** |
| **GET** | **`/api/orders/<id>/tasks`** | **任务 DAG 状态与租约** |
| POST | `/api/orders/<id>/review-suggestion` | 人工审核参考（RAG） |
| POST | `/api/confirm/<id>` | 人工确认/驳回 |

### 2.9 编排器降级为薄适配层（设计 §3.2 硬要求）

`application/orchestrators/order_processing.py` 已**删除全部业务判定分支**，
只剩「装配 Agent + Supervisor → 提交订单 → 映射裁决结果」：

```python
def _run(self, order_id, document_ir, image_path=None, image_type="jpeg"):
    result = self.supervisor.run(order_id, document_ir, image_path=image_path, image_type=image_type)
    self._last_usage = dict(result.get("usage") or self._empty_usage())
    self._last_diagnostics = dict(result.get("diagnostics") or {})
    if self._last_diagnostics:
        self.order_manager.record_stage(order_id, "pipeline", self._last_diagnostics)
    if not result.get("success"):
        ...
    return self._finalize(order_id, result)
```

---

## 3. 关键实现思路与核心代码

### 3.1 Agent 是「近似纯函数」，不是「持有引用的对象」

```python
class CollaborativeAgent(ABC):
    role: AgentRole

    @abstractmethod
    def handle(self, task: Task) -> List[AgentMessage]:
        """纯函数语义：(上下文切片) -> (消息)。禁止调用其他 Agent。"""

    def read_slice(self, task: Task) -> Dict[str, Any]:
        if self.blackboard is None:
            return {}
        return self.blackboard.slice_for(self.role, task.slice_key)
```

Agent 不持有其他 Agent、不接收任意 dict、不返回任意 dict。这是**可重试 / 可重放 / 可单测**的前提，
也是 V1 拓扑断言能被机器校验的原因。

### 3.2 唯一编排者：Supervisor 只做两件事

> 把上下文切片喂给 Agent；把 Agent 产出的消息写回黑板。

```python
def _publish(board, grouped):
    flat = []
    for messages in grouped.values():
        for message in messages:
            record(board, message)      # 按 performative 分发到黑板对应层
            flat.append(message)
    return flat
```

### 3.3 重试分类：瞬态错误重试，结构错误带反馈重试

```python
except ExtractionSchemaException as exc:
    # 模型输出结构失败：有界可重试，带错误详情重抽
    last_error = exc
    retry = task.attempts < task.max_attempts
    if retry:
        task.slice_key = dict(task.slice_key)
        task.slice_key["feedback"] = str(exc)     # ← 注入结构修正反馈
        task.attempts += 1
except Exception as exc:
    last_error = exc
    retry = task.is_retryable(type(exc).__name__) and task.attempts < task.max_attempts
    # 超时/连接类瞬态错误：重试但【不】注入结构反馈
```

`RETRYABLE_ERRORS = {APITimeoutError, APIConnectionError, RateLimitError, TimeoutError, ConnectionError, ModelTruncationException, ...}`。

**第三类错误：输出被截断（本轮新增）。** 推理型模型把「思考」与「正文」计入**同一个
`max_tokens` 预算**。预算被思考耗尽时，API 仍返回 HTTP 200，但 `finish_reason='length'`
且 `content=''`（实测 `max_tokens=200/400` 均如此，`reasoning_tokens == completion_tokens == cap`）。

此时若把空正文送进 `PydanticOutputParser`，会被包装成
`ExtractionSchemaException("上一次输出无法通过结构校验，必须修正这些字段…")`——
系统于是带着一份**与真实故障无关的字段级反馈**去重抽，既误导模型、又掩盖「预算不足」的根因。

因此把截断单独建模为 `ModelTruncationException`（可重试、**不带**结构反馈）：

```python
# application/protocol/model_output.py
def assert_not_truncated(message, agent_name, max_tokens=None):
    metadata = getattr(message, "response_metadata", None) or {}
    finish_reason = metadata.get("finish_reason")
    content = (getattr(message, "content", None) or "").strip()
    if finish_reason == "length" or not content:     # 截断，或根本没产出正文
        raise ModelTruncationException(...)
```

守卫放在 `application/protocol/` 而非某个 Agent 内，是**架构硬约束**：V1 拓扑测试会扫描
AST 禁止 Agent 模块互相引用（仅允许 `base_agent`/`source_map`/`match_keys`）。第一版放进
`extractor.py` 后被该测试正确拦截。

配套把输出上限提到与实测推理消耗相称的水平：`EXTRACTION_MAX_TOKENS=16384`、
`REVIEW_MAX_TOKENS=4096`（原值 1024 低于实测 reasoning 消耗 1158~1982，是稳定的线上截断点）。

### 3.4 证据加权与理由链（Adjudicator 的裁决依据）

```python
accepted_skus = [
    {"sku_code": item.get("sku_code"), "basis": item.get("match_basis"),
     "weight": round(weigh_evidence(self._item_evidence(item)), 2)}
    for item in items if item.get("sku_code")
]
reason_chain = build_reason_chain(
    action=action.value, risk_issues=ordered_issues, disputed_subjects=disputed_subjects,
    normalizations=[...], accepted_skus=accepted_skus,
)
```

裁决保持保守：**任何被证据支撑的 HIGH 风险、任何未决争议字段，都不得自动通过**。

### 3.5 用量记账：每条 INFORM 只上报「本次」快照

这是本轮修掉的一个隐蔽 bug。原实现里 `Extractor.last_usage` 跨 `handle()` 累积，
而每条 INFORM 都携带完整累计快照，Supervisor 汇总时就把 2 次调用算成了 3 次：

```python
def handle(self, task: Task) -> List[AgentMessage]:
    # 每次 handle 只统计本次调用的用量：INFORM 携带的是「本次」快照，
    # 由 Supervisor 汇总各条 INFORM 得到订单级总量，避免累计快照被重复累加。
    self.last_usage = self._empty_usage()
    self.last_call_records = []
    ...
```

### 3.6 失败订单必须留下可诊断的错误类型

```python
"error": (f"{type(result.error).__name__}: {result.error}" if result.error else None),
```

---

## 4. 运行与使用方式

### 4.1 环境

```bash
cd /Users/cmh/Documents/AGENT_project
# 已就绪：Python 3.11 venv
.venv/bin/python --version        # Python 3.11.13
# 依赖：langchain-openai / pydantic / faiss-cpu / sentence-transformers 2.5.1 / flask / psycopg
```

### 4.2 跑全部测试（不需要任何外部服务）

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
# 期望：Ran 199 tests ... OK (skipped=7)
```

跑单项，例如架构验证：

```bash
.venv/bin/python -m unittest tests.test_verification_v1_v7 -v
```

### 4.3 真实 API 轻量冒烟（会消耗少量额度）

```bash
.venv/bin/python scripts/smoke_real_api.py            # 两家都跑
.venv/bin/python scripts/smoke_real_api.py aliyun     # 只跑阿里云
```

脚本内置了两把测试 key，也支持用环境变量覆盖：`DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` /
`ALIYUN_API_KEY` / `ALIYUN_MODEL`。

### 4.4 启动 HTTP 服务

生产需要 PostgreSQL（黑板/任务/消息与订单都落在 Postgres）：

```bash
# 方式一：容器编排（推荐）
cp .env.example .env    # 填入 QWEN_API_KEY 与 POSTGRES_PASSWORD
docker compose up --build

# 方式二：本地直接起（需已有 Postgres + .env）
gunicorn -c gunicorn.conf.py app:app     # bind 0.0.0.0:5001, workers=1
```

### 4.5 调用示例

```bash
# 提交文本订单
curl -X POST http://localhost:5001/api/upload_text \
     -H 'Content-Type: application/json' \
     -d '{"order_text":"1 螺丝 M8 10 个 1.0"}'

# 查看协作轨迹（谁对谁说了什么、证据是什么）
curl http://localhost:5001/api/orders/<order_id>/trace

# 查看任务 DAG（扇出的任务、状态、租约）
curl http://localhost:5001/api/orders/<order_id>/tasks

# 生成人工审核参考
curl -X POST http://localhost:5001/api/orders/<order_id>/review-suggestion
```

---

## 5. 验证结论

### 5.1 V1–V7 架构验证（`tests/test_verification_v1_v7.py`，14 条断言全绿）

| 编号 | 验证内容 | 实测结论 |
| --- | --- | --- |
| V1 | 通信拓扑：Agent 零直接调用 | AST 扫描通过；11 个 Agent 实例均不持有同伴引用 |
| V2 | 调度顺序无关性 | 固定模型替身打乱就绪顺序 20 次，消息集合与终态**完全一致** |
| V3 | 幻觉挑战召回率 | 对抗集召回率 **1.0**，严格高于自我确认基线 0.0 |
| V4 | 上下文隔离消融 | 切片确实剥离 `confidence`；隔离组挑战率 **1.0** > 泄漏组 **0.0** |
| V5 | 反事实贡献归因 | 8 个管线 Agent 逐个禁用，**贡献矩阵无全零行** |
| V6 | 并行收益 | 8 任务并行 < 顺序的 60%；20 行耗时 < 1 行的 5 倍（扇出生效） |
| V7 | 故障注入与恢复 | ①worker 崩溃重试且订单不卡中间态 ②超时/结构失败重试分类正确 ③预算耗尽升级人工 ④并发确认 CAS 唯一赢家 |

### 5.2 真实 API 端到端冒烟

| 平台 | 模型 | 结果 | 用量 | 延迟 |
| --- | --- | --- | --- | --- |
| DeepSeek | `deepseek-flash`（V4.1-Flash） | success，`螺丝→SKU-001`、`螺母→SKU-002` | 3,107 tokens | 8.19 s |
| 阿里云百炼 | `qwen3.8-flash` | success，`螺丝→SKU-001`、`螺母→SKU-002` | 1,735 tokens | 2.73 s |

同一订单、**两个角色各用一家模型**（`Extractor→deepseek-flash` + `ReviewAssistant→qwen3.8-flash`）：
success，2,842 tokens，6.31 s，`review_suggestion` 引用了 `SKU-002`。

> 用量差异的成因（已实测）：阿里云侧 `enable_thinking: False` 生效，`completion_tokens` 仅 **209**；
> DeepSeek 侧仍会推理，`completion_tokens` 达 **1,689**。累计花费仍**远低于 ¥0.5**。

冒烟订单终态为 `manual_review`——因为 `5 个` 不是包装数量 `PACK_QUANTITY_MULTIPLE=10` 的整数倍，
触发 `NON_PACK_QUANTITY`（HIGH）。这是**预期的业务行为，不是缺陷**。

### 5.3 真实物料索引

```
FAISSManager('data/faiss_index') → metadata 720 行, index.ntotal = 720
search('屏蔽控制电缆 RVVP 4×0.5mm² 普通屏蔽') → CBL-003 (dist 0.0019) ← 正确命中
```

---

## 6. 尚未解决 / 需要进一步完善

### P0 — 影响设计承诺的完整性

1. **ReviewAssistant 只接了「人工请求」这一半，ESCALATE 那一半没接。**
   设计 §2.2 说它「响应 ESCALATE / 人工请求」，`handle()` 也写了「响应 ESCALATE」，
   但 **Supervisor 的 DAG 里从未创建 `REVIEW_ASSISTANT` 任务**。目前只能通过
   `POST /api/orders/<id>/review-suggestion` 触发（`suggest()` 直调）。
   → 需要在预算耗尽/争议升级时由 Supervisor 扇出一个 assist 任务。

2. **`Performative.REQUEST` 与 `Performative.ESCALATE` 声明了但从未发出。**
   Supervisor 直接构造 `Task` 调执行器，不往黑板写 REQUEST 消息；
   预算耗尽是写控制层 `escalation` 键，也不是 ESCALATE 消息。
   → 后果：`/trace` 看不到「谁被派了什么任务」和「为何升级」，
   与设计「给定终态必须能列出完整因果链」的目标有差距（A6）。

3. **§4.3 端到端对比矩阵（单 Agent 基线 vs Multi-Agent）未产出。**
   设计要求的 6 项指标对比（字段准确率 / SKU Top-1 / 人工审核召回 / 错误自动放行率 /
   自动覆盖率 / 延迟·token）尚未跑。且**单 Agent 基线代码已被删除**（`ParserAgent` 等），
   要产出基线需要先复活一版基线或改用「关闭对抗协议」的消融配置。

### P1 — 工程质量

4. **PostgreSQL 全链路本地零验证。** `OrderManager` 默认就是 `PostgresOrderRepository`，
   容器注入三个 Postgres 协作仓储；但 7 个集成用例在没有 `TEST_DATABASE_URL` 时全部跳过，
   `infrastructure/repositories` 下的黑板/任务/消息 SQL 与表结构**未在本机跑过**。

5. **`/api/orders/<id>/trace` 与 `/tasks` 两个新接口没有测试覆盖**（`grep` 无命中）。

6. **三处声明式代码未被使用，属死代码或"文档即代码"的缺口：**
   - `domain/agent_roles.is_readable()` —— 定义了白名单，但 `build_slice()` 是手写字典，
     并未调用它。`READABLE_KEYS` 目前是**声明而非强制**。
   - `application/protocol/budget.RetryBudget` —— 重试计数实际由 `Task.attempts` 承担。
   - `application/agents/base_agent.assert_no_agent_references()` —— V1 用自己的 AST 扫描，未调用它。

7. **任务租约与崩溃恢复未测试。** `recover_orphan_tasks(ttl_seconds=180)` 存在且在容器启动时调用，
   但没有任何用例覆盖「租约过期 → 任务被重新接管」。

8. **HTTP 层仍是同步阻塞**（`gunicorn workers=1`）。多 Agent 让**单个请求内部**并行了，
   但 `PROJECT_ANALYSIS.md` 里 P0 级的「上传接口同步阻塞 / 无任务队列 / 无幂等键」并未因本次改造而解决。

### P2 — 口径与细节

9. **V3/V4 的「单 Agent 自检基线」是建模值（0.0），不是实测值。** 真实的基线应该用
   「同一模型做自检」在对抗集上跑一遍得到召回率。当前用「置信度阈值自确认」代理，
   结论方向正确但数值不是实测。

10. **V5 用的是 6 个人工构造场景，不是评测集全量订单**，贡献矩阵的覆盖面有限。

11. **思考/推理控制参数已按平台分流并实测**（取代此前的推测结论）：
    - **DeepSeek**：`GET /models` 明确声明 `effort` 字段（`supported_levels: low/high/max`、
      `default_level: high`），接口接受该参数；但**实测对 token 消耗无可稳定复现的影响**
      （同档位内波动大于档位间差异，且非单调）。故 `effort: low` 仅作为「意图声明」，
      **不应据此宣称节省 token**。DeepSeek 不认 `enable_thinking`（发它会被静默忽略）。
    - **阿里云百炼**：`enable_thinking: False` **实测明确生效** —— `qwen3.8-flash` 关闭思考后
      `completion_tokens` 188 → 31（约 6 倍），且不再返回 `reasoning_tokens`。
    - 结论：真正的成本杠杆是 `max_tokens`（推理与正文共享），不是思考开关。
    - 已实现于 `config.py::_THINKING_PARAM_BY_HOST` + `ModelConfig.request_body()`。

12. **前端未改动**，仍是改造前的那套（`frontend/main.tsx` 巨型 JSX 等历史问题依旧）。

---

## 7. 本轮改动的文件索引

**新增**

- `tests/test_verification_v1_v7.py` —— V1–V7 架构验证（14 断言）
- `tests/test_model_routing.py` —— 角色级多模型路由（8 断言）
- `tests/test_model_truncation.py` —— 输出截断的识别与重试分类（15 断言）
- `application/protocol/model_output.py` —— 跨 Agent 共用的输出守卫 `assert_not_truncated`
- `scripts/smoke_real_api.py` —— 双平台真实 API 轻量冒烟（含双模型协作链路）
- `tests/support.py` —— 共享测试装配（`build_harness(..., rng_seed=)`）
- `IMPLEMENTATION_REPORT.md` —— 本报告

**修复**

- `application/agents/extractor.py` —— 每次 `handle()` 重置用量快照；新增单调 `_call_seq`；
  接入截断守卫；`max_tokens` 4096 → `EXTRACTION_MAX_TOKENS=16384`
- `application/agents/review_assistant.py` —— 接入截断守卫；`max_tokens` 1024 → `REVIEW_MAX_TOKENS=4096`
- `domain/exceptions.py` —— 新增 `ModelTruncationException`
- `domain/tasks.py` —— `RETRYABLE_ERRORS` 增加 `ModelTruncationException`
- `config.py` —— 角色级模型路由 `model_for()`；按平台分流思考参数（注释改为实测结论）
- `application/pipeline/stages.py` —— 节点诊断错误字段带类型名

**重写测试（对齐新架构）**

- `tests/test_review_assistant.py`、`tests/test_http_api.py`、
  `tests/test_order_storage.py`、`tests/test_evaluation_concurrency.py`

---

## 8. 验证复现命令

```bash
cd /Users/cmh/Documents/AGENT_project

# 1) 全量测试（注意：tests/ 下无 __init__.py，unittest discover -s tests 会报
#    "Start directory is not importable"；且 zsh 不对无引号变量做分词，故用 xargs）
ls tests/test_*.py | sed 's|/|.|; s|\.py$||' | xargs .venv/bin/python -m unittest

# 2) 架构验证 V1–V7
.venv/bin/python -m unittest tests.test_verification_v1_v7 -v

# 3) 输出截断与重试分类
.venv/bin/python -m unittest tests.test_model_truncation -v

# 4) 真实 API 冒烟（会消耗少量额度）
.venv/bin/python scripts/smoke_real_api.py

# 5) 真实物料索引自检
.venv/bin/python -c "from infrastructure.vector_store import FAISSManager; s=FAISSManager('data/faiss_index'); print(len(s.metadata), s.index.ntotal)"
```
