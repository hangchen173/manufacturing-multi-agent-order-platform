# Evaluation

这个目录用于管理项目评测，不和业务代码混在一起。

- `EVALUATION_PLAN.md`: 主评测方案，包含公开数据集、自建数据集、指标、执行步骤。
- `run_evaluation.py`: 批量评测入口，读取 `processed/` 目录并输出结果。
- `replay_downstream.py`: 下游重放入口，固定旧 `ParsedOrder`，只重放当前 Matching/Risk/业务动作。
- `templates/`: 标注模板、结果模板、manifest 示例。
- `results/`: 后续放评测结果、截图、表格。
- `manifests/`: 后续放真实采样清单或下载记录。
- `notes/`: 后续放实验日志、异常案例分析。

## 阶段一契约

标注统一使用 `business_decision.action`，取值为 `auto_approve`、`auto_correct` 或
`manual_review`。评测加载标注时会校验 `document_id`、`order_level` 和 `items`；缺失字段直接失败。
历史模板中的 `confirmation.needs_manual_confirmation` 会在加载时转换为上述动作，结果中只使用统一动作口径。

明细指标按预测与标签行数的较大值计数，漏行、多行和未知 SKU 不会从分母中消失。每次运行的
`run_manifest.json` 记录完整运行身份（代码版本、工作区指纹、提示词指纹、模型与阈值、物料/FAISS 摘要、
数据集与标注指纹、评测时点），保证基线可追溯。

## 运行归档与补跑

每个样本的每次尝试都会即时追加写入 `attempts.jsonl`，中断后已落盘的结果不会丢失。用
`--resume-run <run_dir>` 补跑时，只会重跑从未成功过的样本，并把新尝试追加到同一目录；最终预测优先取
首次成功的尝试，`predictions.jsonl` 中的 `attempt` / `attempt_count` 可追溯每条预测来自哪一次尝试。
若当前代码、提示词、模型或数据集与归档运行身份不一致，会拒绝 resume 并另建新运行，避免不同版本混算。
`summary.json` / `summary.md` 会分开给出首次成功率、重试后成功率以及累计耗时与 tokens。

## 快速使用

### 仅批量推理

```bash
python3 -m evaluation.run_evaluation \
  --input-dir datasets/public/sroie/processed \
  --dataset-name sroie_smoke
```

### 带标注评测

如果文档旁边有同名标注 JSON，工具会自动读取。  
也可以单独指定标注目录：

```bash
python3 -m evaluation.run_evaluation \
  --input-dir datasets/self_built/orders_raw/pdf \
  --annotation-dir datasets/self_built/annotations \
  --dataset-name self_built_pdf_eval
```

### 输出结果

运行后会在 `evaluation/results/<dataset_name>_<timestamp>/` 下生成：

- `summary.json`
- `summary.md`
- `predictions.jsonl`
- `attempts.jsonl`
- `failures.json`
- `run_manifest.json`

## 下游重放（非端到端）

`replay_downstream.py` 固定已归档的旧 `ParsedOrder`，只重放当前的 Matching / Risk /
业务动作阶段。它不经过 Parser、自纠错、HTTP、数据库，也不调用 Qwen，因此输出必须标注为
“下游重放”，不得当作端到端指标。

```bash
python3 -m evaluation.replay_downstream \
  --predictions evaluation/results/<archived_run>/predictions.jsonl \
  --dataset-name downstream_replay \
  --evaluation-as-of 2026-09-01
```

`--evaluation-as-of` 固定风控交期判断所用的评测时点，取值来自数据集的
`dataset_summary.validation.evaluation_as_of`（生成集为 `2026-09-01`），保证重放可复现；
不传时回落到 config/env 默认值。运行前会用 `validate_material_index` 校验物料 CSV 与 FAISS
索引 metadata 一致（含 `aliases` 字段，用于名称兼容性判断）。

输出目录除标准 `summary.json` / `summary.md` 外，还包含：

- `replay_summary.json` / `replay_summary.md`: 下游重放报告（含覆盖度与高分错 SKU 复查）。
- `replay_predictions.jsonl`: 逐样本重放结果。

报告中的口径：

- **Accepted-SKU coverage / precision / SKU accuracy**：在“有金标 SKU”的明细上统计，
  区分正确匹配、错误接受与拒识；无金标 SKU 的行单独记为正确拒识或错误接受。
- **High-Score Wrong SKU Recheck**：复查旧版 `match_score >= 0.8` 却 SKU 错误的行，按重放
  结果归为 `fixed`（已改对）、`rejected`（改为拒识）或 `still_wrong`（仍错误）。

口径差异说明：`KNOWN_ISSUES.md` / REVIEW 记录的下游重放为 SKU 98.69%、动作 99.58%
（5805/5882），属于较早代码状态；本脚本在重建索引（补 `aliases`）后为 SKU 98.86%、
业务动作 92.92%（223/240）。两者均为固定旧解析结果的下游重放，动作口径的差异来自动作
判定逻辑与旧基线不同，不代表端到端准确率，也不改写旧基线数字。
