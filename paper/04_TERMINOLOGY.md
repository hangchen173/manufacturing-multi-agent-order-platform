# 术语翻译表（Terminology）

> 用途：把工程语言翻译成学术语言。**这是最容易被忽略但极其重要的一步**——
> 审稿人看不懂「黑板」「言后行为」这类自造词，会直接判定为「工程报告」而非「研究论文」。
> 来源：`../docs/PAPER_PLAN.md` §6 步骤 2，已按本项目实际术语核对。

---

## 1. 核心术语对照

| 项目中的叫法 | 论文中的表述（英文） | 说明 |
|---|---|---|
| 黑板 | **shared blackboard** / structured message bus | 避免直译 blackboard 造成误解，首次出现需定义 |
| 三层黑板 | three-layer blackboard（control state / claims & evidence / order facts） | 需在 Method 中给出形式化定义 |
| 对抗协议 | **adversarial verification protocol** | 与 MAD 区分开 |
| 上下文切片 | **structural context isolation** / selective information hiding | 强调「结构性」而非「提示词层面的要求」 |
| 预算熔断 | **budget-constrained escalation** | 强调「升级人工」而非「降低标准」 |
| 任务 DAG | task dependency graph | — |
| 可复现证据 | **machine-checkable evidence** / verifiable locator | **本文核心术语**，须在 Problem Formulation 中形式化 |
| 言后行为 | **speech act** / performative | 7 种言后行为需列表定义 |
| 终裁 | adjudication | — |
| 主张 | claim / proposition | 对应 PROPOSE |
| 挑战 | challenge | 对应 CHALLENGE，须携带可复现反证 |
| 裁决 | verdict | 对应 VERDICT |
| 争议升级 | dispute escalation | 标记为 `DISPUTED` 后交人工 |
| 幻觉逃逸 | **hallucination escape** | **核心指标**：抽取值在原文无对应证据却进入自动通过的比例 |
| 订单级三重预算 | per-order triple budget（token / call count / wall-clock） | 论文中作为评估维度 |

---

## 2. 需谨慎使用的表述

| ❌ 避免 | ✅ 改为 | 原因 |
|---|---|---|
| 「我做了一个多 Agent 订单解析系统」 | 「本文提出 X 机制，在 Y 场景下把 Z 指标从 A 降到 B」 | 前者是项目描述，无主张、不可证伪 |
| 「效果很好」 | 「幻觉逃逸率从 A% 降至 B%（p < 0.05，n=3 次重复）」 | 结论必须有数据支撑 |
| 「详见代码」 | 算法伪代码 + 完整超参 | 审稿人不会去读仓库 |
| 「我们的系统优于已有方法」 | 「在统一 token 预算下，本方法相比 MAD 提升 X 个百分点」 | 必须交代对比口径 |

---

## 3. 建议标题

- **英文（首选）**：*Evidence-Anchored Adversarial Verification: Machine-Checkable Locators as the Debate Medium for LLM-Based Structured Document Extraction*
- **中文**：证据锚定的对抗验证：以机器可核查定位符作为辩论媒介的结构化文档抽取方法

> 来源：`../docs/PAPER_PLAN.md` §1。定稿前需结合最终选定的会议调整措辞。

---

## 4. 贡献的措辞（Introduction 末尾用）

> **D12 已于 2026-10-02 关闭**：定为 **3 条正式贡献 + 1 条附带**。
> 最终口径见 `09_STRUCTURE_AND_CONTRIBUTIONS.md` §2。

- **C1｜证据锚定的对抗验证协议（VEAP）**：挑战必须以「定位符 + 原文值」形式给出；
  反馈回灌时剔除自然语言措辞，使验证过程可程序化复核。
- **C2｜反证媒介的对照实证**：首个把「反证媒介形态」作为**唯一自变量**的对照实验，
  量化 locator 反证 vs 自然语言反证对幻觉修正率的影响。**核心贡献**
- **C3｜预算感知的验证策略**：统一三重预算（token / 调用次数 / 墙钟）下的
  accuracy–cost Pareto 前沿，并确立「预算耗尽升级人工而非静默通过」的策略及其代价。
- **C4｜可复现的评测协议**（**附带贡献，一句话 + 一段，不计入正式列表**）：
  运行身份可追溯、失败落盘、拒绝跨版本 resume。
