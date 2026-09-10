# Evaluation

这个目录用于管理项目评测，不和业务代码混在一起。

- `EVALUATION_PLAN.md`: 主评测方案，包含公开数据集、自建数据集、指标、执行步骤。
- `run_evaluation.py`: 批量评测入口，读取 `processed/` 目录并输出结果。
- `templates/`: 标注模板、结果模板、manifest 示例。
- `results/`: 后续放评测结果、截图、表格。
- `manifests/`: 后续放真实采样清单或下载记录。
- `notes/`: 后续放实验日志、异常案例分析。

## 阶段一契约

标注统一使用 `business_decision.action`，取值为 `auto_approve`、`auto_correct` 或
`manual_review`。评测加载标注时会校验 `document_id`、`order_level` 和 `items`；缺失字段直接失败。
历史模板中的 `confirmation.needs_manual_confirmation` 会在加载时转换为上述动作，结果中只使用统一动作口径。

明细指标按预测与标签行数的较大值计数，漏行、多行和未知 SKU 不会从分母中消失。每次运行的
`run_manifest.json` 会记录物料 CSV、FAISS 文件摘要、模型名称和阈值，保证基线可追溯。

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
- `failures.json`
- `run_manifest.json`
