# paper/ — 论文准备工作区

> 目标出口：**CCF-C 会议**（候选见 `../docs/CCF_CONFERENCE_SHORTLIST.md`）
> 核心主张：**VEAP** —— 把对抗协议的反证媒介从自然语言论证改为**机器可核查的证据定位符**
> 创建日期：2026-10-01 ｜ 所在分支：`paper-ccfc-prep`

---

## 一、进度看板

状态：`未开始` / `进行中` / `已完成` / `阻塞`

### 阶段 A｜判决与冻结

| ID | 任务 | 状态 | 产出 | 备注 |
|---|---|---|---|---|
| A1 | 冻结代码基线 | **已完成** | tag `paper-v1-baseline` | 见 `01_CONFIG.md` |
| A2 | 核实会议 CFP（截稿/页数/模板/双盲） | **进行中** | `08_SUBMISSION_PLAN.md` | 截稿已核实（PAKDD 2026-11-20）；页数/模板/双盲待官网二次核实（**D14**） |
| A3 | 文献矩阵（20 行） | 进行中 | `03_LITERATURE.md` | 骨架已建，待逐篇精读填充 |
| A4 | **新颖性判决实验** | ⛔ **G0 判定：C1 实证不支持** | `06_NOVELTY_EXPERIMENT.md` §11–§12 | **Go/No-Go 门禁已给出结论**。难度两档 × 模型三档、**共 50 次调用，0 个正向 discordant pair**，全部饱和。根因：任务太容易（基线字段准确率 0.998+，全库仅 0.19% 错误）。**待 D20 战略决策** |
| A5 | 查院校「投出去」认定口径 | **阻塞** | — | 需用户执行 |
| A6 | **C2 实证（核查成本 + 审计可复现性）** | ✅ **已完成（¥0）** | `13_VERIFIABILITY_EXPERIMENTS.md`、`scripts/verifiability_audit.py` | E7 成本比 **292:1**；E8 审计可复现性 **0%**（423 条记录 0 条带证据链）；顺带补上 **D16**（23,528 条定位符 **100% 可解析**） |

### 阶段 B｜方法形式化与实验基建

| ID | 任务 | 状态 | 产出 |
|---|---|---|---|
| B1 | 术语翻译表 + 论文骨架 | **已完成** | `04_TERMINOLOGY.md`、`05_OUTLINE.md`、`09_STRUCTURE_AND_CONTRIBUTIONS.md` |
| B2 | Problem Formulation（形式化定义） | **草稿完成** | `11_PROBLEM_FORMULATION.md` |
| B3 | Method 章英文草稿 | **草稿完成** | `12_METHOD_DRAFT.md` |
| B4 | 实验矩阵规划 | **已完成** | `10_EXPERIMENTS.md` |
| B5 | 实验基建改造（5 基线 / 字段级口径 / 重复） | 未开始 | 见 `10_EXPERIMENTS.md` §3、§7 |
| B6 | 数据集补齐（自建集规范化 + CORD 映射） | 未开始 | 见 `10_EXPERIMENTS.md` §7 |
| B7 | 投稿系统账号 + LNCS 模板 | 未开始 | 依赖 **D14** |

### 阶段 C–F

见 `../docs/CCF_C_CONFERENCE_PREP_PLAN.md` §3。本工作区随进度更新。

---

## 二、文件索引

| 文件 | 内容 |
|---|---|
| `01_CONFIG.md` | **论文配置表**：冻结版本、代码规模实测、环境与运行口径 |
| `02_DECISIONS.md` | **待决事项与决策记录**（D1–D19，含原 docs 的 M1–M12） |
| `03_LITERATURE.md` | **文献矩阵**（20 行模板 + 已预填的竞争工作） |
| `04_TERMINOLOGY.md` | **术语翻译表**：工程语言 → 学术语言 |
| `05_OUTLINE.md` | **论文章节骨架 + 代码素材映射表** |
| `06_NOVELTY_EXPERIMENT.md` | **新颖性判决实验规格**（可执行，Go/No-Go 门禁） |
| `07_BUDGET.md` | **预算估算**：实验 / 投稿 / 到会三段成本，含模型单价与注册费实测 |
| `08_SUBMISSION_PLAN.md` | ⭐ **投稿总纲**：目标会议、倒排时间节点、行动清单（**执行时以本文件为准**） |
| `09_STRUCTURE_AND_CONTRIBUTIONS.md` | ⭐ **结构与贡献最终口径**（已关闭 D12）：3 条正式贡献 + 1 条附带，5 个基线，LNCS 12 页 |
| `10_EXPERIMENTS.md` | **实验与数据整理方案**（MVP 版）：E1–E6、5 基线规格、指标定义、成本工时 |
| `11_PROBLEM_FORMULATION.md` | **§3 草稿**：文档/定位符/证据/幻觉的形式化定义 + Proposition 1 |
| `12_METHOD_DRAFT.md` | **§4 英文草稿**：总览 / VEAP + Algorithm 1 / 上下文隔离 / 预算熔断 / 复杂度 |
| `13_VERIFIABILITY_EXPERIMENTS.md` | ⭐ **C2 的实证主体（D20 方案 α+γ）**：E7 核查成本（292:1）+ E8 审计可复现性缺口（0%） |

