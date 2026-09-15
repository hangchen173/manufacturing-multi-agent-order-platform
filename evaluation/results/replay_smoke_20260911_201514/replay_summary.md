# 下游重放报告（非端到端）: replay_smoke

- 固定旧版解析结果来源: `/Users/cmh/Documents/AGENT_project/evaluation/results/baseline_generated_complex_test_20260910_234250/predictions.jsonl`
- 本报告固定旧 ParsedOrder，只重放当前 Matching / Risk / 业务动作；
  不经过 Parser、自纠错、HTTP、数据库，也不调用 Qwen。
- 不得把本报告的数字当作新版端到端指标。

# Evaluation Summary: replay_smoke

## Run Info

- Input dir: `/Users/cmh/Documents/AGENT_project/evaluation/results/baseline_generated_complex_test_20260910_234250`
- Annotation dir: `None`
- Total samples: 5
- Success count: 5
- Failure count: 0
- Success rate: 100.00%
- Annotated samples: 5
- Avg latency: 3002.86 ms
- Needs confirmation rate: 0.00%

## Order-Level Accuracy

- `order_number`: 5/5 (100.00%)
- `customer_name`: 5/5 (100.00%)
- `total_amount`: 5/5 (100.00%)

## Item-Level Accuracy

- `material_name_raw`: 128/128 (100.00%)
- `specification_raw`: 128/128 (100.00%)
- `quantity`: 128/128 (100.00%)
- `unit`: 128/128 (100.00%)
- `unit_price`: 128/128 (100.00%)
- `delivery_date`: N/A (0/0)

## Extra Metrics

- Item count exact match: 5/5 (100.00%)
- SKU Top-1 accuracy: 128/128 (100.00%)
- Confirmation accuracy: 5/5 (100.00%)
- Business decision accuracy: 5/5 (100.00%)
- Error auto-release rate: 0/5 (0.00%)

## Content & Coverage Metrics

- Order content exact match (all samples): 5/5 (100.00%)
- Order content exact match (success only): 5/5 (100.00%)
- Auto-handle coverage: 5/5 (100.00%)
- Manual-review recall: N/A (0/0)
- Auto-release content-error rate: 0/5 (0.00%)

## Scoring Rules

- 行对齐：标签与预测按行序号一一对齐；标签有金标 SKU 而预测缺行时该行记为 SKU 错误。
- 额外行：预测行数多于标签时，多出的行参与字段与 SKU 比较，任一不符即计入错误。
- 漏行：标签行数多于预测时，缺失行按空预测参与比较，字段与 SKU 均记错。
- 内容正确：订单级字段、明细字段、行数与 SKU 全部命中才算整单内容正确。
- 口径：全样本指标（含技术失败）与技术成功后的条件指标分开展示；分母为 0 的指标显示 N/A。
- 技术失败不算自动放行，不计入自动放行相关指标的分母。

## Failures

- None


## SKU Coverage & Accepted-SKU Accuracy

- Golden-SKU items: 128
- Correct matches: 128
- Wrong accepts: 0
- Rejected (safe, no SKU delivered): 0
- Correct rejects (no golden SKU): 0
- Wrong accepts without golden SKU: 0
- Accepted-SKU coverage: 128/128 (100.00%)
- Accepted-SKU precision: 128/128 (100.00%)
- SKU accuracy: 128/128 (100.00%)

## High-Score Wrong SKU Recheck

- 阈值: match_score >= 0.8
- 旧版高分错 SKU 行数: 24
- 重放后: fixed 24、rejected 0、still_wrong 0

| document | line | golden | old_sku | old_score | new_sku | outcome |
| --- | ---: | --- | --- | ---: | --- | --- |
| `mfg_auto_approve_0009` | 24 | CBL-043 | CBL-003 | 0.999 | CBL-043 | fixed |
| `mfg_auto_approve_0009` | 26 | VLV-045 | VLV-050 | 0.9985 | VLV-045 | fixed |
| `mfg_auto_approve_0009` | 28 | VLV-012 | VLV-017 | 0.9986 | VLV-012 | fixed |
| `mfg_auto_approve_0010` | 6 | CBL-034 | CBL-014 | 0.9989 | CBL-034 | fixed |
| `mfg_auto_approve_0010` | 7 | CBL-054 | CBL-014 | 0.9989 | CBL-054 | fixed |
| `mfg_auto_approve_0010` | 11 | CBL-024 | CBL-004 | 0.999 | CBL-024 | fixed |
| `mfg_auto_approve_0010` | 12 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_auto_approve_0010` | 19 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_auto_approve_0010` | 20 | CBL-035 | CBL-015 | 0.9989 | CBL-035 | fixed |
| `mfg_auto_approve_0019` | 9 | VLV-002 | VLV-007 | 0.9984 | VLV-002 | fixed |
| `mfg_auto_approve_0019` | 10 | CBL-025 | CBL-005 | 0.999 | CBL-025 | fixed |
| `mfg_auto_approve_0019` | 12 | CBL-036 | CBL-016 | 0.9988 | CBL-036 | fixed |
| `mfg_auto_approve_0019` | 15 | SAF-032 | SAF-002 | 0.9112 | SAF-032 | fixed |
| `mfg_auto_approve_0019` | 23 | MET-046 | MET-031 | 0.9162 | MET-046 | fixed |
| `mfg_auto_approve_0019` | 25 | CBL-027 | CBL-007 | 0.999 | CBL-027 | fixed |
| `mfg_auto_approve_0020` | 1 | CBL-047 | CBL-007 | 0.999 | CBL-047 | fixed |
| `mfg_auto_approve_0020` | 3 | CBL-039 | CBL-019 | 0.999 | CBL-039 | fixed |
| `mfg_auto_approve_0020` | 4 | SAF-031 | SAF-001 | 0.9086 | SAF-031 | fixed |
| `mfg_auto_approve_0020` | 11 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_auto_approve_0020` | 15 | CBL-026 | CBL-006 | 0.999 | CBL-026 | fixed |
| `mfg_auto_approve_0020` | 20 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_auto_approve_0020` | 21 | VLV-015 | VLV-020 | 0.9984 | VLV-015 | fixed |
| `mfg_auto_approve_0029` | 1 | CBL-051 | CBL-011 | 0.9989 | CBL-051 | fixed |
| `mfg_auto_approve_0029` | 3 | SAF-046 | SAF-016 | 0.9007 | SAF-046 | fixed |

## Rejected Detailed Items

- None
