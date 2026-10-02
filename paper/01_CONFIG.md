# 论文配置表（Paper Configuration）

> 用途：论文中「实验设置」「可复现性」章节的数据来源。
> **原则：论文里写的每个数字都必须来自本文件的实测值，不得沿用 docs 中的旧数字。**

---

## 1. 冻结版本（A1 产出）

| 项 | 值 |
|---|---|
| Git tag | **`paper-v1-baseline`** |
| Commit hash（完整） | `a596bd67ffc19adf841e4909dbf43961373493c2` |
| Commit hash（短） | `a596bd6` |
| Commit 时间 | 2026-10-01 01:07:26 +0800 |
| 分支 | `paper-ccfc-prep` |
| 冻结日期 | 2026-10-01 |

**第二基线 `paper-v2`**（2026-10-02，D21 落地后）：

| 项 | 值 |
|---|---|
| Git tag | **`paper-v2`** |
| Commit hash（短） | `4e01e92` |
| 与 v1 的差异 | 验证者在**接受**时也外化证据 + 证据链落盘（见 `13_VERIFIABILITY_EXPERIMENTS.md` §2.5） |
| 是否改变任何判定结果 | **否**。纯增量外化，不触碰裁决路径 |

**各实验基于哪个版本**（论文 Reproducibility 章必须写明）：

| 实验 | 版本 |
|---|---|
| G0 判决实验（50 次调用） | `paper-v1-baseline` |
| E7 核查成本（292:1） | `paper-v1-baseline` |
| E8 的 **before** 测量（0%） | `paper-v1-baseline` |
| E8 的 **after** 测量（100%） | **`paper-v2`** |
| E1 / E3 / E4 主实验 | **`paper-v2`** |

**冻结命令（可复现）**：

```bash
git tag -a paper-v1-baseline -m "Paper submission baseline (CCF-C conference prep)"
git rev-parse HEAD
```

> 论文的 Reproducibility 章节必须报告 commit hash。任何后续代码改动，
> 若影响实验结果，必须重新打 tag（如 `paper-v2-baseline`）并在论文中更新。

---

## 2. 代码规模（2026-10-01 实测）

| 项 | 实测值 | 统计口径 |
|---|---|---|
| 项目 Python 行数 | **14,004** | 排除 `.venv/`、`frontend/`、`datasets/`、`__pycache__/` |
| 前端 TS/TSX 行数 | **1,037** | `frontend/src/` |
| 测试文件数 | **19** | `tests/test_*.py` |
| 测试函数数 | **224** | `grep -c "def test_"` |
| 后端分层 | 六边形 `interfaces → application → domain` | 跨层违规由 AST 测试守卫 |
| Agent 总数 | **11**（10 业务 + 1 编排） | `domain/agent_roles.AgentRole` |
| 走 LLM 的 Agent | **2**（`extractor`、`review_assistant`） | 其余 8 个确定性、0 token |

> ⚠️ **与 `docs/` 中旧数字的差异（论文中必须用上表实测值）**：
> - `docs/KYAN_RETEST_STRATEGY.md` 称「13,858 行 Python」→ 实测 **14,004**
> - 同文称「241 项测试」、另一处称「231 后端测试 + 10 前端测试」→ 实测 **19 个测试文件 / 224 个测试函数**
> - `docs/PAPER_PLAN_SCI_Q1.md` 称「2,235 行 TS」→ 实测 `frontend/src/` 为 **1,037**
>
> 投稿前必须重新核对，避免审稿人复现时数字对不上。

**统计命令**：

```bash
find . -name "*.py" -not -path "./.venv/*" -not -path "./frontend/*" \
     -not -path "./datasets/*" -not -path "*/__pycache__/*" -not -path "./.git/*" \
  | xargs wc -l | tail -1

find tests -name "test_*.py" | wc -l
grep -rh "def test_" tests --include="*.py" | wc -l
```

---

## 3. 论文中需要报告的运行口径

> 以下字段需在实验基建改造（B4）后补齐实测值。

