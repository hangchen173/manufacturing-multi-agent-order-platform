# 会话交接说明

> 生成时间：2026-09-11
> 当前分支：`develop`　最新提交：`f12d259`
> 工作区状态：干净（无未提交改动）

---

## 一、当前任务

**P2-4：建立开发冒烟集与独立验收集**，原文见 [`TODO_INTERVIEW_4_DAYS.md`](./TODO_INTERVIEW_4_DAYS.md) L146-155。

要点：
- 开发冒烟集约 12 条制造业样本（覆盖三类动作与关键规格），另约 6 条公开图片验证图像通路。
- 独立验收集约 20-30 条（文本型 PDF、图片、缺字段、歧义、长明细），与开发集用途分开。
- 每份样本需确认输入、字段标注、SKU 与动作依据；无业务标注的公开集不计业务指标。
- 补齐生成方法，避免只有本机存在输入文件。
- **不需要 Qwen**；不得用被测模型生成未经核查的标准答案。
- 验收要求：样本独立于调参、标注可追溯原文与业务政策、明确各格式覆盖范围。

---

## 二、已完成

**本会话（上下文丢失后）仅做只读核查 + 环境探针，未产出任何仓库文件。**

上一轮已提交（此提交打包的是**更早会话**的改动，非本会话产物）：

```
f12d259 feat(evaluation): 重构匹配/风控链路并补齐下游重放与回归测试
38 files changed, 47340 insertions(+), 367 deletions(-)
```

包含：匹配/风控重构、`evaluation/replay_downstream.py`、评测契约与指标增强、回归测试、结果归档。

已逐字确认的事实（**下个会话无需重复读码**）：

| 项目 | 结论 |
|---|---|
| 校验范式 | `evaluation/replay_downstream.py` 已有 `reconstruct_parsed_order` / `replay_order` / `classify_items`，可直接对标，天然满足"不调用 Qwen" |
| 重放调用链 | `create_order` → `update_parsed_order` → `update_order_status(OrderStatus.PARSING)` → `_process_matching_phase` |
| `_process_matching_phase` 返回值 | dict：`success` / `order_id` / `final_result` / `business_decision` / `needs_confirmation` / `message` / `usage` |
| 业务动作判定 | `_decide_business_action`：`needs_confirmation` → `MANUAL_REVIEW`；归一化非空 → `AUTO_CORRECT`；否则 `AUTO_APPROVE` |
| 归一化范围 | 仅 `material_name` / `specification`；数量、单价、交期永不自动纠正 |
| PDF 通路 | `fitz` + 内置 `fitz.Font("china-s")` + `TextWriter` 可生成中文 PDF，回读行首 `^\s*\d+\s+\S` 可被 `_count_source_rows` 统计 ✅ |
| Excel 通路 | `pd.read_excel().to_string(index=False)`，需首列含序号才能被行数校验统计 |
| `reportlab` | venv 有 4.4.10 但**不在 requirements** → 已决定不引入，PDF 一律用 fitz |
| 素材路径 | `data/standard_materials.csv`（720 SKU = 12 类 × 60）、`data/faiss_index`（见 `config.py` DataConfig） |
| 评测时点 | 须以 `RISK_EVALUATION_AS_OF=2026-09-01` 固定（`generated_complex` 同值） |
| 格式边界 | 仅 PDF / xlsx / png,jpg,jpeg；`.txt/.csv` 不在 `SUPPORTED_EVAL_EXTENSIONS` |
| 素材锚点 | `VLV-001`(48.00 全通径) 与 `VLV-006`(69.25 缩径) 规格前缀同为 `Q11F-16P DN15` → 可用不完整规格稳定造 `AMBIGUOUS_MATCH`(HIGH) |
| CORD 标注 | 无 `golden_sku_code`，只验图像通路，不计业务指标 |
| 标注缺失后果 | `evaluate_document` 会 `raise SystemExit` → 每个 document 必须有 annotation |

**两条样本陷阱（必须遵守）：**

1. 单位 ∈ {个, 只, 件} 时 `quantity % 10 == 0`，否则触发 `NON_PACK_QUANTITY`(HIGH)。
2. 单价须落 `[0.5, 1.5] × 参考价`，否则 `PRICE_ABNORMAL`(MEDIUM) 会污染期望动作（MEDIUM 不送审但会改变动作判定）。

---

## 三、未完成（下一个会话的执行清单）

- [ ] 创建 `scripts/build_evaluation_samples.py`（P2-4 核心产物，**唯一未闭环项**）
- [ ] 生成 `datasets/self_built/` 样本、标注与 manifest
- [ ] 实现 `--validate` 确定性校验报告（标注"下游重放 / 非端到端 / 不调用 Qwen"）
- [ ] 更新 evaluation 文档，说明格式覆盖范围与用途分离
- [ ] 勾选 `TODO_INTERVIEW_4_DAYS.md` 中 P2-4 的四项 checkbox
- [ ] P2-5（L157-166）、P2-6（约 18 条开发冒烟样本调真实 Qwen，L168-176）尚未开始

---

## 四、下一步实现方案

创建 `scripts/build_evaluation_samples.py`，风格对齐 [`scripts/prepare_cord.py`](./scripts/prepare_cord.py)：

- 结构：`PROJECT_ROOT = Path(__file__).resolve().parents[1]`、`parse_args()`、`export_dataset(...) -> int`、`main() -> int`
- 参数：`--output-dir`（默认 `datasets/self_built`）、`--validate`、`--evaluation-as-of 2026-09-01`
- 取数：从 `data/standard_materials.csv` **动态按 `sku_code`** 取标准名/规格/单位/参考价，禁止硬编码物料数据
- 开发冒烟集：12 条制造业 PDF/Excel（三类动作各 ≥3；`auto_correct` 走别名归一化与规格 `*↔×` 归一化；`manual_review` 走缺规格 / `Q11F-16P DN15` 歧义 / 缺数量 / 缺单价 / `PAST_DELIVERY`）+ 6 条 CORD jpg（不计业务指标）
- 独立验收集：20-30 条，覆盖文本 PDF、图片、缺字段、歧义、长明细（≥30 行）
- 输出：`datasets/self_built/{orders_raw/{pdf,image},annotations,manifests/self_built_orders_manifest.csv}` 与同 `datasets/generated_complex/dataset_summary.json` 结构的 `dataset_summary.json`
- `--validate`：复用 `validate_material_index` + `create_evaluation_orchestrator(evaluation_as_of="2026-09-01")` + `replay_order` 式固定 `ParsedOrder` 走 `_process_matching_phase`，核对 golden SKU 与期望动作
- 节奏要求：**先落盘、再验证**，用真实 `--validate` 回执迭代修正，不要靠读代码推断

---

## 五、注意事项

1. **提交内容提醒**：`f12d259` 包含 `evaluation/results/` 下 4 组 240 条重放结果（约 17MB 文本 jsonl）。若视为调参中间产物不宜入库，可 `git rm -r --cached` 后追加提交剔除。
2. **环境**：`.venv/bin/python` = Python 3.11.13（PyMuPDF 1.27.1、pandas 2.2.1、openpyxl 3.1.2）。
3. **工具坑**：`LS` 会过滤被 `.gitignore` 忽略的二进制路径（`*.jpg/*.pdf/*.faiss/*.pkl/*.xlsx`），判断此类目录是否存在须用 shell `ls -la`。
4. **不存在** `scripts/dev/` 目录（历史脚本 `generate_test_pdfs_v2.py` 已不可考）。
