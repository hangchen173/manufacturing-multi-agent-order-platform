# 论文章节骨架与素材映射

> 用途：把现有代码资产映射到论文章节，明确「哪些章可直接改写、哪些章必须从零写」。
> 来源：`../docs/PAPER_PLAN_SCI_Q1.md` §5、`../docs/PAPER_PLAN.md` §5。
> 目标篇幅：**LNCS 单栏约 17 页**（2026-10-02 第二轮：主投 ICDAR 2027，页限由 12 放宽到 17），
> 其中 Method + Results 占 8.5 页。章节页数预算见 `08_SUBMISSION_PLAN.md` §2.2 / `01_CONFIG.md` §6.3。
>
> ⚠️ **本文件已于 2026-10-02 被以下文件细化，冲突时以后者为准**：
> - `09_STRUCTURE_AND_CONTRIBUTIONS.md` — 贡献与章节结构的**最终口径**（已关闭 D12）
> - `10_EXPERIMENTS.md` — 实验矩阵（MVP 版）
> - `11_PROBLEM_FORMULATION.md` — §3 草稿（已完成）
> - `12_METHOD_DRAFT.md` — §4 草稿（已完成）
>
> 本文件保留作为**代码素材映射表**使用。

---

## 一、章节状态总览

| # | 章节 | 篇幅 | 状态 | 素材来源 |
|---|---|---|---|---|
| 1 | Introduction | 1.0 页 | **从零写（最后写）** | 问题定义 + 3 条 contribution bullets |
| 2 | Related Work | 1.5 页 | **从零写（最关键）** | `03_LITERATURE.md` 文献矩阵直接生成 |
| 3 | Problem Formulation | 1.0 页 | ✅ **草稿已完成** | `11_PROBLEM_FORMULATION.md` |
| 4 | Method | 3.0 页 | ✅ **草稿已完成** | `12_METHOD_DRAFT.md` + 三处代码 |
| 5 | Experimental Setup | 1.5 页 | 待写（依赖实验） | `10_EXPERIMENTS.md` |
| 6 | Results | 2.5 页 | **待实验产出** | E1–E6 六组实验 |
| 7 | Discussion & Limitations | 1.0 页 | **从零写** | 含 Limitations |
| 8 | Conclusion | 0.5 页 | 从零写 | 重述贡献 |

**合计 12.0 页**（LNCS 单栏，不含参考文献）。

**总结**：Method 与实验基建可直接从现有资产改造；**绪论、相关工作、讨论三章需从零写**。
§3 与 §4 的草稿已于 2026-10-02 完成。

---

## 二、逐章要点与代码映射

### 1. Introduction（1.5 页，从零写）

- 开篇：结构化文档抽取在工业场景的价值
- 问题：LLM 幻觉，且**模型自报置信度不可靠**
- 现有方法的硬伤：自修正无效（引 ACL 2026）；自然语言辩论**不可机器核查**
- 本文主张一句话 + **contribution bullets**（3 或 4 条，见 `04_TERMINOLOGY.md` §4）
- ⚠️ **前两段必须直击问题，不要堆背景**

### 2. Related Work（2 页，从零写）★ 最关键

三条线，每条末尾必须落到「**与我何异**」：

| 小节 | 内容 | 素材 |
|---|---|---|
| 2.1 文档信息抽取 | LayoutLM 系列、Donut；**必须引所使用数据集的原文** | 矩阵 C 组（#12–#18） |
| 2.2 LLM 自验证与多智能体协作 | self-consistency、self-refine、MAD、FC-MAD、MoA、LLM-as-a-Judge | 矩阵 B 组（#6–#11） |
| 2.3 幻觉检测与证据归因 | grounding / attribution / citation 线 | 矩阵 #20 待补 |
| 2.4 本文与已有工作的关系 | **定位表**，逐条说明差异 | 矩阵 A 组（#1–#5） |