| 项 | 值 | 状态 |
|---|---|---|
| LLM 模型与版本 | 待定 | 待决事项 D8 |
| 推理后端（本地 / API） | 待定 | 待决事项 D8 |
| 随机种子策略 | 待定（每配置 ≥3 次重复） | 未开始 |
| 单订单 token 预算 | 项目已有 `application/protocol/budget.py` 三重预算 | 待核实具体默认值 |
| LLM 调用次数预算 | 同上 | 待核实 |
| 墙钟预算 | 同上 | 待核实 |
| 端到端延迟 | 评测框架已记录 | 待补论文级统计 |
| 硬件环境 | 待填 | 未开始 |
| 数据集指纹 | `evaluation/run_manifest.json` 已记录 | 待导出 |

---

## 4. 可复现性基建（项目已有，论文中可作为贡献 C4）

| 能力 | 代码位置 |
|---|---|
| 运行身份可追溯（代码版本 / 提示词指纹 / 模型阈值 / 数据集指纹） | `evaluation/run_manifest.json` |
| 失败尝试即时落盘、支持补跑 | `evaluation/run_evaluation.py` |
| 拒绝跨版本 resume | 同上 |
| 订单级三重预算（token / 调用 / 墙钟）+ 熔断 | `application/protocol/budget.py` |
| 架构断言 V1–V7 | `tests/test_verification_v1_v7.py` |

---

## 5. 目标会议 CFP 实测（D14，2026-10-02 官网核实）

> 🔴 **本节已于 2026-10-02 第二轮被取代**：主投目标由 PAKDD 2027 改为 **ICDAR 2027**。
> **现行口径见 §6**。本节保留为**历史记录**（改判理由见 `08_SUBMISSION_PLAN.md` §0.1）。
>
> 来源：`https://www.pakdd2027.org/pages/calls/research`、`/pages/dates`、`/pages/calls/llm-agentic`
> 核实日期：**2026-10-02**。以下为官网原文口径，不再依赖第三方汇总站。

| 项 | 官网口径 | 状态 |
|---|---|---|
| 会议全称 | The 31st Pacific-Asia Conference on Knowledge Discovery and Data Mining (PAKDD 2027) | ✅ |
| 会期 / 地点 | 2027-06-29（周二）~ 07-02（周五），新西兰 惠灵顿 | ✅ |
| **截稿** | **2026-11-20（周五）23:59 AoE** | ✅ 已核实到时区 |
| 录用通知 | 2027-02-26（周五） | ✅ |
| **Camera-ready** | **2027-03-19（周五）** | ✅ ⚠️ **落在复试期（3~4 月），已记入风险** |
| 模板 | **Springer LNCS** | ✅ |
| 审稿制度 | **双盲**（double-blind） | ✅ |
| 现场要求 | **「PAKDD 2027 will be held exclusively in person. All accepted presentations must be delivered on-site.」** | ✅ 强制现场 |
| 出版 | Springer Conference Proceedings | ✅ |
| 专轨 | **Special Track on Large Language Models and Agentic AI in Data Science**，与主轨**同截稿**、同入 Springer 论文集 | ✅ |
| **页数上限** | 官网原文：「The page limit and the submission site are **still being confirmed**」 | ⏳ **待公布** |
| 投稿系统 | 同上，尚未公布 | ⏳ **待公布** |
| 预印本 / arXiv 政策 | CFP 未提及 | ⚠️ 按「投稿前不主动公开」保守处理 |

### 5.0 未选 PAKDD 的原因（2026-10-02 第二轮记录）

1. **G0 判决实验已推翻 C1 的实证主张**，论文需重建——**11-20 截稿只余 7 周，不够**；
2. **专轨附带排除条款**：「multi-agent systems in the general sense, **without a data science or
   knowledge discovery focus**, is outside the scope」→ 需额外包装；
3. **11-20 截稿把工作量压在 10–11 月**（考研冲刺期）——「12 月不碰论文」只保护了 12 月；
4. 页数上限到 10-02 仍「still being confirmed」，且为 **12 页**（ICDAR 为 **17 页**）；
5. 惠灵顿**必须现场**且差旅 **¥12–20k**（吉隆坡**免签**、¥1.5–3k）。

