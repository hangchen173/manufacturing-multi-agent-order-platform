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