---

## 三、三条不可协商的约束

1. **实验必须基于 `paper-v1-baseline`**。任何代码改动都要能追溯到论文配置表。
2. **12-10 ~ 12-20 初试冲刺期冻结论文工作**（`../docs/KYAN_RETEST_STRATEGY.md` §10 红线）。
3. **G0 不通过就停**。若判决实验显示 locator 反证无显著优势，停止投稿，只损失 2 周而非半年。

---

## 四、已落地的代码产物（2026-10-01，零成本）

| 文件 | 内容 | 测试 |
|---|---|---|
| `application/protocol/adversarial.py` | `build_counter_evidence_feedback(challenges, *, mode=...)`，新增 `FEEDBACK_MODES`；默认行为逐字节不变 | `tests/test_adversarial_feedback_modes.py`（10 项） |
| `scripts/novelty_experiment.py` | 判决实验脚本：造样本 → 两臂重抽 → 判定 → McNemar → 报告；`--dry-run` 不碰模型 | `tests/test_novelty_experiment.py`（16 项） |

全量测试：**257 项通过 / 0 失败**。

判决实验的 50 条注入样本已生成（字段分布 13/13/12/12），两臂 prompt 的
「单变量性」已由断言守住。**只差模型账号就能出 G0 判决。**

---

## 五、2026-10-02 本轮推进（零成本）

| 产出 | 内容 |
|---|---|
| `08_SUBMISSION_PLAN.md` | 三个候选会议重新核实（PAKDD / IJCNN / ICDAR），给出 **PAKDD 2027 主投** 的建议；49 天倒排时间节点；D1/D2/D3 建议答案；范围裁剪方案 |
| `09_STRUCTURE_AND_CONTRIBUTIONS.md` | **关闭 D12**：3 条正式贡献 + 1 条附带；5 个基线；LNCS 12 页；标题候选 |
| `10_EXPERIMENTS.md` | E1–E6 实验矩阵（MVP）；5 个基线规格；指标定义；成本 82M tokens / 72 h（4 并发）；数据整理行动项 |
| `11_PROBLEM_FORMULATION.md` | §3 草稿：7 个形式化定义 + **Proposition 1（可验证性鸿沟）** + 双目标问题表述 |
| `12_METHOD_DRAFT.md` | §4 英文草稿：含 **Algorithm 1**、上下文隔离、预算熔断、复杂度对比表 |

**本轮发现的三个硬约束**（已记入决策记录）：

1. **跨域实验只有 CORD 可用** —— `sroie`/`docvqa` 目录为空，`xfund_zh` 仅 2 张未处理
2. **自建集被 `.gitignore` 排除** —— 论文承诺「数据集公开」时无法用仓库链接交付（D9）
3. **订单级自动通过率仅 6.25%** —— HER 分母过小，叙事需改为**字段级**口径（D15）

**本轮发现的一处代码与定义的语义落差**：`Evidence.reproducible` 是生产者自报的布尔值
（`challenge_evidence()` 恒置 `True`），并未真的去 resolve 校验；而 §3 的 Definition 1
把「可复现」定义为 $\rho(\ell,D)=v$。**论文不能写得比代码更强**（D16）。

---

## 六、下一步（按依赖顺序）

| 顺序 | 动作 | 阻塞于 | 期限 |
|---|---|---|---|
| 1 | 确认 **D1 / D2 / D3**（建议答案已给出，见 `08_SUBMISSION_PLAN.md` §2） | 用户 | 10-02 |
| 2 | 决策 **D13**（Arm A 是否保留项号） | 用户 | 10-04 |
| 3 | 核实 **D14**（PAKDD 页数/模板/双盲/预印本） | 官网 | 10-03 |
| 4 | 执行 **A4 判决实验**（`--limit 5` 试跑 → `--samples 50 --repeats 3`） | D8 账号、D13 | 10-05 ~ 10-11 |
| 5 | 填 **A3 文献矩阵**（20 行，逐篇精读） | — | 10-05 ~ 10-18 |
| 6 | 实现 **5 个基线**（见 `10_EXPERIMENTS.md` §3） | — | 10-12 ~ 10-20 |
| 7 | 补测**字段级自动通过率**（D15） | — | 10-20 ~ 10-22 |

> **10-25 决策门**：若此时 E4 消融尚未出数，**转投 IJCNN 2027（2027-01-31）**，多 81 天缓冲。