### 5.1 内部硬截止的时区换算

截稿为 **AoE（UTC-12）**。北京时间为 UTC+8，故北京时间比 AoE **早 20 小时**：

| 口径 | 时刻 |
|---|---|
| AoE 2026-11-20 23:59 | **北京时间 2026-11-21 19:59** |
| 内部硬截止（自设） | **2026-11-16**，留 4 天缓冲 |

> ⚠️ **注意**：此前第三方源显示的「2026-11-21」正是**北京时间**下的日期，与官网 AoE 口径一致，不是矛盾。论文与投稿系统一律以 **AoE** 为准。

### 5.2 为什么投专轨而不是主轨

主轨 CFP 明确：「Work on large language models and agentic AI for data science is better suited to the **Special Track on Large Language Models and Agentic AI**」。本工作以 LLM 抽取 + 多智能体对抗验证为核心，投主轨会被分流。

### 5.3 ⭐ 专轨 topic list 与本项目的逐条对应（决定性的契合度证据）

专轨 CFP 显式列出的 topic 中，以下条目与本文三条贡献**一一对应**：

| 专轨 topic（官网原文） | 本文对应 |
|---|---|
| *Reproducibility, verifiability and **auditability** of agent-generated analyses* | **C2b** 可核查字段覆盖率 |
| *Hallucination detection, factual **grounding** and uncertainty quantification* | **C1** VEAP 的溯源验证 |
| ***Multi-agent** collaboration, specialization and orchestration for data science and knowledge discovery* | 11 Agent + 对抗协议 |
| *Memory, context management, retrieval, search and **evidence gathering** for data-intensive agentic systems* | **C1** 证据三元组 `E=(kind, locator, value)` |
| *Cost, latency and sustainability of LLM and agentic workflows* | **C3** 预算感知验证 |
| *Benchmarks and evaluation **methodologies** for LLMs and agents* | **C4** 可复现评测协议 |
| *Domain applications in ... **industry*** | 制造业采购订单 |

> **写作含义**：Introduction 与 Related Work 应直接引用专轨 CFP 的措辞（auditability / grounding / evidence gathering）来定位本文，
> 而不是泛泛说「多智能体很重要」。这能显著提高与专轨 PC 的契合度感知。

### 5.4 一条必须注意的**排除条款**

专轨 CFP 明确：「Work on **multi-agent systems in the general sense**, such as coordination theory or agent-based modelling **without a data science or knowledge discovery focus**, is **outside the scope** of this track.」

> 本文的数据抽取 / 知识发现属性**必须写在标题与摘要的第一句**，否则有被判 out-of-scope 的风险。
> 这正是标题候选 A（*...for Multi-Agent Document Extraction*）优于纯机制型标题的原因。
>
> ⭐ **2026-10-02 改判后**：ICDAR 2027 **没有**此类排除条款——「多智能体做文档抽取」就是它的正题。
> 该包装负担解除。

---

## 6. ⭐ 现行目标会议：ICDAR 2027 实测（2026-10-02，三源交叉核实）

> 来源：`mldeadlines.com/conference/icdar-2027`、`aiwhatson.com/event/icdar-2027-*`、
> `beri.net/events/icdar-2027`（三者均引 `icdar2027.org` 官方 CFP，**互相一致**）。
> ⚠️ **`icdar2027.org` 有 Cloudflare 反爬，本次未能直接抓取官网**——
> **投稿前必须人工打开 `/call-for-papers` 与 `/important-dates` 复核本节全部条目**。