> **必须正面处理 §2.4 的 5 篇竞争工作。回避是拒稿的常见原因。**

### 3. Problem Formulation（1 页，从零写）

- 符号定义：文档 `D`、字段模式 `S`、抽取函数 `f`、**证据 `E = (kind, locator, value)`**
- 定义「**可复现证据**（reproducible evidence）」与「**幻觉逃逸**（hallucination escape）」
- 形式化 VEAP 的输入输出
- 符号表（Table 1）

> **这是把工程实现转为学术表述的关键一章**，审稿人从这里判断工作的严谨性。

### 4. Method（3 页，可改写）

| 小节 | 内容 | **代码来源** |
|---|---|---|
| 4.1 总览 | 系统架构图 | `MULTI_AGENT_DESIGN.md` §2.3–2.4（改写成英文） |
| 4.2 证据锚定的对抗协议（C1） | PROPOSE → CHALLENGE → VERDICT 形式化 + **Algorithm 1 伪代码** | **`application/protocol/adversarial.py`** |
| 4.3 结构性上下文隔离（C2） | 黑板三层结构与切片机制；形式化说明「隔离是结构性的」 | **`application/blackboard/slices.py`** + `blackboard.py` |
| 4.4 争议升级与预算熔断（C3） | 三重预算定义 + 升级策略 | **`application/protocol/budget.py`** + `arbitration.py` |
| 4.5 复杂度分析 | 时间 / token 复杂度随字段数、行数的增长 | 需新写 |

> **已核实的关键代码事实**（`adversarial.py`，2026-10-01 读取）：
> - `build_counter_evidence_feedback()` 确实**只回灌 locator + 原文值，不回灌验证者措辞**
>   —— 这是 C1 主张的**代码级证据**，论文中应直接引用该函数
> - `challenge_evidence()` 构造 `Evidence(kind, locator, value, reproducible=True)`
>   —— 对应形式化定义中的证据三元组
> - `_describe_locator()` 支持三种 locator：`cell`（工作表/行/列）、`page`（页码）、`span`（文本片段）
>   —— 论文中应把这三种作为 locator 的完备取值域

### 5. Experimental Setup（1.5 页，可改造）

- 数据集与标注协议（含自建集构建过程）
- 基线实现细节（**必须写清每个基线的复现配置**）
- 评估指标定义
- **计算预算的统一口径**（token / 调用次数 / 墙钟）
- 硬件与超参数 → 取自 `01_CONFIG.md`

### 6. Results（3 页，待实验产出）

| 小节 | 内容 | 产出物 |
|---|---|---|
| 6.1 主结果 | 域内性能，字段级 F1 + 幻觉逃逸率 | 表 1 |
| 6.2 基线对比 | 与 **5 个**基线的对比 | 表 2 + 图 1 |
| 6.3 **预算-准确率前沿** | Pareto 曲线 ← **亮点** | 图 2 |
| 6.4 消融实验 | 5–6 项消融 | 表 3 |
| 6.5 跨域泛化 | 四个公开数据集 | 表 4 |
| 6.6 失败分析 | 诚实呈现失败模式 | 图 3 + 案例 |

### 7. Discussion（1 页，从零写）

- 为什么证据锚定有效（**机制层面的解释**，而非只是数字）
- 与 ACL 2026「自我修正需要外部信号」结论的呼应
- **Limitations**：跨域边界（CORD）、并发上限、模型依赖、成本

### 8. Conclusion（0.5 页）

- 重述贡献（**不要引入新内容**）
- 一句话总结

---

## 三、写作顺序建议

> **不要按章节顺序写。**

1. **Results**（有数据好写）
2. **Method + Problem Formulation**（先定方法，才知道要跑什么实验）
3. **Related Work**（由文献矩阵直接生成）
4. **Introduction**（最后写，因为要呼应全文）
5. **Discussion / Conclusion**

英文写作建议：**先用中文写完整逻辑，再翻译**，最后找母语级润色。