| 项 | 核实结果 | 一致性 |
|---|---|---|
| 会议全称 | 21st International Conference on Document Analysis and Recognition (ICDAR 2027) | ✅ |
| 会期 / 地点 | **2027-08-18 ~ 22，马来西亚 吉隆坡**（预计约 450 人） | ✅ |
| **摘要截稿** | **2027-01-31 23:59 AoE**（**"no extension"**） | ✅ 三源 |
| **全文截稿** | **2027-02-20 23:59 AoE** | ✅ 三源 |
| 审稿意见返还 | **2027-04-20** | ✅ 两源 |
| **Rebuttal 截止** | **2027-04-27**（窗口 **7 天**） | ✅ 两源 |
| **录用通知** | **2027-05-15** | ✅ 两源 |
| **Camera-ready** | **2027-06-05** | ⚠️ 单源 |
| 模板 / 页数 | **Springer LNCS，最多 17 页** | ✅ 两源 |
| 审稿制度 | **双盲 + rebuttal 环节** | ✅ 两源 |
| 出版 / 检索 | Springer LNCS 论文集；EI / Scopus | ✅ |
| 另有轨道 | **ICDAR–IJDAR journal track**（独立期刊轨，可作备投） | ⚠️ 单源 |
| 录用率 | 历史平均约 **40.3%** | ✅ `openresearch.org/wiki/ICDAR` |
| 现场要求 | **in-person**；每篇录用论文至少一名作者完成 **full main conference registration** | ✅ |
| 签证 | **中国公民免签**——《中马互免持公务普通护照和普通护照人员签证的协定》**2025-07-17 生效**（条约级），单次停留 ≤30 日 | ✅ |

### 6.1 内部硬截止的时区换算

| 口径 | 时刻 |
|---|---|
| AoE 2027-02-20 23:59 | **北京时间 2027-02-21 19:59** |
| **摘要** AoE 2027-01-31 23:59 | **北京时间 2027-02-01 19:59** |
| 内部硬截止（自设） | **2027-02-16**，留 4 天缓冲 |
| 摘要内部截止（自设） | **2027-01-29**，留 2 天缓冲 |

### 6.2 ⭐ main track 征稿方向与本项目的对应（决定性的契合度证据）

ICDAR 2027 CFP 把以下议题列为**一等公民**（非 workshop 边角）：

| ICDAR 2027 main track topic（官方 CFP） | 本文对应 |
|---|---|
| ***agents for document AI*** | 11 Agent + 对抗协议（**正题，无需包装**） |
| ***multimodal LLMs for documents*** | 图片路径抽取（`extractor.py:196`） |
| ***document reasoning models*** | PROPOSE → CHALLENGE → VERDICT 对抗推理 |
| *foundation models for document understanding* | LLM 抽取器 |
| ***information extraction and document retrieval*** | 结构化字段抽取（订单明细） |
| *table and formula recognition* | 表格单元格定位符 `cell(sheet,row,col)` |
| *document forensics and provenance* | **C1** 证据三元组 `E=(kind, locator, value)` + ρ(ℓ,D) 复算 |
| *private and secure document understanding* | 结构性上下文隔离（`FORBIDDEN_KEYS`） |
| *Benchmarks / evaluation*（散见） | **C2** 核查成本 292:1 + 审计可核查覆盖 0%→100% |

> **写作含义**：Introduction 与 Related Work 应直接引用 ICDAR CFP 的措辞
> （*agents for document AI* / *document reasoning* / *information extraction* / *provenance*）
> 来定位本文。**注意 §5.3 的 PAKDD 专轨映射表仍可用于贡献-议题对应，但引用时须换成 ICDAR 的措辞。**

### 6.3 17 页的章节预算

| 章 | 页数 | 内容 |
|---|---|---|
| 1 Introduction | 1.5 | 定位 + 三条贡献 |
| 2 Related Work | 1.5 | 文献矩阵生成 |
| 3 Problem Formulation | 1.5 | 7 个定义 + Proposition 1 |
| 4 Method（VEAP） | 3.5 | Algorithm 1 + 上下文隔离 + 预算熔断 |
| 5 Experiments | 5.0 | E1/E3/E4/E7/E8 + **G0 负面结果（§5.4）** |
| 6 Discussion & Limitations | 1.5 | 诚实报告边界 |
| 7 Conclusion | 0.5 | — |
| References | 2.0 | — |
| **合计** | **17.0** | — |
