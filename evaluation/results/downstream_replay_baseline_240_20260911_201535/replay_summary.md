# 下游重放报告（非端到端）: downstream_replay_baseline_240

- 固定旧版解析结果来源: `/Users/cmh/Documents/AGENT_project/evaluation/results/baseline_generated_complex_test_20260910_234250/predictions.jsonl`
- 本报告固定旧 ParsedOrder，只重放当前 Matching / Risk / 业务动作；
  不经过 Parser、自纠错、HTTP、数据库，也不调用 Qwen。
- 不得把本报告的数字当作新版端到端指标。

# Evaluation Summary: downstream_replay_baseline_240

## Run Info

- Input dir: `/Users/cmh/Documents/AGENT_project/evaluation/results/baseline_generated_complex_test_20260910_234250`
- Annotation dir: `None`
- Total samples: 240
- Success count: 240
- Failure count: 0
- Success rate: 100.00%
- Annotated samples: 240
- Avg latency: 554.61 ms
- Needs confirmation rate: 66.67%

## Order-Level Accuracy

- `order_number`: 240/240 (100.00%)
- `customer_name`: 240/240 (100.00%)
- `total_amount`: 240/240 (100.00%)

## Item-Level Accuracy

- `material_name_raw`: 5869/5882 (99.78%)
- `specification_raw`: 5838/5882 (99.25%)
- `quantity`: 5882/5882 (100.00%)
- `unit`: 5882/5882 (100.00%)
- `unit_price`: 5882/5882 (100.00%)
- `delivery_date`: N/A (0/0)

## Extra Metrics

- Item count exact match: 240/240 (100.00%)
- SKU Top-1 accuracy: 5668/5882 (96.36%)
- Confirmation accuracy: 154/240 (64.17%)
- Business decision accuracy: 154/240 (64.17%)
- Error auto-release rate: 3/240 (1.25%)

## Content & Coverage Metrics

- Order content exact match (all samples): 116/240 (48.33%)
- Order content exact match (success only): 116/240 (48.33%)
- Auto-handle coverage: 80/240 (33.33%)
- Manual-review recall: 77/80 (96.25%)
- Auto-release content-error rate: 0/80 (0.00%)

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

- Golden-SKU items: 5856
- Correct matches: 5642
- Wrong accepts: 0
- Rejected (safe, no SKU delivered): 214
- Correct rejects (no golden SKU): 26
- Wrong accepts without golden SKU: 0
- Accepted-SKU coverage: 5642/5856 (96.35%)
- Accepted-SKU precision: 5642/5642 (100.00%)
- SKU accuracy: 5642/5856 (96.35%)

## High-Score Wrong SKU Recheck

- 阈值: match_score >= 0.8
- 旧版高分错 SKU 行数: 1037
- 重放后: fixed 979、rejected 58、still_wrong 0

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
| `mfg_auto_approve_0030` | 7 | SAF-049 | SAF-019 | 0.9358 | SAF-049 | fixed |
| `mfg_auto_approve_0030` | 16 | MET-039 | MET-019 | 0.9247 | MET-039 | fixed |
| `mfg_auto_approve_0030` | 17 | SAF-058 | SAF-028 | 0.9087 | SAF-058 | fixed |
| `mfg_auto_approve_0039` | 3 | MET-059 | MET-029 | 0.9171 | MET-059 | fixed |
| `mfg_auto_approve_0039` | 4 | MET-015 | MET-020 | 0.9247 | MET-015 | fixed |
| `mfg_auto_approve_0039` | 6 | VLV-014 | VLV-019 | 0.9981 | VLV-014 | fixed |
| `mfg_auto_approve_0039` | 8 | VLV-054 | VLV-059 | 0.9983 | VLV-054 | fixed |
| `mfg_auto_approve_0039` | 12 | SAF-050 | SAF-020 | 0.9229 | SAF-050 | fixed |
| `mfg_auto_approve_0039` | 25 | MET-008 | MET-018 | 0.9238 | MET-008 | fixed |
| `mfg_auto_approve_0040` | 3 | CBL-060 | CBL-020 | 0.9989 | CBL-060 | fixed |
| `mfg_auto_approve_0040` | 12 | CBL-038 | CBL-018 | 0.999 | CBL-038 | fixed |
| `mfg_auto_approve_0040` | 13 | VLV-042 | VLV-047 | 0.9987 | VLV-042 | fixed |
| `mfg_auto_approve_0040` | 15 | VLV-041 | VLV-046 | 0.9986 | VLV-041 | fixed |
| `mfg_auto_approve_0049` | 2 | CBL-032 | CBL-012 | 0.9989 | CBL-032 | fixed |
| `mfg_auto_approve_0049` | 19 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_auto_approve_0049` | 21 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_auto_approve_0049` | 22 | CBL-022 | CBL-002 | 0.9991 | CBL-022 | fixed |
| `mfg_auto_approve_0049` | 28 | MET-012 | MET-017 | 0.9296 | MET-012 | fixed |
| `mfg_auto_approve_0050` | 10 | SAF-059 | SAF-029 | 0.9343 | SAF-059 | fixed |
| `mfg_auto_approve_0050` | 15 | CBL-051 | CBL-011 | 0.9989 | CBL-051 | fixed |
| `mfg_auto_approve_0050` | 22 | CBL-035 | CBL-015 | 0.9989 | CBL-035 | fixed |
| `mfg_auto_approve_0050` | 27 | SAF-046 | SAF-016 | 0.9007 | SAF-046 | fixed |
| `mfg_auto_approve_0059` | 6 | VLV-001 | VLV-006 | 0.9983 | VLV-001 | fixed |
| `mfg_auto_approve_0059` | 10 | SAF-057 | SAF-027 | 0.9033 | SAF-057 | fixed |
| `mfg_auto_approve_0059` | 12 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_auto_approve_0059` | 13 | MET-010 | MET-020 | 0.925 | MET-010 | fixed |
| `mfg_auto_approve_0059` | 14 | CBL-023 | CBL-003 | 0.999 | CBL-023 | fixed |
| `mfg_auto_approve_0059` | 17 | VLV-002 | VLV-007 | 0.9984 | VLV-002 | fixed |
| `mfg_auto_approve_0060` | 5 | VLV-003 | VLV-008 | 0.9982 | VLV-003 | fixed |
| `mfg_auto_approve_0060` | 7 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_auto_approve_0060` | 8 | CBL-052 | CBL-012 | 0.9989 | CBL-052 | fixed |
| `mfg_auto_approve_0060` | 11 | SAF-058 | SAF-028 | 0.9087 | SAF-058 | fixed |
| `mfg_auto_approve_0060` | 18 | SAF-049 | SAF-019 | 0.9358 | SAF-049 | fixed |
| `mfg_auto_approve_0060` | 21 | SAF-057 | SAF-027 | 0.9033 | SAF-057 | fixed |
| `mfg_auto_approve_0060` | 22 | VLV-033 | VLV-038 | 0.9987 | VLV-033 | fixed |
| `mfg_auto_approve_0069` | 8 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_auto_approve_0069` | 9 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_auto_approve_0069` | 14 | CBL-039 | CBL-019 | 0.999 | CBL-039 | fixed |
| `mfg_auto_approve_0070` | 13 | VLV-055 | VLV-060 | 0.9986 | VLV-055 | fixed |
| `mfg_auto_approve_0070` | 14 | VLV-031 | VLV-036 | 0.9987 | VLV-031 | fixed |
| `mfg_auto_approve_0070` | 21 | CBL-024 | CBL-004 | 0.999 | CBL-024 | fixed |
| `mfg_auto_approve_0070` | 25 | CBL-044 | CBL-004 | 0.999 | CBL-044 | fixed |
| `mfg_auto_approve_0079` | 8 | SAF-047 | SAF-017 | 0.9051 | SAF-047 | fixed |
| `mfg_auto_approve_0079` | 15 | MET-006 | MET-016 | 0.9233 | MET-006 | fixed |
| `mfg_auto_approve_0079` | 19 | VLV-034 | VLV-039 | 0.9983 | VLV-034 | fixed |
| `mfg_auto_approve_0080` | 13 | MET-012 | MET-017 | 0.9296 | MET-012 | fixed |
| `mfg_auto_approve_0089` | 1 | MET-049 | MET-034 | 0.9165 | MET-049 | fixed |
| `mfg_auto_approve_0089` | 3 | MET-059 | MET-029 | 0.9171 | MET-059 | fixed |
| `mfg_auto_approve_0089` | 4 | SAF-041 | SAF-011 | 0.9044 | SAF-041 | fixed |
| `mfg_auto_approve_0089` | 11 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_auto_approve_0089` | 13 | CBL-030 | CBL-010 | 0.999 | CBL-030 | fixed |
| `mfg_auto_approve_0089` | 19 | MET-055 | MET-020 | 0.9191 | MET-055 | fixed |
| `mfg_auto_approve_0089` | 22 | CBL-057 | CBL-017 | 0.999 | CBL-057 | fixed |
| `mfg_auto_approve_0089` | 24 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_auto_approve_0090` | 8 | VLV-052 | VLV-057 | 0.9988 | VLV-052 | fixed |
| `mfg_auto_approve_0099` | 6 | SAF-043 | SAF-013 | 0.9133 | SAF-043 | fixed |
| `mfg_auto_approve_0099` | 7 | MET-013 | MET-028 | 0.9254 | MET-013 | fixed |
| `mfg_auto_approve_0099` | 10 | CBL-042 | CBL-002 | 0.9991 | CBL-042 | fixed |
| `mfg_auto_approve_0099` | 27 | MET-047 | MET-017 | 0.924 | MET-047 | fixed |
| `mfg_auto_approve_0100` | 14 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_auto_approve_0100` | 19 | VLV-055 | VLV-060 | 0.9986 | VLV-055 | fixed |
| `mfg_auto_approve_0100` | 20 | MET-053 | MET-018 | 0.9181 | MET-053 | fixed |
| `mfg_auto_approve_0109` | 2 | VLV-015 | VLV-020 | 0.9984 | VLV-015 | fixed |
| `mfg_auto_approve_0109` | 7 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_auto_approve_0109` | 14 | CBL-048 | CBL-008 | 0.999 | CBL-048 | fixed |
| `mfg_auto_approve_0110` | 15 | CBL-057 | CBL-017 | 0.999 | CBL-057 | fixed |
| `mfg_auto_approve_0110` | 28 | SAF-046 | SAF-016 | 0.9007 | SAF-046 | fixed |
| `mfg_auto_approve_0119` | 9 | VLV-032 | VLV-037 | 0.9987 | VLV-032 | fixed |
| `mfg_auto_approve_0119` | 10 | CBL-046 | CBL-006 | 0.999 | CBL-046 | fixed |
| `mfg_auto_approve_0119` | 16 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_auto_approve_0119` | 19 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_auto_approve_0119` | 22 | SAF-060 | SAF-030 | 0.923 | SAF-060 | fixed |
| `mfg_auto_approve_0120` | 22 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_auto_approve_0120` | 26 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_auto_approve_0129` | 1 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_auto_approve_0129` | 5 | CBL-053 | CBL-013 | 0.999 | CBL-053 | fixed |
| `mfg_auto_approve_0129` | 8 | MET-007 | MET-017 | 0.9294 | MET-007 | fixed |
| `mfg_auto_approve_0129` | 10 | CBL-055 | CBL-015 | 0.9989 | CBL-055 | fixed |
| `mfg_auto_approve_0129` | 14 | MET-012 | MET-017 | 0.9296 | MET-012 | fixed |
| `mfg_auto_approve_0129` | 17 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_auto_approve_0129` | 21 | VLV-052 | VLV-057 | 0.9988 | VLV-052 | fixed |
| `mfg_auto_approve_0130` | 3 | CBL-039 | CBL-019 | 0.999 | CBL-039 | fixed |
| `mfg_auto_approve_0130` | 4 | SAF-026 | SAF-030 | 0.8975 | SAF-026 | fixed |
| `mfg_auto_approve_0130` | 10 | CBL-034 | CBL-014 | 0.9989 | CBL-034 | fixed |
| `mfg_auto_approve_0130` | 13 | MET-060 | MET-030 | 0.9167 | MET-060 | fixed |
| `mfg_auto_approve_0130` | 19 | CBL-025 | CBL-005 | 0.999 | CBL-025 | fixed |
| `mfg_auto_approve_0130` | 24 | SAF-033 | SAF-003 | 0.9156 | SAF-033 | fixed |
| `mfg_auto_approve_0139` | 9 | CBL-058 | CBL-018 | 0.999 | CBL-058 | fixed |
| `mfg_auto_approve_0139` | 17 | SAF-040 | SAF-010 | 0.9334 | SAF-040 | fixed |
| `mfg_auto_approve_0139` | 18 | MET-048 | MET-018 | 0.9148 | MET-048 | fixed |
| `mfg_auto_approve_0139` | 22 | MET-053 | MET-018 | 0.9181 | MET-053 | fixed |
| `mfg_auto_approve_0140` | 4 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_auto_approve_0140` | 5 | VLV-013 | VLV-018 | 0.9983 | VLV-013 | fixed |
| `mfg_auto_approve_0140` | 6 | SAF-034 | SAF-004 | 0.9405 | SAF-034 | fixed |
| `mfg_auto_approve_0140` | 14 | CBL-023 | CBL-003 | 0.999 | CBL-023 | fixed |
| `mfg_auto_approve_0140` | 22 | SAF-031 | SAF-001 | 0.9086 | SAF-031 | fixed |
| `mfg_auto_approve_0140` | 23 | CBL-057 | CBL-017 | 0.999 | CBL-057 | fixed |
| `mfg_auto_approve_0149` | 5 | CBL-044 | CBL-004 | 0.999 | CBL-044 | fixed |
| `mfg_auto_approve_0149` | 8 | SAF-032 | SAF-002 | 0.9112 | SAF-032 | fixed |
| `mfg_auto_approve_0149` | 9 | CBL-050 | CBL-010 | 0.999 | CBL-050 | fixed |
| `mfg_auto_approve_0149` | 12 | MET-037 | MET-017 | 0.9308 | MET-037 | fixed |
| `mfg_auto_approve_0149` | 13 | CBL-039 | CBL-019 | 0.999 | CBL-039 | fixed |
| `mfg_auto_approve_0149` | 21 | VLV-051 | VLV-056 | 0.9987 | VLV-051 | fixed |
| `mfg_auto_approve_0150` | 15 | CBL-028 | CBL-008 | 0.999 | CBL-028 | fixed |
| `mfg_auto_approve_0150` | 20 | MET-040 | MET-020 | 0.924 | MET-040 | fixed |
| `mfg_auto_approve_0159` | 2 | SAF-041 | SAF-011 | 0.9044 | SAF-041 | fixed |
| `mfg_auto_approve_0159` | 6 | SAF-060 | SAF-030 | 0.923 | SAF-060 | fixed |
| `mfg_auto_approve_0159` | 12 | VLV-031 | VLV-036 | 0.9987 | VLV-031 | fixed |
| `mfg_auto_approve_0159` | 16 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_auto_approve_0159` | 17 | SAF-055 | SAF-025 | 0.9332 | SAF-055 | fixed |
| `mfg_auto_approve_0159` | 19 | CBL-036 | CBL-016 | 0.9988 | CBL-036 | fixed |
| `mfg_auto_approve_0160` | 13 | MET-009 | MET-019 | 0.9259 | MET-009 | fixed |
| `mfg_auto_approve_0160` | 22 | SAF-034 | SAF-004 | 0.9405 | SAF-034 | fixed |
| `mfg_auto_approve_0160` | 28 | CBL-058 | CBL-018 | 0.999 | CBL-058 | fixed |
| `mfg_auto_approve_0160` | 30 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_auto_approve_0169` | 3 | VLV-053 | VLV-058 | 0.9987 | VLV-053 | fixed |
| `mfg_auto_approve_0169` | 9 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_auto_approve_0169` | 11 | CBL-044 | CBL-004 | 0.999 | CBL-044 | fixed |
| `mfg_auto_approve_0169` | 16 | MET-008 | MET-018 | 0.9238 | MET-008 | fixed |
| `mfg_auto_approve_0169` | 18 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_auto_approve_0170` | 3 | SAF-041 | SAF-011 | 0.9044 | SAF-041 | fixed |
| `mfg_auto_approve_0170` | 7 | MET-040 | MET-020 | 0.924 | MET-040 | fixed |
| `mfg_auto_approve_0170` | 22 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_auto_approve_0179` | 1 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_auto_approve_0179` | 3 | VLV-052 | VLV-057 | 0.9988 | VLV-052 | fixed |
| `mfg_auto_approve_0179` | 5 | SAF-026 | SAF-030 | 0.8975 | SAF-026 | fixed |
| `mfg_auto_approve_0179` | 10 | MET-060 | MET-030 | 0.9167 | MET-060 | fixed |
| `mfg_auto_approve_0179` | 15 | VLV-034 | VLV-039 | 0.9983 | VLV-034 | fixed |
| `mfg_auto_approve_0179` | 19 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_auto_approve_0179` | 25 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_auto_approve_0179` | 26 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_auto_approve_0179` | 30 | CBL-038 | CBL-018 | 0.999 | CBL-038 | fixed |
| `mfg_auto_approve_0180` | 2 | MET-059 | MET-029 | 0.9171 | MET-059 | fixed |
| `mfg_auto_approve_0180` | 7 | VLV-032 | VLV-037 | 0.9987 | VLV-032 | fixed |
| `mfg_auto_approve_0180` | 11 | SAF-041 | SAF-011 | 0.9044 | SAF-041 | fixed |
| `mfg_auto_approve_0180` | 18 | MET-010 | MET-020 | 0.925 | MET-010 | fixed |
| `mfg_auto_approve_0189` | 6 | SAF-036 | SAF-006 | 0.9147 | SAF-036 | fixed |
| `mfg_auto_approve_0189` | 7 | CBL-058 | CBL-018 | 0.999 | CBL-058 | fixed |
| `mfg_auto_approve_0189` | 13 | VLV-002 | VLV-007 | 0.9984 | VLV-002 | fixed |
| `mfg_auto_approve_0190` | 1 | CBL-051 | CBL-011 | 0.9989 | CBL-051 | fixed |
| `mfg_auto_approve_0190` | 7 | CBL-047 | CBL-007 | 0.999 | CBL-047 | fixed |
| `mfg_auto_approve_0190` | 12 | MET-056 | MET-026 | 0.917 | MET-056 | fixed |
| `mfg_auto_approve_0190` | 18 | SAF-045 | SAF-015 | 0.925 | SAF-045 | fixed |
| `mfg_auto_approve_0190` | 20 | SAF-026 | SAF-030 | 0.8975 | SAF-026 | fixed |
| `mfg_auto_approve_0199` | 5 | VLV-004 | VLV-009 | 0.9979 | VLV-004 | fixed |
| `mfg_auto_approve_0199` | 6 | SAF-043 | SAF-013 | 0.9133 | SAF-043 | fixed |
| `mfg_auto_approve_0199` | 13 | MET-053 | MET-018 | 0.9181 | MET-053 | fixed |
| `mfg_auto_approve_0199` | 15 | VLV-014 | VLV-019 | 0.9981 | VLV-014 | fixed |
| `mfg_auto_approve_0199` | 20 | MET-055 | MET-020 | 0.9191 | MET-055 | fixed |
| `mfg_auto_approve_0200` | 1 | VLV-033 | VLV-038 | 0.9987 | VLV-033 | fixed |
| `mfg_auto_approve_0200` | 2 | MET-047 | MET-017 | 0.924 | MET-047 | fixed |
| `mfg_auto_approve_0200` | 16 | MET-006 | MET-016 | 0.9233 | MET-006 | fixed |
| `mfg_auto_approve_0200` | 20 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_auto_approve_0200` | 22 | CBL-060 | CBL-020 | 0.9989 | CBL-060 | fixed |
| `mfg_auto_approve_0209` | 3 | MET-046 | MET-031 | 0.9162 | MET-046 | fixed |
| `mfg_auto_approve_0209` | 8 | CBL-056 | CBL-016 | 0.9988 | CBL-056 | fixed |
| `mfg_auto_approve_0209` | 10 | CBL-034 | CBL-014 | 0.9989 | CBL-034 | fixed |
| `mfg_auto_approve_0209` | 15 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_auto_approve_0209` | 25 | SAF-056 | SAF-030 | 0.8975 | SAF-056 | fixed |
| `mfg_auto_approve_0209` | 27 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_auto_approve_0209` | 28 | VLV-033 | VLV-038 | 0.9987 | VLV-033 | fixed |
| `mfg_auto_approve_0210` | 14 | CBL-050 | CBL-010 | 0.999 | CBL-050 | fixed |
| `mfg_auto_approve_0210` | 23 | VLV-044 | VLV-049 | 0.9981 | VLV-044 | fixed |
| `mfg_auto_approve_0210` | 24 | SAF-039 | SAF-009 | 0.9429 | SAF-039 | fixed |
| `mfg_auto_approve_0219` | 1 | CBL-031 | CBL-011 | 0.9989 | CBL-031 | fixed |
| `mfg_auto_approve_0219` | 15 | MET-051 | MET-016 | 0.9185 | MET-051 | fixed |
| `mfg_auto_approve_0219` | 17 | CBL-049 | CBL-009 | 0.999 | CBL-049 | fixed |
| `mfg_auto_approve_0219` | 24 | MET-049 | MET-034 | 0.9165 | MET-049 | fixed |
| `mfg_auto_approve_0220` | 4 | SAF-037 | SAF-007 | 0.9186 | SAF-037 | fixed |
| `mfg_auto_approve_0220` | 9 | SAF-038 | SAF-008 | 0.9218 | SAF-038 | fixed |
| `mfg_auto_approve_0220` | 17 | SAF-039 | SAF-009 | 0.9429 | SAF-039 | fixed |
| `mfg_auto_approve_0229` | 10 | CBL-055 | CBL-015 | 0.9989 | CBL-055 | fixed |
| `mfg_auto_approve_0229` | 12 | VLV-021 | VLV-026 | 0.9986 | VLV-021 | fixed |
| `mfg_auto_approve_0229` | 23 | CBL-058 | CBL-018 | 0.999 | CBL-058 | fixed |
| `mfg_auto_approve_0230` | 15 | SAF-056 | SAF-030 | 0.8975 | SAF-056 | fixed |
| `mfg_auto_approve_0230` | 20 | MET-008 | MET-018 | 0.9238 | MET-008 | fixed |
| `mfg_auto_approve_0230` | 24 | CBL-026 | CBL-006 | 0.999 | CBL-026 | fixed |
| `mfg_auto_approve_0239` | 2 | CBL-050 | CBL-010 | 0.999 | CBL-050 | fixed |
| `mfg_auto_approve_0239` | 3 | SAF-037 | SAF-007 | 0.9186 | SAF-037 | fixed |
| `mfg_auto_approve_0240` | 2 | SAF-040 | SAF-010 | 0.9334 | SAF-040 | fixed |
| `mfg_auto_approve_0240` | 3 | VLV-002 | VLV-007 | 0.9984 | VLV-002 | fixed |
| `mfg_auto_approve_0240` | 4 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_auto_approve_0240` | 13 | SAF-054 | SAF-024 | 0.9441 | SAF-054 | fixed |
| `mfg_auto_approve_0240` | 19 | CBL-057 | CBL-017 | 0.999 | CBL-057 | fixed |
| `mfg_auto_approve_0249` | 6 | CBL-025 | CBL-005 | 0.999 | CBL-025 | fixed |
| `mfg_auto_approve_0249` | 19 | CBL-024 | CBL-004 | 0.999 | CBL-024 | fixed |
| `mfg_auto_approve_0250` | 8 | SAF-026 | SAF-030 | 0.8975 | SAF-026 | fixed |
| `mfg_auto_approve_0250` | 10 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_auto_approve_0250` | 18 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_auto_approve_0250` | 21 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_auto_approve_0250` | 24 | SAF-057 | SAF-027 | 0.9033 | SAF-057 | fixed |
| `mfg_auto_approve_0250` | 26 | SAF-032 | SAF-002 | 0.9112 | SAF-032 | fixed |
| `mfg_auto_approve_0259` | 14 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_auto_approve_0260` | 3 | ELC-001 | ELC-025 | 0.984 | - | rejected |
| `mfg_auto_approve_0260` | 11 | CBL-042 | CBL-002 | 0.9991 | CBL-042 | fixed |
| `mfg_auto_approve_0260` | 13 | VLV-021 | VLV-026 | 0.9986 | VLV-021 | fixed |
| `mfg_auto_approve_0260` | 15 | VLV-033 | VLV-038 | 0.9987 | VLV-033 | fixed |
| `mfg_auto_approve_0260` | 16 | CBL-025 | CBL-005 | 0.999 | CBL-025 | fixed |
| `mfg_auto_approve_0260` | 22 | SAF-050 | SAF-020 | 0.9229 | SAF-050 | fixed |
| `mfg_auto_approve_0269` | 2 | MET-006 | MET-016 | 0.9233 | MET-006 | fixed |
| `mfg_auto_approve_0269` | 10 | CBL-044 | CBL-004 | 0.999 | CBL-044 | fixed |
| `mfg_auto_approve_0269` | 12 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_auto_approve_0269` | 14 | VLV-004 | VLV-009 | 0.9979 | VLV-004 | fixed |
| `mfg_auto_approve_0269` | 17 | CBL-045 | CBL-005 | 0.999 | CBL-045 | fixed |
| `mfg_auto_approve_0269` | 21 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_auto_approve_0269` | 23 | SAF-059 | SAF-029 | 0.9343 | SAF-059 | fixed |
| `mfg_auto_approve_0269` | 24 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_auto_approve_0270` | 4 | VLV-005 | VLV-010 | 0.9983 | VLV-005 | fixed |
| `mfg_auto_approve_0270` | 20 | SAF-045 | SAF-015 | 0.925 | SAF-045 | fixed |
| `mfg_auto_approve_0279` | 9 | CBL-042 | CBL-002 | 0.9991 | CBL-042 | fixed |
| `mfg_auto_approve_0279` | 13 | VLV-042 | VLV-047 | 0.9987 | VLV-042 | fixed |
| `mfg_auto_approve_0279` | 22 | SAF-036 | SAF-006 | 0.9147 | SAF-036 | fixed |
| `mfg_auto_approve_0280` | 2 | CBL-060 | CBL-020 | 0.9989 | CBL-060 | fixed |
| `mfg_auto_approve_0280` | 13 | SAF-041 | SAF-011 | 0.9044 | SAF-041 | fixed |
| `mfg_auto_approve_0280` | 14 | CBL-053 | CBL-013 | 0.999 | CBL-053 | fixed |
| `mfg_auto_approve_0280` | 15 | VLV-022 | VLV-027 | 0.9985 | VLV-022 | fixed |
| `mfg_auto_approve_0289` | 3 | MET-040 | MET-020 | 0.924 | MET-040 | fixed |
| `mfg_auto_approve_0289` | 8 | CBL-050 | CBL-010 | 0.999 | CBL-050 | fixed |
| `mfg_auto_approve_0289` | 11 | ELC-008 | ELC-032 | 0.9821 | - | rejected |
| `mfg_auto_approve_0289` | 16 | VLV-051 | VLV-056 | 0.9987 | VLV-051 | fixed |
| `mfg_auto_approve_0289` | 19 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_auto_approve_0289` | 20 | VLV-045 | VLV-050 | 0.9985 | VLV-045 | fixed |
| `mfg_auto_approve_0290` | 1 | MET-056 | MET-026 | 0.917 | MET-056 | fixed |
| `mfg_auto_approve_0290` | 2 | CBL-052 | CBL-012 | 0.9989 | CBL-052 | fixed |
| `mfg_auto_approve_0290` | 8 | VLV-052 | VLV-057 | 0.9988 | VLV-052 | fixed |
| `mfg_auto_approve_0290` | 16 | VLV-023 | VLV-028 | 0.9986 | VLV-023 | fixed |
| `mfg_auto_approve_0290` | 21 | MET-047 | MET-017 | 0.924 | MET-047 | fixed |
| `mfg_auto_approve_0290` | 22 | MET-014 | MET-029 | 0.9262 | MET-014 | fixed |
| `mfg_auto_approve_0299` | 13 | VLV-021 | VLV-026 | 0.9986 | VLV-021 | fixed |
| `mfg_auto_approve_0299` | 18 | CBL-035 | CBL-015 | 0.9989 | CBL-035 | fixed |
| `mfg_auto_approve_0299` | 20 | SAF-054 | SAF-024 | 0.9441 | SAF-054 | fixed |
| `mfg_auto_approve_0300` | 14 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_auto_approve_0300` | 19 | VLV-055 | VLV-060 | 0.9986 | VLV-055 | fixed |
| `mfg_auto_approve_0300` | 25 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_auto_approve_0300` | 26 | SAF-038 | SAF-008 | 0.9218 | SAF-038 | fixed |
| `mfg_auto_approve_0309` | 3 | CBL-044 | CBL-004 | 0.999 | CBL-044 | fixed |
| `mfg_auto_approve_0309` | 5 | CBL-041 | CBL-001 | 0.9991 | CBL-041 | fixed |
| `mfg_auto_approve_0309` | 7 | VLV-012 | VLV-017 | 0.9986 | VLV-012 | fixed |
| `mfg_auto_approve_0309` | 9 | VLV-014 | VLV-019 | 0.9981 | VLV-014 | fixed |
| `mfg_auto_approve_0309` | 13 | MET-008 | MET-018 | 0.9238 | MET-008 | fixed |
| `mfg_auto_approve_0310` | 2 | VLV-034 | VLV-039 | 0.9983 | VLV-034 | fixed |
| `mfg_auto_approve_0310` | 10 | SAF-059 | SAF-029 | 0.9343 | SAF-059 | fixed |
| `mfg_auto_approve_0310` | 13 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_auto_approve_0319` | 16 | CBL-040 | CBL-020 | 0.9989 | CBL-040 | fixed |
| `mfg_auto_approve_0319` | 24 | SAF-031 | SAF-001 | 0.9086 | SAF-031 | fixed |
| `mfg_auto_approve_0319` | 26 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_auto_approve_0320` | 10 | MET-056 | MET-026 | 0.917 | MET-056 | fixed |
| `mfg_auto_approve_0320` | 18 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_auto_approve_0329` | 4 | CBL-045 | CBL-005 | 0.999 | CBL-045 | fixed |
| `mfg_auto_approve_0329` | 12 | MET-015 | MET-020 | 0.9247 | MET-015 | fixed |
| `mfg_auto_approve_0329` | 17 | CBL-052 | CBL-012 | 0.9989 | CBL-052 | fixed |
| `mfg_auto_approve_0329` | 19 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_auto_approve_0329` | 22 | CBL-050 | CBL-010 | 0.999 | CBL-050 | fixed |
| `mfg_auto_approve_0329` | 25 | VLV-014 | VLV-019 | 0.9981 | VLV-014 | fixed |
| `mfg_auto_approve_0330` | 4 | MET-059 | MET-029 | 0.9171 | MET-059 | fixed |
| `mfg_auto_approve_0330` | 13 | CBL-028 | CBL-008 | 0.999 | CBL-028 | fixed |
| `mfg_auto_approve_0330` | 19 | CBL-043 | CBL-003 | 0.999 | CBL-043 | fixed |
| `mfg_auto_approve_0330` | 21 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_auto_approve_0339` | 3 | MET-007 | MET-017 | 0.9294 | MET-007 | fixed |
| `mfg_auto_approve_0339` | 15 | MET-039 | MET-019 | 0.9247 | MET-039 | fixed |
| `mfg_auto_approve_0339` | 16 | CBL-032 | CBL-012 | 0.9989 | CBL-032 | fixed |
| `mfg_auto_approve_0339` | 21 | MET-040 | MET-020 | 0.924 | MET-040 | fixed |
| `mfg_auto_approve_0340` | 12 | MET-051 | MET-016 | 0.9185 | MET-051 | fixed |
| `mfg_auto_approve_0340` | 14 | VLV-044 | VLV-049 | 0.9981 | VLV-044 | fixed |
| `mfg_auto_approve_0340` | 21 | CBL-046 | CBL-006 | 0.999 | CBL-046 | fixed |
| `mfg_auto_approve_0340` | 24 | VLV-034 | VLV-039 | 0.9983 | VLV-034 | fixed |
| `mfg_auto_approve_0349` | 6 | SAF-046 | SAF-016 | 0.9007 | SAF-046 | fixed |
| `mfg_auto_approve_0349` | 8 | VLV-031 | VLV-036 | 0.9987 | VLV-031 | fixed |
| `mfg_auto_approve_0349` | 10 | CBL-059 | CBL-019 | 0.999 | CBL-059 | fixed |
| `mfg_auto_approve_0349` | 18 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_auto_approve_0349` | 19 | CBL-052 | CBL-012 | 0.9989 | CBL-052 | fixed |
| `mfg_auto_approve_0349` | 21 | SAF-036 | SAF-006 | 0.9147 | SAF-036 | fixed |
| `mfg_auto_approve_0350` | 20 | ELC-038 | ELC-026 | 0.9821 | - | rejected |
| `mfg_auto_approve_0359` | 8 | CBL-026 | CBL-006 | 0.999 | CBL-026 | fixed |
| `mfg_auto_approve_0359` | 10 | CBL-039 | CBL-019 | 0.999 | CBL-039 | fixed |
| `mfg_auto_approve_0359` | 11 | MET-046 | MET-031 | 0.9162 | MET-046 | fixed |
| `mfg_auto_approve_0359` | 15 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_auto_approve_0359` | 21 | VLV-002 | VLV-007 | 0.9984 | VLV-002 | fixed |
| `mfg_auto_approve_0360` | 7 | CBL-031 | CBL-011 | 0.9989 | CBL-031 | fixed |
| `mfg_auto_approve_0360` | 15 | CBL-049 | CBL-009 | 0.999 | CBL-049 | fixed |
| `mfg_auto_approve_0360` | 21 | VLV-053 | VLV-058 | 0.9987 | VLV-053 | fixed |
| `mfg_auto_approve_0360` | 25 | SAF-032 | SAF-002 | 0.9112 | SAF-032 | fixed |
| `mfg_auto_approve_0369` | 9 | SAF-045 | SAF-015 | 0.925 | SAF-045 | fixed |
| `mfg_auto_approve_0369` | 21 | SAF-036 | SAF-006 | 0.9147 | SAF-036 | fixed |
| `mfg_auto_approve_0369` | 26 | MET-006 | MET-016 | 0.9233 | MET-006 | fixed |
| `mfg_auto_approve_0370` | 7 | MET-039 | MET-019 | 0.9247 | MET-039 | fixed |
| `mfg_auto_approve_0370` | 9 | MET-057 | MET-027 | 0.9244 | MET-057 | fixed |
| `mfg_auto_approve_0370` | 17 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_auto_approve_0370` | 18 | MET-015 | MET-020 | 0.9247 | MET-015 | fixed |
| `mfg_auto_approve_0379` | 4 | CBL-050 | CBL-010 | 0.999 | CBL-050 | fixed |
| `mfg_auto_approve_0379` | 6 | VLV-032 | VLV-037 | 0.9987 | VLV-032 | fixed |
| `mfg_auto_approve_0379` | 11 | CBL-056 | CBL-016 | 0.9988 | CBL-056 | fixed |
| `mfg_auto_approve_0379` | 13 | CBL-045 | CBL-005 | 0.999 | CBL-045 | fixed |
| `mfg_auto_approve_0379` | 18 | SAF-059 | SAF-029 | 0.9343 | SAF-059 | fixed |
| `mfg_auto_approve_0379` | 21 | MET-052 | MET-017 | 0.9278 | MET-052 | fixed |
| `mfg_auto_approve_0379` | 23 | MET-015 | MET-020 | 0.9247 | MET-015 | fixed |
| `mfg_auto_approve_0379` | 28 | SAF-054 | SAF-024 | 0.9441 | SAF-054 | fixed |
| `mfg_auto_approve_0380` | 3 | CBL-048 | CBL-008 | 0.999 | CBL-048 | fixed |
| `mfg_auto_approve_0380` | 9 | VLV-032 | VLV-037 | 0.9987 | VLV-032 | fixed |
| `mfg_auto_approve_0380` | 12 | SAF-031 | SAF-001 | 0.9086 | SAF-031 | fixed |
| `mfg_auto_approve_0380` | 15 | VLV-002 | VLV-007 | 0.9984 | VLV-002 | fixed |
| `mfg_auto_approve_0380` | 19 | CBL-059 | CBL-019 | 0.999 | CBL-059 | fixed |
| `mfg_auto_approve_0380` | 22 | CBL-056 | CBL-016 | 0.9988 | CBL-056 | fixed |
| `mfg_auto_approve_0380` | 23 | MET-009 | MET-019 | 0.9259 | MET-009 | fixed |
| `mfg_auto_approve_0389` | 2 | VLV-011 | VLV-016 | 0.9984 | VLV-011 | fixed |
| `mfg_auto_approve_0389` | 5 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_auto_approve_0389` | 8 | CBL-023 | CBL-003 | 0.999 | CBL-023 | fixed |
| `mfg_auto_approve_0389` | 14 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_auto_approve_0389` | 19 | CBL-049 | CBL-009 | 0.999 | CBL-049 | fixed |
| `mfg_auto_approve_0390` | 2 | MET-056 | MET-026 | 0.917 | MET-056 | fixed |
| `mfg_auto_approve_0390` | 13 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_auto_approve_0390` | 17 | CBL-042 | CBL-002 | 0.9991 | CBL-042 | fixed |
| `mfg_auto_approve_0390` | 22 | VLV-041 | VLV-046 | 0.9986 | VLV-041 | fixed |
| `mfg_auto_approve_0399` | 1 | VLV-004 | VLV-009 | 0.9979 | VLV-004 | fixed |
| `mfg_auto_approve_0399` | 8 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_auto_approve_0399` | 10 | VLV-033 | VLV-038 | 0.9987 | VLV-033 | fixed |
| `mfg_auto_approve_0399` | 19 | SAF-040 | SAF-010 | 0.9334 | SAF-040 | fixed |
| `mfg_auto_approve_0400` | 8 | VLV-045 | VLV-050 | 0.9985 | VLV-045 | fixed |
| `mfg_auto_approve_0400` | 10 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_auto_approve_0400` | 14 | CBL-032 | CBL-012 | 0.9989 | CBL-032 | fixed |
| `mfg_auto_approve_0400` | 18 | MET-037 | MET-017 | 0.9308 | MET-037 | fixed |
| `mfg_auto_approve_0400` | 19 | CBL-041 | CBL-001 | 0.9991 | CBL-041 | fixed |
| `mfg_auto_approve_0400` | 23 | SAF-032 | SAF-002 | 0.9112 | SAF-032 | fixed |
| `mfg_auto_correct_0009` | 1 | PKG-021 | PKG-026 | 0.836 | - | rejected |
| `mfg_auto_correct_0009` | 2 | ELC-029 | ELC-053 | 0.8644 | - | rejected |
| `mfg_auto_correct_0009` | 8 | VLV-004 | VLV-009 | 0.9979 | VLV-004 | fixed |
| `mfg_auto_correct_0009` | 9 | SAF-050 | SAF-020 | 0.9229 | SAF-050 | fixed |
| `mfg_auto_correct_0009` | 11 | CBL-051 | CBL-011 | 0.9989 | CBL-051 | fixed |
| `mfg_auto_correct_0009` | 15 | MET-039 | MET-019 | 0.9247 | MET-039 | fixed |
| `mfg_auto_correct_0009` | 19 | SAF-056 | SAF-030 | 0.8975 | SAF-056 | fixed |
| `mfg_auto_correct_0009` | 21 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_auto_correct_0010` | 3 | VLV-023 | VLV-028 | 0.9986 | VLV-023 | fixed |
| `mfg_auto_correct_0010` | 4 | MET-013 | MET-028 | 0.9254 | MET-013 | fixed |
| `mfg_auto_correct_0010` | 15 | MET-009 | MET-019 | 0.9259 | MET-009 | fixed |
| `mfg_auto_correct_0010` | 18 | VLV-002 | VLV-007 | 0.9984 | VLV-002 | fixed |
| `mfg_auto_correct_0019` | 4 | VLV-033 | VLV-038 | 0.9987 | VLV-033 | fixed |
| `mfg_auto_correct_0019` | 8 | VLV-003 | VLV-008 | 0.9982 | VLV-003 | fixed |
| `mfg_auto_correct_0019` | 9 | VLV-024 | VLV-029 | 0.9982 | VLV-024 | fixed |
| `mfg_auto_correct_0019` | 14 | CBL-045 | CBL-005 | 0.999 | CBL-045 | fixed |
| `mfg_auto_correct_0019` | 27 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_auto_correct_0020` | 2 | ELC-031 | ELC-007 | 0.8482 | - | rejected |
| `mfg_auto_correct_0020` | 7 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_auto_correct_0020` | 9 | MET-051 | MET-016 | 0.9185 | MET-051 | fixed |
| `mfg_auto_correct_0020` | 10 | CBL-041 | CBL-001 | 0.9991 | CBL-041 | fixed |
| `mfg_auto_correct_0020` | 12 | MET-015 | MET-020 | 0.9247 | MET-015 | fixed |
| `mfg_auto_correct_0020` | 24 | VLV-031 | VLV-036 | 0.9987 | VLV-031 | fixed |
| `mfg_auto_correct_0029` | 3 | CBL-042 | CBL-002 | 0.9991 | CBL-042 | fixed |
| `mfg_auto_correct_0029` | 7 | SAF-043 | SAF-013 | 0.9133 | SAF-043 | fixed |
| `mfg_auto_correct_0029` | 11 | VLV-022 | VLV-027 | 0.9985 | VLV-022 | fixed |
| `mfg_auto_correct_0029` | 16 | VLV-023 | VLV-028 | 0.9986 | VLV-023 | fixed |
| `mfg_auto_correct_0029` | 19 | SAF-057 | SAF-027 | 0.9033 | SAF-057 | fixed |
| `mfg_auto_correct_0029` | 23 | VLV-004 | VLV-009 | 0.9979 | VLV-004 | fixed |
| `mfg_auto_correct_0029` | 26 | MET-048 | MET-018 | 0.9148 | MET-048 | fixed |
| `mfg_auto_correct_0030` | 5 | CBL-048 | CBL-008 | 0.999 | CBL-048 | fixed |
| `mfg_auto_correct_0030` | 18 | CBL-041 | CBL-001 | 0.9991 | CBL-041 | fixed |
| `mfg_auto_correct_0039` | 1 | SNS-024 | SNS-022 | 0.8149 | - | rejected |
| `mfg_auto_correct_0039` | 7 | ELC-002 | ELC-026 | 0.9821 | - | rejected |
| `mfg_auto_correct_0039` | 18 | ELC-011 | ELC-035 | 0.9833 | - | rejected |
| `mfg_auto_correct_0039` | 23 | VLV-044 | VLV-049 | 0.9981 | VLV-044 | fixed |
| `mfg_auto_correct_0039` | 24 | MET-056 | MET-026 | 0.917 | MET-056 | fixed |
| `mfg_auto_correct_0040` | 16 | CBL-037 | CBL-017 | 0.999 | CBL-037 | fixed |
| `mfg_auto_correct_0040` | 19 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_auto_correct_0040` | 20 | MET-053 | MET-018 | 0.9181 | MET-053 | fixed |
| `mfg_auto_correct_0040` | 21 | VLV-053 | VLV-058 | 0.9987 | VLV-053 | fixed |
| `mfg_auto_correct_0049` | 5 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_auto_correct_0049` | 12 | VLV-055 | VLV-060 | 0.9986 | VLV-055 | fixed |
| `mfg_auto_correct_0049` | 14 | CBL-059 | CBL-019 | 0.999 | CBL-059 | fixed |
| `mfg_auto_correct_0050` | 2 | SAF-052 | SAF-022 | 0.9206 | - | rejected |
| `mfg_auto_correct_0050` | 4 | SAF-033 | SAF-003 | 0.9156 | SAF-033 | fixed |
| `mfg_auto_correct_0050` | 13 | SAF-034 | SAF-004 | 0.9405 | SAF-034 | fixed |
| `mfg_auto_correct_0050` | 14 | CBL-028 | CBL-008 | 0.999 | CBL-028 | fixed |
| `mfg_auto_correct_0050` | 18 | CBL-031 | CBL-011 | 0.9989 | CBL-031 | fixed |
| `mfg_auto_correct_0050` | 25 | MET-008 | MET-018 | 0.9238 | MET-008 | fixed |
| `mfg_auto_correct_0050` | 27 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_auto_correct_0059` | 5 | MET-014 | MET-029 | 0.9262 | MET-014 | fixed |
| `mfg_auto_correct_0059` | 7 | SAF-045 | SAF-015 | 0.925 | SAF-045 | fixed |
| `mfg_auto_correct_0059` | 15 | MET-010 | MET-020 | 0.925 | MET-010 | fixed |
| `mfg_auto_correct_0059` | 16 | SAF-058 | SAF-028 | 0.9087 | SAF-058 | fixed |
| `mfg_auto_correct_0060` | 12 | VLV-025 | VLV-030 | 0.9985 | VLV-025 | fixed |
| `mfg_auto_correct_0060` | 18 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_auto_correct_0060` | 23 | CBL-035 | CBL-015 | 0.9989 | CBL-035 | fixed |
| `mfg_auto_correct_0069` | 1 | SAF-035 | SAF-005 | 0.9261 | - | rejected |
| `mfg_auto_correct_0069` | 23 | CBL-031 | CBL-011 | 0.9989 | CBL-031 | fixed |
| `mfg_auto_correct_0070` | 5 | VLV-032 | VLV-037 | 0.9987 | VLV-032 | fixed |
| `mfg_auto_correct_0070` | 12 | CBL-046 | CBL-006 | 0.999 | CBL-046 | fixed |
| `mfg_auto_correct_0070` | 13 | CBL-059 | CBL-019 | 0.999 | CBL-059 | fixed |
| `mfg_auto_correct_0070` | 14 | SAF-039 | SAF-009 | 0.9429 | SAF-039 | fixed |
| `mfg_auto_correct_0070` | 20 | ELC-044 | ELC-032 | 0.9821 | - | rejected |
| `mfg_auto_correct_0079` | 3 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_auto_correct_0079` | 5 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_auto_correct_0079` | 6 | CBL-026 | CBL-006 | 0.999 | CBL-026 | fixed |
| `mfg_auto_correct_0079` | 7 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_auto_correct_0079` | 9 | SAF-050 | SAF-020 | 0.9229 | SAF-050 | fixed |
| `mfg_auto_correct_0079` | 14 | VLV-011 | VLV-016 | 0.9984 | VLV-011 | fixed |
| `mfg_auto_correct_0079` | 19 | VLV-051 | VLV-056 | 0.9987 | VLV-051 | fixed |
| `mfg_auto_correct_0080` | 19 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_auto_correct_0089` | 4 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_auto_correct_0089` | 9 | CBL-038 | CBL-018 | 0.999 | CBL-038 | fixed |
| `mfg_auto_correct_0089` | 11 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_auto_correct_0089` | 12 | SAF-037 | SAF-007 | 0.9186 | SAF-037 | fixed |
| `mfg_auto_correct_0089` | 13 | MET-056 | MET-026 | 0.917 | MET-056 | fixed |
| `mfg_auto_correct_0089` | 14 | SAF-031 | SAF-001 | 0.9086 | SAF-031 | fixed |
| `mfg_auto_correct_0089` | 15 | SAF-032 | SAF-002 | 0.9112 | SAF-032 | fixed |
| `mfg_auto_correct_0090` | 2 | ELC-041 | ELC-053 | 0.8632 | - | rejected |
| `mfg_auto_correct_0090` | 11 | MET-015 | MET-020 | 0.9247 | MET-015 | fixed |
| `mfg_auto_correct_0090` | 19 | CBL-049 | CBL-009 | 0.999 | CBL-049 | fixed |
| `mfg_auto_correct_0099` | 2 | SNS-054 | SNS-052 | 0.8114 | - | rejected |
| `mfg_auto_correct_0099` | 9 | VLV-013 | VLV-018 | 0.9983 | VLV-013 | fixed |
| `mfg_auto_correct_0099` | 11 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_auto_correct_0099` | 22 | CBL-027 | CBL-007 | 0.999 | CBL-027 | fixed |
| `mfg_auto_correct_0099` | 23 | CBL-034 | CBL-014 | 0.9989 | CBL-034 | fixed |
| `mfg_auto_correct_0099` | 24 | CBL-050 | CBL-010 | 0.999 | CBL-050 | fixed |
| `mfg_auto_correct_0100` | 3 | SAF-036 | SAF-006 | 0.9147 | SAF-036 | fixed |
| `mfg_auto_correct_0100` | 4 | CBL-047 | CBL-007 | 0.999 | CBL-047 | fixed |
| `mfg_auto_correct_0100` | 5 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_auto_correct_0109` | 8 | MET-009 | MET-019 | 0.9259 | MET-009 | fixed |
| `mfg_auto_correct_0109` | 10 | MET-007 | MET-017 | 0.9294 | MET-007 | fixed |
| `mfg_auto_correct_0109` | 16 | CBL-039 | CBL-019 | 0.999 | CBL-039 | fixed |
| `mfg_auto_correct_0109` | 17 | MET-052 | MET-017 | 0.9278 | MET-052 | fixed |
| `mfg_auto_correct_0109` | 18 | SAF-043 | SAF-013 | 0.9133 | SAF-043 | fixed |
| `mfg_auto_correct_0109` | 20 | CBL-048 | CBL-008 | 0.999 | CBL-048 | fixed |
| `mfg_auto_correct_0109` | 22 | SAF-050 | SAF-020 | 0.9229 | SAF-050 | fixed |
| `mfg_auto_correct_0110` | 1 | FST-050 | FST-047 | 0.8024 | - | rejected |
| `mfg_auto_correct_0110` | 2 | ELC-049 | ELC-013 | 0.8372 | - | rejected |
| `mfg_auto_correct_0110` | 8 | SAF-043 | SAF-013 | 0.9133 | SAF-043 | fixed |
| `mfg_auto_correct_0110` | 10 | SAF-055 | SAF-025 | 0.9332 | SAF-055 | fixed |
| `mfg_auto_correct_0110` | 11 | SAF-026 | SAF-030 | 0.8975 | SAF-026 | fixed |
| `mfg_auto_correct_0110` | 16 | VLV-013 | VLV-018 | 0.9983 | VLV-013 | fixed |
| `mfg_auto_correct_0110` | 17 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_auto_correct_0110` | 23 | CBL-041 | CBL-001 | 0.9991 | CBL-041 | fixed |
| `mfg_auto_correct_0119` | 1 | FST-014 | FST-019 | 0.8198 | - | rejected |
| `mfg_auto_correct_0119` | 5 | VLV-042 | VLV-047 | 0.9987 | VLV-042 | fixed |
| `mfg_auto_correct_0119` | 7 | SAF-026 | SAF-030 | 0.8975 | SAF-026 | fixed |
| `mfg_auto_correct_0119` | 10 | CBL-054 | CBL-014 | 0.9989 | CBL-054 | fixed |
| `mfg_auto_correct_0119` | 12 | CBL-047 | CBL-007 | 0.999 | CBL-047 | fixed |
| `mfg_auto_correct_0120` | 1 | TRN-025 | TRN-010 | 0.8859 | - | rejected |
| `mfg_auto_correct_0120` | 3 | SAF-036 | SAF-006 | 0.9147 | SAF-036 | fixed |
| `mfg_auto_correct_0120` | 7 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_auto_correct_0120` | 13 | VLV-041 | VLV-046 | 0.9986 | VLV-041 | fixed |
| `mfg_auto_correct_0120` | 16 | MET-051 | MET-016 | 0.9185 | MET-051 | fixed |
| `mfg_auto_correct_0120` | 17 | SAF-059 | SAF-029 | 0.9343 | SAF-059 | fixed |
| `mfg_auto_correct_0120` | 21 | MET-058 | MET-028 | 0.9168 | MET-058 | fixed |
| `mfg_auto_correct_0120` | 22 | CBL-037 | CBL-017 | 0.999 | CBL-037 | fixed |
| `mfg_auto_correct_0120` | 28 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_auto_correct_0129` | 1 | TRN-030 | TRN-015 | 0.888 | - | rejected |
| `mfg_auto_correct_0129` | 2 | CBL-037 | CBL-009 | 0.8015 | - | rejected |
| `mfg_auto_correct_0129` | 3 | VLV-013 | VLV-018 | 0.9983 | VLV-013 | fixed |
| `mfg_auto_correct_0129` | 9 | VLV-052 | VLV-057 | 0.9988 | VLV-052 | fixed |
| `mfg_auto_correct_0129` | 13 | CBL-039 | CBL-019 | 0.999 | CBL-039 | fixed |
| `mfg_auto_correct_0129` | 15 | MET-010 | MET-020 | 0.925 | MET-010 | fixed |
| `mfg_auto_correct_0129` | 18 | VLV-044 | VLV-049 | 0.9981 | VLV-044 | fixed |
| `mfg_auto_correct_0130` | 9 | VLV-044 | VLV-049 | 0.9981 | VLV-044 | fixed |
| `mfg_auto_correct_0130` | 17 | VLV-011 | VLV-016 | 0.9984 | VLV-011 | fixed |
| `mfg_auto_correct_0130` | 22 | MET-007 | MET-017 | 0.9294 | MET-007 | fixed |
| `mfg_auto_correct_0130` | 23 | VLV-003 | VLV-008 | 0.9982 | VLV-003 | fixed |
| `mfg_auto_correct_0139` | 1 | CBL-021 | CBL-009 | 0.8758 | - | rejected |
| `mfg_auto_correct_0139` | 5 | MET-010 | MET-020 | 0.925 | MET-010 | fixed |
| `mfg_auto_correct_0139` | 11 | CBL-060 | CBL-020 | 0.9989 | CBL-060 | fixed |
| `mfg_auto_correct_0139` | 15 | VLV-023 | VLV-028 | 0.9986 | VLV-023 | fixed |
| `mfg_auto_correct_0139` | 17 | ELC-004 | ELC-028 | 0.9801 | - | rejected |
| `mfg_auto_correct_0140` | 1 | TRN-028 | TRN-013 | 0.8846 | - | rejected |
| `mfg_auto_correct_0140` | 4 | MET-006 | MET-016 | 0.9233 | MET-006 | fixed |
| `mfg_auto_correct_0140` | 10 | VLV-054 | VLV-059 | 0.9983 | VLV-054 | fixed |
| `mfg_auto_correct_0140` | 12 | MET-047 | MET-017 | 0.924 | MET-047 | fixed |
| `mfg_auto_correct_0140` | 17 | CBL-055 | CBL-015 | 0.9989 | CBL-055 | fixed |
| `mfg_auto_correct_0140` | 20 | CBL-031 | CBL-011 | 0.9989 | CBL-031 | fixed |
| `mfg_auto_correct_0140` | 23 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_auto_correct_0149` | 14 | VLV-052 | VLV-057 | 0.9988 | VLV-052 | fixed |
| `mfg_auto_correct_0149` | 15 | CBL-056 | CBL-016 | 0.9988 | CBL-056 | fixed |
| `mfg_auto_correct_0149` | 17 | VLV-005 | VLV-010 | 0.9983 | VLV-005 | fixed |
| `mfg_auto_correct_0149` | 25 | CBL-044 | CBL-004 | 0.999 | CBL-044 | fixed |
| `mfg_auto_correct_0150` | 1 | CBL-041 | CBL-009 | 0.8758 | - | rejected |
| `mfg_auto_correct_0150` | 4 | VLV-021 | VLV-026 | 0.9986 | VLV-021 | fixed |
| `mfg_auto_correct_0150` | 12 | ELC-005 | ELC-029 | 0.983 | - | rejected |
| `mfg_auto_correct_0150` | 17 | CBL-059 | CBL-019 | 0.999 | CBL-059 | fixed |
| `mfg_auto_correct_0150` | 20 | MET-013 | MET-028 | 0.9254 | MET-013 | fixed |
| `mfg_auto_correct_0159` | 1 | TRN-023 | TRN-053 | 0.8985 | - | rejected |
| `mfg_auto_correct_0159` | 2 | TRN-059 | TRN-029 | 0.8032 | - | rejected |
| `mfg_auto_correct_0159` | 4 | CBL-027 | CBL-007 | 0.999 | CBL-027 | fixed |
| `mfg_auto_correct_0159` | 6 | SAF-043 | SAF-013 | 0.9133 | SAF-043 | fixed |
| `mfg_auto_correct_0159` | 7 | MET-057 | MET-027 | 0.9244 | MET-057 | fixed |
| `mfg_auto_correct_0159` | 8 | VLV-024 | VLV-029 | 0.9982 | VLV-024 | fixed |
| `mfg_auto_correct_0159` | 12 | VLV-001 | VLV-006 | 0.9983 | VLV-001 | fixed |
| `mfg_auto_correct_0160` | 15 | VLV-032 | VLV-037 | 0.9987 | VLV-032 | fixed |
| `mfg_auto_correct_0160` | 17 | VLV-025 | VLV-030 | 0.9985 | VLV-025 | fixed |
| `mfg_auto_correct_0160` | 19 | MET-055 | MET-020 | 0.9191 | MET-055 | fixed |
| `mfg_auto_correct_0169` | 3 | SAF-055 | SAF-025 | 0.9332 | SAF-055 | fixed |
| `mfg_auto_correct_0169` | 10 | MET-006 | MET-016 | 0.9233 | MET-006 | fixed |
| `mfg_auto_correct_0169` | 13 | VLV-022 | VLV-027 | 0.9985 | VLV-022 | fixed |
| `mfg_auto_correct_0169` | 15 | VLV-004 | VLV-009 | 0.9979 | VLV-004 | fixed |
| `mfg_auto_correct_0169` | 20 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_auto_correct_0169` | 24 | CBL-052 | CBL-012 | 0.9989 | CBL-052 | fixed |
| `mfg_auto_correct_0170` | 10 | MET-048 | MET-018 | 0.9148 | MET-048 | fixed |
| `mfg_auto_correct_0170` | 14 | VLV-055 | VLV-060 | 0.9986 | VLV-055 | fixed |
| `mfg_auto_correct_0170` | 18 | VLV-013 | VLV-018 | 0.9983 | VLV-013 | fixed |
| `mfg_auto_correct_0170` | 23 | SAF-040 | SAF-010 | 0.9334 | SAF-040 | fixed |
| `mfg_auto_correct_0179` | 13 | CBL-051 | CBL-011 | 0.9989 | CBL-051 | fixed |
| `mfg_auto_correct_0179` | 18 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_auto_correct_0179` | 19 | VLV-022 | VLV-027 | 0.9985 | VLV-022 | fixed |
| `mfg_auto_correct_0180` | 3 | VLV-031 | VLV-036 | 0.9987 | VLV-031 | fixed |
| `mfg_auto_correct_0180` | 5 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_auto_correct_0180` | 19 | MET-012 | MET-017 | 0.9296 | MET-012 | fixed |
| `mfg_auto_correct_0189` | 12 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_auto_correct_0189` | 16 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_auto_correct_0189` | 19 | SAF-050 | SAF-020 | 0.9229 | SAF-050 | fixed |
| `mfg_auto_correct_0190` | 7 | CBL-058 | CBL-018 | 0.999 | CBL-058 | fixed |
| `mfg_auto_correct_0190` | 12 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_auto_correct_0190` | 23 | SAF-036 | SAF-006 | 0.9147 | SAF-036 | fixed |
| `mfg_auto_correct_0190` | 25 | CBL-060 | CBL-020 | 0.9989 | CBL-060 | fixed |
| `mfg_auto_correct_0190` | 26 | CBL-042 | CBL-002 | 0.9991 | CBL-042 | fixed |
| `mfg_auto_correct_0190` | 30 | VLV-031 | VLV-036 | 0.9987 | VLV-031 | fixed |
| `mfg_auto_correct_0199` | 20 | VLV-004 | VLV-009 | 0.9979 | VLV-004 | fixed |
| `mfg_auto_correct_0199` | 21 | SAF-058 | SAF-028 | 0.9087 | SAF-058 | fixed |
| `mfg_auto_correct_0199` | 23 | MET-037 | MET-017 | 0.9308 | MET-037 | fixed |
| `mfg_auto_correct_0200` | 6 | SAF-026 | SAF-030 | 0.8975 | SAF-026 | fixed |
| `mfg_auto_correct_0200` | 13 | CBL-052 | CBL-012 | 0.9989 | CBL-052 | fixed |
| `mfg_auto_correct_0200` | 20 | VLV-024 | VLV-029 | 0.9982 | VLV-024 | fixed |
| `mfg_auto_correct_0209` | 1 | PNE-057 | PNE-037 | 0.8196 | - | rejected |
| `mfg_auto_correct_0209` | 5 | SAF-034 | SAF-004 | 0.9405 | SAF-034 | fixed |
| `mfg_auto_correct_0209` | 17 | SAF-059 | SAF-029 | 0.9343 | SAF-059 | fixed |
| `mfg_auto_correct_0209` | 22 | SAF-036 | SAF-006 | 0.9147 | SAF-036 | fixed |
| `mfg_auto_correct_0209` | 24 | MET-057 | MET-027 | 0.9244 | MET-057 | fixed |
| `mfg_auto_correct_0210` | 1 | ELC-057 | ELC-045 | 0.8506 | - | rejected |
| `mfg_auto_correct_0210` | 2 | SAF-035 | SAF-005 | 0.9261 | - | rejected |
| `mfg_auto_correct_0210` | 3 | VLV-023 | VLV-028 | 0.9986 | VLV-023 | fixed |
| `mfg_auto_correct_0210` | 8 | VLV-013 | VLV-018 | 0.9983 | VLV-013 | fixed |
| `mfg_auto_correct_0210` | 9 | SAF-058 | SAF-028 | 0.9087 | SAF-058 | fixed |
| `mfg_auto_correct_0210` | 27 | MET-047 | MET-017 | 0.924 | MET-047 | fixed |
| `mfg_auto_correct_0219` | 12 | MET-060 | MET-030 | 0.9167 | MET-060 | fixed |
| `mfg_auto_correct_0219` | 14 | VLV-031 | VLV-036 | 0.9987 | VLV-031 | fixed |
| `mfg_auto_correct_0219` | 23 | MET-058 | MET-028 | 0.9168 | MET-058 | fixed |
| `mfg_auto_correct_0219` | 25 | CBL-024 | CBL-004 | 0.999 | CBL-024 | fixed |
| `mfg_auto_correct_0220` | 9 | CBL-045 | CBL-005 | 0.999 | CBL-045 | fixed |
| `mfg_auto_correct_0220` | 24 | VLV-022 | VLV-027 | 0.9985 | VLV-022 | fixed |
| `mfg_auto_correct_0229` | 21 | MET-039 | MET-019 | 0.9247 | MET-039 | fixed |
| `mfg_auto_correct_0229` | 22 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_auto_correct_0230` | 15 | CBL-044 | CBL-004 | 0.999 | CBL-044 | fixed |
| `mfg_auto_correct_0239` | 2 | ELC-033 | ELC-045 | 0.8514 | - | rejected |
| `mfg_auto_correct_0239` | 20 | CBL-049 | CBL-009 | 0.999 | CBL-049 | fixed |
| `mfg_auto_correct_0239` | 23 | VLV-003 | VLV-008 | 0.9982 | VLV-003 | fixed |
| `mfg_auto_correct_0240` | 3 | SAF-037 | SAF-007 | 0.9186 | SAF-037 | fixed |
| `mfg_auto_correct_0240` | 5 | CBL-058 | CBL-018 | 0.999 | CBL-058 | fixed |
| `mfg_auto_correct_0240` | 12 | CBL-043 | CBL-003 | 0.999 | CBL-043 | fixed |
| `mfg_auto_correct_0249` | 3 | CBL-025 | CBL-005 | 0.999 | CBL-025 | fixed |
| `mfg_auto_correct_0249` | 11 | CBL-040 | CBL-020 | 0.9989 | CBL-040 | fixed |
| `mfg_auto_correct_0249` | 15 | MET-007 | MET-017 | 0.9294 | MET-007 | fixed |
| `mfg_auto_correct_0249` | 20 | VLV-053 | VLV-058 | 0.9987 | VLV-053 | fixed |
| `mfg_auto_correct_0250` | 1 | CBL-049 | CBL-009 | 0.8758 | - | rejected |
| `mfg_auto_correct_0250` | 21 | VLV-034 | VLV-039 | 0.9983 | VLV-034 | fixed |
| `mfg_auto_correct_0259` | 6 | VLV-002 | VLV-007 | 0.9984 | VLV-002 | fixed |
| `mfg_auto_correct_0259` | 9 | SAF-041 | SAF-011 | 0.9044 | SAF-041 | fixed |
| `mfg_auto_correct_0259` | 10 | MET-049 | MET-034 | 0.9165 | MET-049 | fixed |
| `mfg_auto_correct_0259` | 17 | MET-047 | MET-017 | 0.924 | MET-047 | fixed |
| `mfg_auto_correct_0259` | 19 | VLV-023 | VLV-028 | 0.9986 | VLV-023 | fixed |
| `mfg_auto_correct_0259` | 24 | SAF-032 | SAF-002 | 0.9112 | SAF-032 | fixed |
| `mfg_auto_correct_0260` | 1 | CBL-001 | CBL-009 | 0.8758 | - | rejected |
| `mfg_auto_correct_0260` | 2 | FST-048 | FST-053 | 0.8395 | - | rejected |
| `mfg_auto_correct_0260` | 7 | CBL-036 | CBL-016 | 0.9988 | CBL-036 | fixed |
| `mfg_auto_correct_0260` | 8 | SAF-031 | SAF-001 | 0.9086 | SAF-031 | fixed |
| `mfg_auto_correct_0260` | 9 | CBL-059 | CBL-019 | 0.999 | CBL-059 | fixed |
| `mfg_auto_correct_0260` | 16 | SAF-047 | SAF-017 | 0.9051 | SAF-047 | fixed |
| `mfg_auto_correct_0269` | 3 | VLV-001 | VLV-006 | 0.9983 | VLV-001 | fixed |
| `mfg_auto_correct_0269` | 4 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_auto_correct_0269` | 9 | SAF-043 | SAF-013 | 0.9133 | SAF-043 | fixed |
| `mfg_auto_correct_0269` | 15 | SAF-055 | SAF-025 | 0.9332 | SAF-055 | fixed |
| `mfg_auto_correct_0269` | 19 | MET-008 | MET-018 | 0.9238 | MET-008 | fixed |
| `mfg_auto_correct_0269` | 22 | CBL-022 | CBL-002 | 0.9991 | CBL-022 | fixed |
| `mfg_auto_correct_0269` | 25 | SAF-047 | SAF-017 | 0.9051 | SAF-047 | fixed |
| `mfg_auto_correct_0270` | 12 | CBL-054 | CBL-014 | 0.9989 | CBL-054 | fixed |
| `mfg_auto_correct_0270` | 14 | VLV-015 | VLV-020 | 0.9984 | VLV-015 | fixed |
| `mfg_auto_correct_0270` | 25 | MET-059 | MET-029 | 0.9171 | MET-059 | fixed |
| `mfg_auto_correct_0279` | 1 | PKG-051 | PKG-026 | 0.8277 | - | rejected |
| `mfg_auto_correct_0279` | 5 | MET-039 | MET-019 | 0.9247 | MET-039 | fixed |
| `mfg_auto_correct_0279` | 11 | MET-046 | MET-031 | 0.9162 | MET-046 | fixed |
| `mfg_auto_correct_0279` | 15 | SAF-055 | SAF-025 | 0.9332 | SAF-055 | fixed |
| `mfg_auto_correct_0279` | 18 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_auto_correct_0280` | 4 | MET-047 | MET-017 | 0.924 | MET-047 | fixed |
| `mfg_auto_correct_0280` | 6 | VLV-043 | VLV-048 | 0.9986 | VLV-043 | fixed |
| `mfg_auto_correct_0280` | 8 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_auto_correct_0280` | 11 | VLV-052 | VLV-057 | 0.9988 | VLV-052 | fixed |
| `mfg_auto_correct_0280` | 19 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_auto_correct_0289` | 5 | CBL-023 | CBL-003 | 0.999 | CBL-023 | fixed |
| `mfg_auto_correct_0289` | 9 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_auto_correct_0289` | 22 | MET-056 | MET-026 | 0.917 | MET-056 | fixed |
| `mfg_auto_correct_0289` | 24 | SAF-034 | SAF-004 | 0.9405 | SAF-034 | fixed |
| `mfg_auto_correct_0290` | 1 | FST-004 | FST-003 | 0.8347 | - | rejected |
| `mfg_auto_correct_0290` | 24 | CBL-059 | CBL-019 | 0.999 | CBL-059 | fixed |
| `mfg_auto_correct_0290` | 25 | CBL-023 | CBL-003 | 0.999 | CBL-023 | fixed |
| `mfg_auto_correct_0299` | 3 | CBL-028 | CBL-008 | 0.999 | CBL-028 | fixed |
| `mfg_auto_correct_0299` | 5 | CBL-041 | CBL-001 | 0.9991 | CBL-041 | fixed |
| `mfg_auto_correct_0299` | 13 | CBL-025 | CBL-005 | 0.999 | CBL-025 | fixed |
| `mfg_auto_correct_0299` | 18 | MET-059 | MET-029 | 0.9171 | MET-059 | fixed |
| `mfg_auto_correct_0299` | 21 | CBL-031 | CBL-011 | 0.9989 | CBL-031 | fixed |
| `mfg_auto_correct_0300` | 1 | PKG-053 | PKG-028 | 0.8302 | - | rejected |
| `mfg_auto_correct_0300` | 2 | ELC-034 | ELC-058 | 0.8623 | - | rejected |
| `mfg_auto_correct_0300` | 13 | VLV-014 | VLV-019 | 0.9981 | VLV-014 | fixed |
| `mfg_auto_correct_0309` | 1 | PKG-054 | PKG-029 | 0.8337 | - | rejected |
| `mfg_auto_correct_0309` | 3 | CBL-036 | CBL-016 | 0.9988 | CBL-036 | fixed |
| `mfg_auto_correct_0309` | 18 | CBL-053 | CBL-013 | 0.999 | CBL-053 | fixed |
| `mfg_auto_correct_0309` | 21 | CBL-046 | CBL-006 | 0.999 | CBL-046 | fixed |
| `mfg_auto_correct_0310` | 1 | PKG-047 | PKG-057 | 0.8623 | - | rejected |
| `mfg_auto_correct_0310` | 6 | MET-013 | MET-028 | 0.9254 | MET-013 | fixed |
| `mfg_auto_correct_0310` | 11 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_auto_correct_0310` | 15 | CBL-032 | CBL-012 | 0.9989 | CBL-032 | fixed |
| `mfg_auto_correct_0310` | 16 | VLV-045 | VLV-050 | 0.9985 | VLV-045 | fixed |
| `mfg_auto_correct_0310` | 21 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_auto_correct_0310` | 27 | CBL-024 | CBL-004 | 0.999 | CBL-024 | fixed |
| `mfg_auto_correct_0310` | 28 | VLV-054 | VLV-059 | 0.9983 | VLV-054 | fixed |
| `mfg_auto_correct_0319` | 18 | VLV-041 | VLV-046 | 0.9986 | VLV-041 | fixed |
| `mfg_auto_correct_0319` | 19 | SAF-049 | SAF-019 | 0.9358 | SAF-049 | fixed |
| `mfg_auto_correct_0320` | 3 | MET-058 | MET-028 | 0.9168 | MET-058 | fixed |
| `mfg_auto_correct_0320` | 4 | MET-012 | MET-017 | 0.9296 | MET-012 | fixed |
| `mfg_auto_correct_0320` | 9 | CBL-034 | CBL-014 | 0.9989 | CBL-034 | fixed |
| `mfg_auto_correct_0320` | 14 | SAF-033 | SAF-003 | 0.9156 | SAF-033 | fixed |
| `mfg_auto_correct_0320` | 16 | CBL-059 | CBL-019 | 0.999 | CBL-059 | fixed |
| `mfg_auto_correct_0329` | 4 | SAF-032 | SAF-002 | 0.9112 | SAF-032 | fixed |
| `mfg_auto_correct_0329` | 11 | SAF-060 | SAF-030 | 0.923 | SAF-060 | fixed |
| `mfg_auto_correct_0329` | 15 | MET-014 | MET-029 | 0.9262 | MET-014 | fixed |
| `mfg_auto_correct_0329` | 19 | MET-060 | MET-030 | 0.9167 | MET-060 | fixed |
| `mfg_auto_correct_0329` | 25 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_auto_correct_0330` | 3 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_auto_correct_0330` | 16 | CBL-058 | CBL-018 | 0.999 | CBL-058 | fixed |
| `mfg_auto_correct_0339` | 2 | PNE-056 | PNE-041 | 0.8044 | - | rejected |
| `mfg_auto_correct_0339` | 5 | CBL-053 | CBL-013 | 0.999 | CBL-053 | fixed |
| `mfg_auto_correct_0339` | 7 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_auto_correct_0339` | 13 | CBL-027 | CBL-007 | 0.999 | CBL-027 | fixed |
| `mfg_auto_correct_0339` | 14 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_auto_correct_0339` | 22 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_auto_correct_0340` | 8 | VLV-044 | VLV-049 | 0.9981 | VLV-044 | fixed |
| `mfg_auto_correct_0340` | 19 | MET-039 | MET-019 | 0.9247 | MET-039 | fixed |
| `mfg_auto_correct_0340` | 25 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_auto_correct_0349` | 6 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_auto_correct_0349` | 25 | CBL-031 | CBL-011 | 0.9989 | CBL-031 | fixed |
| `mfg_auto_correct_0349` | 27 | SAF-026 | SAF-030 | 0.8975 | SAF-026 | fixed |
| `mfg_auto_correct_0350` | 4 | VLV-002 | VLV-007 | 0.9984 | VLV-002 | fixed |
| `mfg_auto_correct_0350` | 19 | SAF-031 | SAF-001 | 0.9086 | SAF-031 | fixed |
| `mfg_auto_correct_0359` | 2 | ELC-002 | ELC-014 | 0.8743 | - | rejected |
| `mfg_auto_correct_0359` | 3 | CBL-055 | CBL-015 | 0.9989 | CBL-055 | fixed |
| `mfg_auto_correct_0359` | 7 | CBL-032 | CBL-012 | 0.9989 | CBL-032 | fixed |
| `mfg_auto_correct_0359` | 20 | SAF-050 | SAF-020 | 0.9229 | SAF-050 | fixed |
| `mfg_auto_correct_0360` | 1 | FST-011 | FST-007 | 0.8179 | - | rejected |
| `mfg_auto_correct_0360` | 4 | MET-059 | MET-029 | 0.9171 | MET-059 | fixed |
| `mfg_auto_correct_0360` | 6 | VLV-005 | VLV-010 | 0.9983 | VLV-005 | fixed |
| `mfg_auto_correct_0360` | 7 | CBL-024 | CBL-004 | 0.999 | CBL-024 | fixed |
| `mfg_auto_correct_0360` | 11 | CBL-060 | CBL-020 | 0.9989 | CBL-060 | fixed |
| `mfg_auto_correct_0360` | 12 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_auto_correct_0360` | 14 | CBL-034 | CBL-014 | 0.9989 | CBL-034 | fixed |
| `mfg_auto_correct_0360` | 16 | CBL-043 | CBL-003 | 0.999 | CBL-043 | fixed |
| `mfg_auto_correct_0360` | 21 | MET-057 | MET-027 | 0.9244 | MET-057 | fixed |
| `mfg_auto_correct_0369` | 16 | MET-057 | MET-027 | 0.9244 | MET-057 | fixed |
| `mfg_auto_correct_0369` | 17 | CBL-043 | CBL-003 | 0.999 | CBL-043 | fixed |
| `mfg_auto_correct_0369` | 23 | MET-053 | MET-018 | 0.9181 | MET-053 | fixed |
| `mfg_auto_correct_0370` | 4 | VLV-042 | VLV-047 | 0.9987 | VLV-042 | fixed |
| `mfg_auto_correct_0370` | 5 | CBL-037 | CBL-017 | 0.999 | CBL-037 | fixed |
| `mfg_auto_correct_0370` | 10 | VLV-032 | VLV-037 | 0.9987 | VLV-032 | fixed |
| `mfg_auto_correct_0370` | 11 | MET-037 | MET-017 | 0.9308 | MET-037 | fixed |
| `mfg_auto_correct_0370` | 17 | CBL-060 | CBL-020 | 0.9989 | CBL-060 | fixed |
| `mfg_auto_correct_0370` | 21 | VLV-053 | VLV-058 | 0.9987 | VLV-053 | fixed |
| `mfg_auto_correct_0370` | 22 | MET-010 | MET-020 | 0.925 | MET-010 | fixed |
| `mfg_auto_correct_0379` | 14 | CBL-025 | CBL-005 | 0.999 | CBL-025 | fixed |
| `mfg_auto_correct_0380` | 1 | CBL-028 | CBL-008 | 0.8859 | - | rejected |
| `mfg_auto_correct_0380` | 5 | SAF-055 | SAF-025 | 0.9332 | SAF-055 | fixed |
| `mfg_auto_correct_0389` | 20 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_auto_correct_0390` | 7 | MET-007 | MET-017 | 0.9294 | MET-007 | fixed |
| `mfg_auto_correct_0390` | 23 | SAF-039 | SAF-009 | 0.9429 | SAF-039 | fixed |
| `mfg_auto_correct_0399` | 6 | VLV-051 | VLV-056 | 0.9987 | VLV-051 | fixed |
| `mfg_auto_correct_0399` | 21 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_auto_correct_0399` | 26 | MET-007 | MET-017 | 0.9294 | MET-007 | fixed |
| `mfg_auto_correct_0400` | 4 | CBL-032 | CBL-012 | 0.9989 | CBL-032 | fixed |
| `mfg_auto_correct_0400` | 15 | SAF-055 | SAF-025 | 0.9332 | SAF-055 | fixed |
| `mfg_manual_review_0009` | 3 | CBL-026 | CBL-006 | 0.999 | CBL-026 | fixed |
| `mfg_manual_review_0009` | 7 | VLV-052 | VLV-057 | 0.9988 | VLV-052 | fixed |
| `mfg_manual_review_0009` | 22 | MET-010 | MET-020 | 0.925 | MET-010 | fixed |
| `mfg_manual_review_0009` | 23 | SAF-037 | SAF-007 | 0.9186 | SAF-037 | fixed |
| `mfg_manual_review_0009` | 24 | VLV-051 | VLV-056 | 0.9987 | VLV-051 | fixed |
| `mfg_manual_review_0010` | 4 | ELC-011 | ELC-035 | 0.9833 | - | rejected |
| `mfg_manual_review_0010` | 9 | VLV-014 | VLV-019 | 0.9981 | VLV-014 | fixed |
| `mfg_manual_review_0010` | 12 | MET-053 | MET-018 | 0.9181 | MET-053 | fixed |
| `mfg_manual_review_0010` | 14 | VLV-045 | VLV-050 | 0.9985 | VLV-045 | fixed |
| `mfg_manual_review_0010` | 15 | CBL-024 | CBL-004 | 0.999 | CBL-024 | fixed |
| `mfg_manual_review_0010` | 20 | ELC-042 | ELC-030 | 0.9792 | - | rejected |
| `mfg_manual_review_0010` | 24 | SAF-034 | SAF-004 | 0.9405 | SAF-034 | fixed |
| `mfg_manual_review_0019` | 3 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_manual_review_0019` | 16 | VLV-012 | VLV-017 | 0.9986 | VLV-012 | fixed |
| `mfg_manual_review_0019` | 18 | SAF-039 | SAF-009 | 0.9429 | SAF-039 | fixed |
| `mfg_manual_review_0020` | 11 | SAF-049 | SAF-019 | 0.9358 | SAF-049 | fixed |
| `mfg_manual_review_0020` | 19 | VLV-023 | VLV-028 | 0.9986 | VLV-023 | fixed |
| `mfg_manual_review_0020` | 21 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_manual_review_0020` | 22 | CBL-028 | CBL-008 | 0.999 | CBL-028 | fixed |
| `mfg_manual_review_0029` | 5 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_manual_review_0029` | 10 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_manual_review_0029` | 12 | CBL-025 | CBL-005 | 0.999 | CBL-025 | fixed |
| `mfg_manual_review_0029` | 19 | CBL-041 | CBL-001 | 0.9991 | CBL-041 | fixed |
| `mfg_manual_review_0029` | 22 | VLV-041 | VLV-046 | 0.9986 | VLV-041 | fixed |
| `mfg_manual_review_0029` | 24 | CBL-040 | CBL-020 | 0.9989 | CBL-040 | fixed |
| `mfg_manual_review_0030` | 1 | VLV-012 | VLV-017 | 0.9986 | VLV-012 | fixed |
| `mfg_manual_review_0030` | 13 | CBL-053 | CBL-013 | 0.999 | CBL-053 | fixed |
| `mfg_manual_review_0030` | 22 | VLV-002 | VLV-007 | 0.9984 | VLV-002 | fixed |
| `mfg_manual_review_0039` | 4 | VLV-001 | VLV-006 | 0.9983 | VLV-001 | fixed |
| `mfg_manual_review_0039` | 8 | VLV-045 | VLV-050 | 0.9985 | VLV-045 | fixed |
| `mfg_manual_review_0039` | 17 | CBL-054 | CBL-014 | 0.9989 | CBL-054 | fixed |
| `mfg_manual_review_0039` | 20 | MET-051 | MET-016 | 0.9185 | MET-051 | fixed |
| `mfg_manual_review_0039` | 21 | CBL-038 | CBL-018 | 0.999 | CBL-038 | fixed |
| `mfg_manual_review_0040` | 1 | SAF-026 | SAF-030 | 0.8975 | SAF-026 | fixed |
| `mfg_manual_review_0040` | 3 | SAF-038 | SAF-008 | 0.9218 | SAF-038 | fixed |
| `mfg_manual_review_0040` | 7 | CBL-023 | CBL-003 | 0.999 | CBL-023 | fixed |
| `mfg_manual_review_0040` | 14 | SAF-034 | SAF-004 | 0.9405 | SAF-034 | fixed |
| `mfg_manual_review_0049` | 9 | VLV-022 | VLV-027 | 0.9985 | VLV-022 | fixed |
| `mfg_manual_review_0049` | 13 | SAF-033 | SAF-003 | 0.9156 | SAF-033 | fixed |
| `mfg_manual_review_0049` | 16 | MET-058 | MET-028 | 0.9168 | MET-058 | fixed |
| `mfg_manual_review_0049` | 19 | MET-047 | MET-017 | 0.924 | MET-047 | fixed |
| `mfg_manual_review_0050` | 20 | VLV-031 | VLV-036 | 0.9987 | VLV-031 | fixed |
| `mfg_manual_review_0059` | 2 | SAF-039 | SAF-009 | 0.9429 | SAF-039 | fixed |
| `mfg_manual_review_0059` | 3 | CBL-044 | CBL-004 | 0.999 | CBL-044 | fixed |
| `mfg_manual_review_0059` | 14 | MET-049 | MET-034 | 0.9165 | MET-049 | fixed |
| `mfg_manual_review_0059` | 15 | CBL-022 | CBL-002 | 0.9991 | CBL-022 | fixed |
| `mfg_manual_review_0059` | 22 | CBL-050 | CBL-010 | 0.999 | CBL-050 | fixed |
| `mfg_manual_review_0059` | 24 | SAF-055 | SAF-025 | 0.9332 | SAF-055 | fixed |
| `mfg_manual_review_0060` | 6 | ELC-012 | ELC-036 | 0.9798 | - | rejected |
| `mfg_manual_review_0060` | 13 | CBL-058 | CBL-018 | 0.999 | CBL-058 | fixed |
| `mfg_manual_review_0060` | 15 | VLV-012 | VLV-017 | 0.9986 | VLV-012 | fixed |
| `mfg_manual_review_0069` | 4 | CBL-037 | CBL-017 | 0.999 | CBL-037 | fixed |
| `mfg_manual_review_0069` | 5 | SAF-059 | SAF-029 | 0.9343 | SAF-059 | fixed |
| `mfg_manual_review_0069` | 9 | CBL-058 | CBL-018 | 0.999 | CBL-058 | fixed |
| `mfg_manual_review_0069` | 13 | CBL-049 | CBL-009 | 0.999 | CBL-049 | fixed |
| `mfg_manual_review_0069` | 14 | SAF-041 | SAF-011 | 0.9044 | SAF-041 | fixed |
| `mfg_manual_review_0070` | 15 | CBL-039 | CBL-019 | 0.999 | CBL-039 | fixed |
| `mfg_manual_review_0070` | 24 | SAF-057 | SAF-027 | 0.9033 | SAF-057 | fixed |
| `mfg_manual_review_0079` | 1 | CUT-031 | CUT-030 | 0.8766 | - | rejected |
| `mfg_manual_review_0079` | 5 | VLV-011 | VLV-016 | 0.9984 | VLV-011 | fixed |
| `mfg_manual_review_0079` | 18 | VLV-015 | VLV-020 | 0.9984 | VLV-015 | fixed |
| `mfg_manual_review_0080` | 3 | VLV-001 | VLV-006 | 0.9983 | VLV-001 | fixed |
| `mfg_manual_review_0080` | 11 | CBL-047 | CBL-007 | 0.999 | CBL-047 | fixed |
| `mfg_manual_review_0080` | 13 | VLV-015 | VLV-020 | 0.9984 | VLV-015 | fixed |
| `mfg_manual_review_0080` | 19 | CBL-038 | CBL-018 | 0.999 | CBL-038 | fixed |
| `mfg_manual_review_0080` | 21 | VLV-054 | VLV-059 | 0.9983 | VLV-054 | fixed |
| `mfg_manual_review_0089` | 2 | SAF-041 | SAF-011 | 0.9044 | SAF-041 | fixed |
| `mfg_manual_review_0089` | 5 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_manual_review_0089` | 8 | MET-014 | MET-029 | 0.9262 | MET-014 | fixed |
| `mfg_manual_review_0089` | 9 | CBL-051 | CBL-011 | 0.9989 | CBL-051 | fixed |
| `mfg_manual_review_0089` | 16 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_manual_review_0089` | 18 | VLV-001 | VLV-006 | 0.9983 | VLV-001 | fixed |
| `mfg_manual_review_0089` | 19 | VLV-033 | VLV-038 | 0.9987 | VLV-033 | fixed |
| `mfg_manual_review_0089` | 20 | MET-051 | MET-016 | 0.9185 | MET-051 | fixed |
| `mfg_manual_review_0089` | 22 | CBL-043 | CBL-003 | 0.999 | CBL-043 | fixed |
| `mfg_manual_review_0090` | 5 | VLV-024 | VLV-029 | 0.9982 | VLV-024 | fixed |
| `mfg_manual_review_0090` | 9 | CBL-024 | CBL-004 | 0.999 | CBL-024 | fixed |
| `mfg_manual_review_0090` | 22 | SAF-034 | SAF-004 | 0.9405 | SAF-034 | fixed |
| `mfg_manual_review_0099` | 8 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_manual_review_0099` | 13 | VLV-004 | VLV-009 | 0.9979 | VLV-004 | fixed |
| `mfg_manual_review_0099` | 16 | CBL-047 | CBL-007 | 0.999 | CBL-047 | fixed |
| `mfg_manual_review_0099` | 20 | VLV-043 | VLV-048 | 0.9986 | VLV-043 | fixed |
| `mfg_manual_review_0099` | 30 | SAF-060 | SAF-030 | 0.923 | SAF-060 | fixed |
| `mfg_manual_review_0100` | 9 | CBL-036 | CBL-016 | 0.9988 | CBL-036 | fixed |
| `mfg_manual_review_0100` | 12 | CBL-045 | CBL-005 | 0.999 | CBL-045 | fixed |
| `mfg_manual_review_0100` | 17 | CBL-051 | CBL-011 | 0.9989 | CBL-051 | fixed |
| `mfg_manual_review_0100` | 18 | CBL-046 | CBL-006 | 0.999 | CBL-046 | fixed |
| `mfg_manual_review_0100` | 24 | CBL-037 | CBL-017 | 0.999 | CBL-037 | fixed |
| `mfg_manual_review_0100` | 25 | SAF-060 | SAF-030 | 0.923 | SAF-060 | fixed |
| `mfg_manual_review_0109` | 5 | CBL-057 | CBL-017 | 0.999 | CBL-057 | fixed |
| `mfg_manual_review_0109` | 24 | CBL-025 | CBL-005 | 0.999 | CBL-025 | fixed |
| `mfg_manual_review_0110` | 3 | VLV-042 | VLV-047 | 0.9987 | VLV-042 | fixed |
| `mfg_manual_review_0110` | 9 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_manual_review_0110` | 12 | CBL-023 | CBL-003 | 0.999 | CBL-023 | fixed |
| `mfg_manual_review_0110` | 14 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_manual_review_0110` | 22 | CBL-045 | CBL-005 | 0.999 | CBL-045 | fixed |
| `mfg_manual_review_0119` | 6 | CBL-035 | CBL-015 | 0.9989 | CBL-035 | fixed |
| `mfg_manual_review_0119` | 7 | ELC-004 | ELC-028 | 0.9801 | - | rejected |
| `mfg_manual_review_0119` | 8 | SAF-056 | SAF-030 | 0.8975 | SAF-056 | fixed |
| `mfg_manual_review_0119` | 13 | ELC-057 | ELC-033 | 0.9818 | - | rejected |
| `mfg_manual_review_0119` | 18 | VLV-055 | VLV-060 | 0.9986 | VLV-055 | fixed |
| `mfg_manual_review_0119` | 19 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_manual_review_0119` | 22 | MET-056 | MET-026 | 0.917 | MET-056 | fixed |
| `mfg_manual_review_0119` | 24 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_manual_review_0120` | 5 | MET-056 | MET-026 | 0.917 | MET-056 | fixed |
| `mfg_manual_review_0120` | 14 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_manual_review_0120` | 15 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_manual_review_0120` | 20 | CBL-035 | CBL-015 | 0.9989 | CBL-035 | fixed |
| `mfg_manual_review_0129` | 6 | MET-048 | MET-018 | 0.9148 | MET-048 | fixed |
| `mfg_manual_review_0129` | 8 | VLV-024 | VLV-029 | 0.9982 | VLV-024 | fixed |
| `mfg_manual_review_0129` | 9 | VLV-052 | VLV-057 | 0.9988 | VLV-052 | fixed |
| `mfg_manual_review_0129` | 11 | MET-040 | MET-020 | 0.924 | MET-040 | fixed |
| `mfg_manual_review_0129` | 12 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_manual_review_0130` | 2 | VLV-051 | VLV-057 | 0.9052 | - | rejected |
| `mfg_manual_review_0130` | 5 | CBL-059 | CBL-019 | 0.999 | CBL-059 | fixed |
| `mfg_manual_review_0130` | 14 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_manual_review_0130` | 22 | VLV-052 | VLV-057 | 0.9988 | VLV-052 | fixed |
| `mfg_manual_review_0130` | 24 | MET-037 | MET-017 | 0.9308 | MET-037 | fixed |
| `mfg_manual_review_0139` | 3 | MET-015 | MET-020 | 0.9247 | MET-015 | fixed |
| `mfg_manual_review_0139` | 11 | VLV-024 | VLV-029 | 0.9982 | VLV-024 | fixed |
| `mfg_manual_review_0139` | 18 | VLV-042 | VLV-047 | 0.9987 | VLV-042 | fixed |
| `mfg_manual_review_0140` | 8 | CBL-050 | CBL-010 | 0.999 | CBL-050 | fixed |
| `mfg_manual_review_0149` | 20 | CBL-030 | CBL-010 | 0.999 | CBL-030 | fixed |
| `mfg_manual_review_0149` | 24 | VLV-031 | VLV-036 | 0.9987 | VLV-031 | fixed |
| `mfg_manual_review_0149` | 26 | CBL-041 | CBL-001 | 0.9991 | CBL-041 | fixed |
| `mfg_manual_review_0150` | 1 | SAF-034 | SAF-004 | 0.9405 | SAF-034 | fixed |
| `mfg_manual_review_0150` | 7 | CBL-051 | CBL-011 | 0.9989 | CBL-051 | fixed |
| `mfg_manual_review_0150` | 16 | CBL-056 | CBL-016 | 0.9988 | CBL-056 | fixed |
| `mfg_manual_review_0159` | 3 | SAF-037 | SAF-007 | 0.9186 | SAF-037 | fixed |
| `mfg_manual_review_0159` | 9 | CBL-036 | CBL-016 | 0.9988 | CBL-036 | fixed |
| `mfg_manual_review_0159` | 12 | MET-052 | MET-017 | 0.9278 | MET-052 | fixed |
| `mfg_manual_review_0159` | 16 | MET-040 | MET-020 | 0.924 | MET-040 | fixed |
| `mfg_manual_review_0159` | 17 | VLV-004 | VLV-009 | 0.9979 | VLV-004 | fixed |
| `mfg_manual_review_0159` | 23 | VLV-033 | VLV-038 | 0.9987 | VLV-033 | fixed |
| `mfg_manual_review_0160` | 4 | SAF-046 | SAF-016 | 0.9007 | SAF-046 | fixed |
| `mfg_manual_review_0160` | 11 | VLV-001 | VLV-006 | 0.9983 | VLV-001 | fixed |
| `mfg_manual_review_0160` | 18 | CBL-056 | CBL-016 | 0.9988 | CBL-056 | fixed |
| `mfg_manual_review_0160` | 22 | CBL-050 | CBL-010 | 0.999 | CBL-050 | fixed |
| `mfg_manual_review_0160` | 23 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_manual_review_0169` | 4 | SAF-033 | SAF-003 | 0.9156 | SAF-033 | fixed |
| `mfg_manual_review_0169` | 10 | MET-047 | MET-017 | 0.924 | MET-047 | fixed |
| `mfg_manual_review_0169` | 21 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_manual_review_0170` | 2 | MET-053 | MET-018 | 0.9181 | MET-053 | fixed |
| `mfg_manual_review_0170` | 4 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_manual_review_0170` | 7 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_manual_review_0170` | 9 | CBL-054 | CBL-014 | 0.9989 | CBL-054 | fixed |
| `mfg_manual_review_0170` | 15 | SAF-048 | SAF-018 | 0.9089 | SAF-048 | fixed |
| `mfg_manual_review_0179` | 1 | FST-039 | FST-044 | 0.8786 | - | rejected |
| `mfg_manual_review_0179` | 2 | MET-058 | MET-028 | 0.9168 | MET-058 | fixed |
| `mfg_manual_review_0179` | 4 | CBL-030 | CBL-010 | 0.999 | CBL-030 | fixed |
| `mfg_manual_review_0179` | 5 | VLV-001 | VLV-006 | 0.9983 | VLV-001 | fixed |
| `mfg_manual_review_0179` | 10 | VLV-053 | VLV-058 | 0.9987 | VLV-053 | fixed |
| `mfg_manual_review_0180` | 8 | VLV-042 | VLV-047 | 0.9987 | VLV-042 | fixed |
| `mfg_manual_review_0180` | 10 | SAF-047 | SAF-017 | 0.9051 | SAF-047 | fixed |
| `mfg_manual_review_0180` | 12 | MET-056 | MET-026 | 0.917 | MET-056 | fixed |
| `mfg_manual_review_0180` | 19 | VLV-041 | VLV-046 | 0.9986 | VLV-041 | fixed |
| `mfg_manual_review_0180` | 20 | ELC-048 | ELC-036 | 0.9798 | - | rejected |
| `mfg_manual_review_0180` | 22 | ELC-013 | ELC-025 | 0.984 | - | rejected |
| `mfg_manual_review_0189` | 15 | SAF-032 | SAF-002 | 0.9112 | SAF-032 | fixed |
| `mfg_manual_review_0189` | 16 | VLV-054 | VLV-059 | 0.9983 | VLV-054 | fixed |
| `mfg_manual_review_0189` | 22 | MET-057 | MET-027 | 0.9244 | MET-057 | fixed |
| `mfg_manual_review_0189` | 23 | CBL-060 | CBL-020 | 0.9989 | CBL-060 | fixed |
| `mfg_manual_review_0189` | 25 | CBL-052 | CBL-012 | 0.9989 | CBL-052 | fixed |
| `mfg_manual_review_0190` | 2 | VLV-050 | VLV-047 | 0.8931 | - | rejected |
| `mfg_manual_review_0190` | 20 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_manual_review_0199` | 3 | SAF-039 | SAF-009 | 0.9429 | SAF-039 | fixed |
| `mfg_manual_review_0199` | 5 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_manual_review_0199` | 13 | CBL-037 | CBL-017 | 0.999 | CBL-037 | fixed |
| `mfg_manual_review_0199` | 17 | VLV-011 | VLV-016 | 0.9984 | VLV-011 | fixed |
| `mfg_manual_review_0199` | 21 | VLV-025 | VLV-030 | 0.9985 | VLV-025 | fixed |
| `mfg_manual_review_0200` | 10 | SAF-040 | SAF-010 | 0.9334 | SAF-040 | fixed |
| `mfg_manual_review_0200` | 15 | VLV-003 | VLV-008 | 0.9982 | VLV-003 | fixed |
| `mfg_manual_review_0209` | 1 | VLV-053 | VLV-057 | 0.9052 | - | rejected |
| `mfg_manual_review_0209` | 11 | SAF-039 | SAF-009 | 0.9429 | SAF-039 | fixed |
| `mfg_manual_review_0209` | 18 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_manual_review_0209` | 26 | MET-051 | MET-016 | 0.9185 | MET-051 | fixed |
| `mfg_manual_review_0210` | 4 | CBL-048 | CBL-008 | 0.999 | CBL-048 | fixed |
| `mfg_manual_review_0210` | 8 | VLV-014 | VLV-019 | 0.9981 | VLV-014 | fixed |
| `mfg_manual_review_0210` | 20 | VLV-041 | VLV-046 | 0.9986 | VLV-041 | fixed |
| `mfg_manual_review_0210` | 22 | CBL-036 | CBL-016 | 0.9988 | CBL-036 | fixed |
| `mfg_manual_review_0210` | 25 | VLV-031 | VLV-036 | 0.9987 | VLV-031 | fixed |
| `mfg_manual_review_0210` | 27 | VLV-054 | VLV-059 | 0.9983 | VLV-054 | fixed |
| `mfg_manual_review_0219` | 2 | VLV-015 | VLV-020 | 0.9984 | VLV-015 | fixed |
| `mfg_manual_review_0219` | 4 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_manual_review_0219` | 7 | SAF-058 | SAF-028 | 0.9087 | SAF-058 | fixed |
| `mfg_manual_review_0219` | 9 | MET-006 | MET-016 | 0.9233 | MET-006 | fixed |
| `mfg_manual_review_0219` | 10 | SAF-050 | SAF-020 | 0.9229 | SAF-050 | fixed |
| `mfg_manual_review_0219` | 18 | MET-046 | MET-031 | 0.9162 | MET-046 | fixed |
| `mfg_manual_review_0219` | 20 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_manual_review_0219` | 22 | VLV-013 | VLV-018 | 0.9983 | VLV-013 | fixed |
| `mfg_manual_review_0220` | 3 | CBL-028 | CBL-008 | 0.999 | CBL-028 | fixed |
| `mfg_manual_review_0220` | 6 | CBL-034 | CBL-014 | 0.9989 | CBL-034 | fixed |
| `mfg_manual_review_0220` | 17 | VLV-033 | VLV-038 | 0.9987 | VLV-033 | fixed |
| `mfg_manual_review_0229` | 17 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_manual_review_0229` | 19 | SAF-038 | SAF-008 | 0.9218 | SAF-038 | fixed |
| `mfg_manual_review_0229` | 20 | CBL-042 | CBL-002 | 0.9991 | CBL-042 | fixed |
| `mfg_manual_review_0229` | 21 | CBL-045 | CBL-005 | 0.999 | CBL-045 | fixed |
| `mfg_manual_review_0230` | 4 | VLV-032 | VLV-037 | 0.9987 | VLV-032 | fixed |
| `mfg_manual_review_0230` | 7 | VLV-005 | VLV-010 | 0.9983 | VLV-005 | fixed |
| `mfg_manual_review_0230` | 9 | MET-011 | MET-016 | 0.9249 | MET-011 | fixed |
| `mfg_manual_review_0230` | 17 | VLV-044 | VLV-049 | 0.9981 | VLV-044 | fixed |
| `mfg_manual_review_0230` | 18 | VLV-013 | VLV-018 | 0.9983 | VLV-013 | fixed |
| `mfg_manual_review_0239` | 4 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_manual_review_0239` | 16 | CBL-038 | CBL-018 | 0.999 | CBL-038 | fixed |
| `mfg_manual_review_0239` | 17 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_manual_review_0240` | 7 | VLV-051 | VLV-056 | 0.9987 | VLV-051 | fixed |
| `mfg_manual_review_0240` | 21 | VLV-012 | VLV-017 | 0.9986 | VLV-012 | fixed |
| `mfg_manual_review_0249` | 3 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_manual_review_0249` | 7 | MET-010 | MET-020 | 0.925 | MET-010 | fixed |
| `mfg_manual_review_0249` | 12 | CBL-032 | CBL-012 | 0.9989 | CBL-032 | fixed |
| `mfg_manual_review_0249` | 17 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_manual_review_0249` | 18 | VLV-011 | VLV-016 | 0.9984 | VLV-011 | fixed |
| `mfg_manual_review_0249` | 20 | VLV-035 | VLV-040 | 0.9986 | VLV-035 | fixed |
| `mfg_manual_review_0250` | 5 | SAF-059 | SAF-029 | 0.9343 | SAF-059 | fixed |
| `mfg_manual_review_0250` | 6 | CBL-044 | CBL-004 | 0.999 | CBL-044 | fixed |
| `mfg_manual_review_0250` | 9 | MET-046 | MET-031 | 0.9162 | MET-046 | fixed |
| `mfg_manual_review_0259` | 4 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_manual_review_0259` | 13 | MET-060 | MET-030 | 0.9167 | MET-060 | fixed |
| `mfg_manual_review_0259` | 17 | CBL-049 | CBL-009 | 0.999 | CBL-049 | fixed |
| `mfg_manual_review_0260` | 10 | SAF-049 | SAF-019 | 0.9358 | SAF-049 | fixed |
| `mfg_manual_review_0269` | 12 | MET-046 | MET-031 | 0.9162 | MET-046 | fixed |
| `mfg_manual_review_0269` | 13 | VLV-032 | VLV-037 | 0.9987 | VLV-032 | fixed |
| `mfg_manual_review_0269` | 17 | CBL-023 | CBL-003 | 0.999 | CBL-023 | fixed |
| `mfg_manual_review_0270` | 12 | MET-048 | MET-018 | 0.9148 | MET-048 | fixed |
| `mfg_manual_review_0270` | 15 | CBL-030 | CBL-010 | 0.999 | CBL-030 | fixed |
| `mfg_manual_review_0279` | 1 | SAF-044 | SAF-014 | 0.9373 | SAF-044 | fixed |
| `mfg_manual_review_0279` | 3 | SAF-047 | SAF-017 | 0.9051 | SAF-047 | fixed |
| `mfg_manual_review_0279` | 6 | VLV-055 | VLV-060 | 0.9986 | VLV-055 | fixed |
| `mfg_manual_review_0279` | 7 | VLV-014 | VLV-019 | 0.9981 | VLV-014 | fixed |
| `mfg_manual_review_0279` | 10 | VLV-033 | VLV-038 | 0.9987 | VLV-033 | fixed |
| `mfg_manual_review_0279` | 13 | SAF-054 | SAF-024 | 0.9441 | SAF-054 | fixed |
| `mfg_manual_review_0279` | 21 | VLV-044 | VLV-049 | 0.9981 | VLV-044 | fixed |
| `mfg_manual_review_0280` | 1 | VLV-041 | VLV-046 | 0.9986 | VLV-041 | fixed |
| `mfg_manual_review_0280` | 17 | VLV-051 | VLV-056 | 0.9987 | VLV-051 | fixed |
| `mfg_manual_review_0280` | 27 | VLV-021 | VLV-026 | 0.9986 | VLV-021 | fixed |
| `mfg_manual_review_0290` | 6 | MET-009 | MET-019 | 0.9259 | MET-009 | fixed |
| `mfg_manual_review_0290` | 8 | CBL-035 | CBL-015 | 0.9989 | CBL-035 | fixed |
| `mfg_manual_review_0290` | 17 | SAF-036 | SAF-006 | 0.9147 | SAF-036 | fixed |
| `mfg_manual_review_0299` | 6 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_manual_review_0299` | 7 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_manual_review_0299` | 16 | SAF-026 | SAF-030 | 0.8975 | SAF-026 | fixed |
| `mfg_manual_review_0300` | 7 | CBL-027 | CBL-007 | 0.999 | CBL-027 | fixed |
| `mfg_manual_review_0300` | 8 | MET-037 | MET-017 | 0.9308 | MET-037 | fixed |
| `mfg_manual_review_0300` | 19 | SAF-054 | SAF-024 | 0.9441 | SAF-054 | fixed |
| `mfg_manual_review_0300` | 25 | CBL-021 | CBL-001 | 0.9991 | CBL-021 | fixed |
| `mfg_manual_review_0300` | 27 | VLV-044 | VLV-049 | 0.9981 | VLV-044 | fixed |
| `mfg_manual_review_0309` | 1 | CBL-041 | CBL-001 | 0.9991 | CBL-041 | fixed |
| `mfg_manual_review_0309` | 4 | CBL-022 | CBL-002 | 0.9991 | CBL-022 | fixed |
| `mfg_manual_review_0309` | 13 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_manual_review_0309` | 14 | MET-014 | MET-029 | 0.9262 | MET-014 | fixed |
| `mfg_manual_review_0309` | 15 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_manual_review_0309` | 20 | CBL-028 | CBL-008 | 0.999 | CBL-028 | fixed |
| `mfg_manual_review_0310` | 1 | MET-008 | MET-018 | 0.9238 | MET-008 | fixed |
| `mfg_manual_review_0310` | 3 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_manual_review_0310` | 13 | MET-046 | MET-031 | 0.9162 | MET-046 | fixed |
| `mfg_manual_review_0310` | 15 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_manual_review_0310` | 18 | MET-054 | MET-019 | 0.9192 | MET-054 | fixed |
| `mfg_manual_review_0310` | 21 | VLV-051 | VLV-056 | 0.9987 | VLV-051 | fixed |
| `mfg_manual_review_0310` | 23 | CBL-031 | CBL-011 | 0.9989 | CBL-031 | fixed |
| `mfg_manual_review_0319` | 3 | SAF-031 | SAF-001 | 0.9086 | SAF-031 | fixed |
| `mfg_manual_review_0319` | 4 | MET-006 | MET-016 | 0.9233 | MET-006 | fixed |
| `mfg_manual_review_0319` | 6 | MET-051 | MET-016 | 0.9185 | MET-051 | fixed |
| `mfg_manual_review_0319` | 8 | SAF-059 | SAF-029 | 0.9343 | SAF-059 | fixed |
| `mfg_manual_review_0319` | 18 | VLV-041 | VLV-046 | 0.9986 | VLV-041 | fixed |
| `mfg_manual_review_0320` | 3 | CBL-025 | CBL-005 | 0.999 | CBL-025 | fixed |
| `mfg_manual_review_0320` | 6 | VLV-013 | VLV-018 | 0.9983 | VLV-013 | fixed |
| `mfg_manual_review_0320` | 20 | MET-008 | MET-018 | 0.9238 | MET-008 | fixed |
| `mfg_manual_review_0329` | 2 | MET-008 | MET-018 | 0.9238 | MET-008 | fixed |
| `mfg_manual_review_0329` | 3 | VLV-024 | VLV-029 | 0.9982 | VLV-024 | fixed |
| `mfg_manual_review_0329` | 9 | VLV-034 | VLV-039 | 0.9983 | VLV-034 | fixed |
| `mfg_manual_review_0329` | 11 | SAF-036 | SAF-006 | 0.9147 | SAF-036 | fixed |
| `mfg_manual_review_0329` | 12 | VLV-022 | VLV-027 | 0.9985 | VLV-022 | fixed |
| `mfg_manual_review_0329` | 14 | CBL-060 | CBL-020 | 0.9989 | CBL-060 | fixed |
| `mfg_manual_review_0329` | 17 | VLV-005 | VLV-010 | 0.9983 | VLV-005 | fixed |
| `mfg_manual_review_0329` | 22 | VLV-015 | VLV-020 | 0.9984 | VLV-015 | fixed |
| `mfg_manual_review_0329` | 23 | CBL-045 | CBL-005 | 0.999 | CBL-045 | fixed |
| `mfg_manual_review_0330` | 4 | SAF-035 | SAF-005 | 0.9295 | SAF-035 | fixed |
| `mfg_manual_review_0330` | 11 | VLV-014 | VLV-019 | 0.9981 | VLV-014 | fixed |
| `mfg_manual_review_0330` | 16 | MET-008 | MET-018 | 0.9238 | MET-008 | fixed |
| `mfg_manual_review_0330` | 19 | VLV-012 | VLV-017 | 0.9986 | VLV-012 | fixed |
| `mfg_manual_review_0339` | 1 | CBL-034 | CBL-014 | 0.9989 | CBL-034 | fixed |
| `mfg_manual_review_0339` | 12 | CBL-023 | CBL-003 | 0.999 | CBL-023 | fixed |
| `mfg_manual_review_0339` | 16 | SAF-060 | SAF-030 | 0.923 | SAF-060 | fixed |
| `mfg_manual_review_0339` | 18 | CBL-044 | CBL-004 | 0.999 | CBL-044 | fixed |
| `mfg_manual_review_0339` | 21 | VLV-032 | VLV-037 | 0.9987 | VLV-032 | fixed |
| `mfg_manual_review_0339` | 22 | VLV-025 | VLV-030 | 0.9985 | VLV-025 | fixed |
| `mfg_manual_review_0340` | 4 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_manual_review_0340` | 5 | VLV-011 | VLV-016 | 0.9984 | VLV-011 | fixed |
| `mfg_manual_review_0340` | 10 | VLV-025 | VLV-030 | 0.9985 | VLV-025 | fixed |
| `mfg_manual_review_0340` | 11 | SAF-041 | SAF-011 | 0.9044 | SAF-041 | fixed |
| `mfg_manual_review_0340` | 23 | CBL-059 | CBL-019 | 0.999 | CBL-059 | fixed |
| `mfg_manual_review_0340` | 24 | CBL-032 | CBL-012 | 0.9989 | CBL-032 | fixed |
| `mfg_manual_review_0340` | 25 | SAF-056 | SAF-030 | 0.8975 | SAF-056 | fixed |
| `mfg_manual_review_0349` | 4 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_manual_review_0349` | 17 | CBL-037 | CBL-017 | 0.999 | CBL-037 | fixed |
| `mfg_manual_review_0349` | 22 | MET-039 | MET-019 | 0.9247 | MET-039 | fixed |
| `mfg_manual_review_0349` | 23 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_manual_review_0349` | 24 | CBL-054 | CBL-014 | 0.9989 | CBL-054 | fixed |
| `mfg_manual_review_0350` | 3 | CBL-054 | CBL-014 | 0.9989 | CBL-054 | fixed |
| `mfg_manual_review_0350` | 16 | CBL-039 | CBL-019 | 0.999 | CBL-039 | fixed |
| `mfg_manual_review_0350` | 21 | VLV-025 | VLV-030 | 0.9985 | VLV-025 | fixed |
| `mfg_manual_review_0359` | 2 | VLV-055 | VLV-060 | 0.9986 | VLV-055 | fixed |
| `mfg_manual_review_0359` | 9 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_manual_review_0359` | 12 | VLV-042 | VLV-047 | 0.9987 | VLV-042 | fixed |
| `mfg_manual_review_0359` | 15 | CBL-024 | CBL-004 | 0.999 | CBL-024 | fixed |
| `mfg_manual_review_0359` | 16 | CBL-038 | CBL-018 | 0.999 | CBL-038 | fixed |
| `mfg_manual_review_0360` | 2 | CUT-021 | CUT-030 | 0.8766 | - | rejected |
| `mfg_manual_review_0360` | 5 | VLV-055 | VLV-060 | 0.9986 | VLV-055 | fixed |
| `mfg_manual_review_0360` | 7 | SAF-053 | SAF-023 | 0.9225 | SAF-053 | fixed |
| `mfg_manual_review_0360` | 8 | CBL-039 | CBL-019 | 0.999 | CBL-039 | fixed |
| `mfg_manual_review_0360` | 13 | SAF-038 | SAF-008 | 0.9218 | SAF-038 | fixed |
| `mfg_manual_review_0360` | 20 | SAF-034 | SAF-004 | 0.9405 | SAF-034 | fixed |
| `mfg_manual_review_0369` | 2 | MET-006 | MET-016 | 0.9233 | MET-006 | fixed |
| `mfg_manual_review_0369` | 4 | CBL-056 | CBL-016 | 0.9988 | CBL-056 | fixed |
| `mfg_manual_review_0369` | 11 | SAF-031 | SAF-001 | 0.9086 | SAF-031 | fixed |
| `mfg_manual_review_0369` | 15 | CBL-055 | CBL-015 | 0.9989 | CBL-055 | fixed |
| `mfg_manual_review_0369` | 19 | VLV-023 | VLV-028 | 0.9986 | VLV-023 | fixed |
| `mfg_manual_review_0369` | 20 | CBL-024 | CBL-004 | 0.999 | CBL-024 | fixed |
| `mfg_manual_review_0369` | 25 | SAF-049 | SAF-019 | 0.9358 | SAF-049 | fixed |
| `mfg_manual_review_0370` | 1 | CBL-060 | CBL-020 | 0.9989 | CBL-060 | fixed |
| `mfg_manual_review_0370` | 10 | SAF-042 | SAF-012 | 0.9095 | SAF-042 | fixed |
| `mfg_manual_review_0370` | 14 | VLV-034 | VLV-039 | 0.9983 | VLV-034 | fixed |
| `mfg_manual_review_0370` | 16 | CBL-033 | CBL-013 | 0.999 | CBL-033 | fixed |
| `mfg_manual_review_0370` | 21 | CBL-038 | CBL-018 | 0.999 | CBL-038 | fixed |
| `mfg_manual_review_0379` | 7 | VLV-001 | VLV-006 | 0.9983 | VLV-001 | fixed |
| `mfg_manual_review_0379` | 9 | CBL-045 | CBL-005 | 0.999 | CBL-045 | fixed |
| `mfg_manual_review_0379` | 28 | MET-053 | MET-018 | 0.9181 | MET-053 | fixed |
| `mfg_manual_review_0380` | 5 | VLV-012 | VLV-017 | 0.9986 | VLV-012 | fixed |
| `mfg_manual_review_0380` | 6 | VLV-021 | VLV-026 | 0.9986 | VLV-021 | fixed |
| `mfg_manual_review_0380` | 17 | SAF-051 | SAF-021 | 0.9119 | SAF-051 | fixed |
| `mfg_manual_review_0380` | 24 | CBL-054 | CBL-014 | 0.9989 | CBL-054 | fixed |
| `mfg_manual_review_0380` | 25 | CBL-058 | CBL-018 | 0.999 | CBL-058 | fixed |
| `mfg_manual_review_0380` | 26 | SAF-056 | SAF-030 | 0.8975 | SAF-056 | fixed |
| `mfg_manual_review_0389` | 13 | CBL-046 | CBL-006 | 0.999 | CBL-046 | fixed |
| `mfg_manual_review_0390` | 3 | SAF-052 | SAF-022 | 0.9152 | SAF-052 | fixed |
| `mfg_manual_review_0390` | 9 | SAF-057 | SAF-027 | 0.9033 | SAF-057 | fixed |
| `mfg_manual_review_0399` | 1 | VLV-051 | VLV-056 | 0.9987 | VLV-051 | fixed |
| `mfg_manual_review_0399` | 19 | SAF-054 | SAF-024 | 0.9441 | SAF-054 | fixed |
| `mfg_manual_review_0399` | 25 | VLV-013 | VLV-018 | 0.9983 | VLV-013 | fixed |
| `mfg_manual_review_0400` | 2 | VLV-051 | VLV-057 | 0.9052 | - | rejected |
| `mfg_manual_review_0400` | 15 | MET-058 | MET-028 | 0.9168 | MET-058 | fixed |
| `mfg_manual_review_0400` | 23 | CBL-029 | CBL-009 | 0.999 | CBL-029 | fixed |
| `mfg_manual_review_0400` | 24 | SAF-039 | SAF-009 | 0.9429 | SAF-039 | fixed |

## Rejected Detailed Items

| document | line | golden | candidate_skus | reason |
| --- | ---: | --- | --- | --- |
| `mfg_auto_approve_0260` | 3 | ELC-001 | ELC-025, ELC-001, ELC-013 | 规格 'CJX2-0910 AC220V' 缺少区分候选 ELC-025（CJX2-0910 AC220V 01）的关键属性 |
| `mfg_auto_approve_0289` | 11 | ELC-008 | ELC-032, ELC-008, ELC-020 | 规格 'CJX2-1210 AC380V' 缺少区分候选 ELC-032（CJX2-1210 AC380V 01）的关键属性 |
| `mfg_auto_approve_0350` | 20 | ELC-038 | ELC-026, ELC-002, ELC-014 | 规格 'CJX2-1210 AC220V' 缺少区分候选 ELC-026（CJX2-1210 AC220V 01）的关键属性 |
| `mfg_auto_correct_0009` | 1 | PKG-021 | PKG-026, PKG-021, PKG-036 | 规格 '300mm*23μm*400m' 与最高相似候选 PKG-026（300mm×25μm×400m）存在冲突 |
| `mfg_auto_correct_0009` | 2 | ELC-029 | ELC-053, ELC-050, ELC-029 | 规格 'CJX2-3210AC220V01' 与最高相似候选 ELC-053（CJX2-3210 AC220V 31）存在冲突 |
| `mfg_auto_correct_0010` | 1 | PNE-049 | PNE-049, PNE-039, PNE-034 | 物料名称 'SDA缸径40行程100' 与最高相似候选 PNE-049（气缸）不兼容 |
| `mfg_auto_correct_0010` | 2 | ELC-021 | ELC-021, ELC-045, ELC-009 | 物料名称 'CJX2 18A 380V' 与最高相似候选 ELC-021（交流接触器）不兼容 |
| `mfg_auto_correct_0019` | 1 | SAF-023 | SAF-023, SAF-053, SAF-025 | 物料名称 '丁腈手套 L码' 与最高相似候选 SAF-023（丁腈防护手套）不兼容 |
| `mfg_auto_correct_0019` | 2 | VLV-047 | VLV-044, VLV-049, VLV-043 | 规格 'Q61F-16PDN20缩径' 与最高相似候选 VLV-044（Q61F-16P DN32 全通径）存在冲突 |
| `mfg_auto_correct_0020` | 1 | ELC-058 | ELC-058, ELC-052, ELC-046 | 物料名称 'CJX2 25A 380V' 与最高相似候选 ELC-058（交流接触器）不兼容 |
| `mfg_auto_correct_0020` | 2 | ELC-031 | ELC-007, ELC-031, ELC-019 | 规格 'CJX2-0910AC380V01' 与最高相似候选 ELC-007（CJX2-0910 AC380V 10）存在冲突 |
| `mfg_auto_correct_0029` | 1 | ELC-003 | ELC-003, ELC-015, ELC-039 | 物料名称 'CJX2 18A 220V' 与最高相似候选 ELC-003（交流接触器）不兼容 |
| `mfg_auto_correct_0029` | 2 | PKG-005 | BRG-006, BRG-001, BRG-004 | 规格 '600毫米*12微米*300m' 与最高相似候选 BRG-006（6005-2RS）存在冲突 |
| `mfg_auto_correct_0030` | 1 | CUT-040 | PNE-022, CUT-033, PNE-017 | 规格 'D20*1004刃' 与最高相似候选 PNE-022（SC-25×125）存在冲突 |
| `mfg_auto_correct_0030` | 2 | SAF-017 | SAF-017, SAF-047, SAF-022 | 物料名称 '丁腈手套 M码' 与最高相似候选 SAF-017（丁腈防护手套）不兼容 |
| `mfg_auto_correct_0039` | 1 | SNS-024 | SNS-022, SNS-025, SNS-024 | 规格 'LJ18A3-8-Z/BX' 与最高相似候选 SNS-022（LJ8A3-8-Z/BX）存在冲突 |
| `mfg_auto_correct_0039` | 2 | ELC-038 | ELC-038, ELC-014, ELC-026 | 物料名称 'CJX2 12A 220V' 与最高相似候选 ELC-038（交流接触器）不兼容 |
| `mfg_auto_correct_0039` | 7 | ELC-002 | ELC-026, ELC-002, ELC-014 | 规格 'CJX2-1210 AC220V' 缺少区分候选 ELC-026（CJX2-1210 AC220V 01）的关键属性 |
| `mfg_auto_correct_0039` | 18 | ELC-011 | ELC-035, ELC-059, ELC-011 | 规格 'CJX2-3210 AC380V' 缺少区分候选 ELC-035（CJX2-3210 AC380V 01）的关键属性 |
| `mfg_auto_correct_0040` | 1 | SNS-036 | SNS-036, SNS-011, SNS-031 | 物料名称 'M6接近开关 4mm' 与最高相似候选 SNS-036（接近传感器）不兼容 |
| `mfg_auto_correct_0040` | 2 | SNS-012 | SNS-012, SNS-022, SNS-007 | 物料名称 'M8接近开关 4mm' 与最高相似候选 SNS-012（接近传感器）不兼容 |
| `mfg_auto_correct_0049` | 1 | BRG-021 | BRG-021, BRG-020, BRG-022 | 物料名称 '轴承6202ZZ' 与最高相似候选 BRG-021（深沟球轴承）不兼容 |
| `mfg_auto_correct_0049` | 2 | ELC-059 | ELC-059, ELC-058, ELC-056 | 物料名称 'CJX2 32A 380V' 与最高相似候选 ELC-059（交流接触器）不兼容 |
| `mfg_auto_correct_0050` | 1 | CUT-015 | BRG-053, BRG-005, BRG-017 | 规格 'D6*604刃' 与最高相似候选 BRG-053（6004-C3）存在冲突 |
| `mfg_auto_correct_0050` | 2 | SAF-052 | SAF-022, SAF-052, SAF-025 | 规格 'NBR-M-15mil黑色' 与最高相似候选 SAF-022（NBR-M-15mil 蓝色）存在冲突 |
| `mfg_auto_correct_0059` | 1 | ELC-021 | ELC-021, ELC-045, ELC-009 | 物料名称 'CJX2 18A 380V' 与最高相似候选 ELC-021（交流接触器）不兼容 |
| `mfg_auto_correct_0059` | 2 | BRG-013 | BRG-013, BRG-016, BRG-018 | 物料名称 '轴承6000ZZ' 与最高相似候选 BRG-013（深沟球轴承）不兼容 |
| `mfg_auto_correct_0060` | 1 | CBL-010 | CBL-010, CBL-030, CBL-050 | 物料名称 'RVVP3*1.0平方' 与最高相似候选 CBL-010（屏蔽控制电缆）不兼容 |
| `mfg_auto_correct_0060` | 2 | MET-051 | MET-017, MET-032, MET-002 | 规格 '1.0毫米*1220*6000' 与最高相似候选 MET-017（1.5mm×1000×2440）存在冲突 |
| `mfg_auto_correct_0069` | 1 | SAF-035 | SAF-005, SAF-035, SAF-010 | 规格 'NBR-XXL-6mil黑色' 与最高相似候选 SAF-005（NBR-XXL-6mil 蓝色）存在冲突 |
| `mfg_auto_correct_0069` | 2 | FST-006 | FST-006, FST-036, FST-008 | 物料名称 '304内六角螺丝 M4*16' 与最高相似候选 FST-006（不锈钢内六角圆柱头螺钉）不兼容 |
| `mfg_auto_correct_0070` | 1 | CUT-016 | BRG-053, FST-036, BRG-017 | 规格 'D8*604刃' 与最高相似候选 BRG-053（6004-C3）存在冲突 |
| `mfg_auto_correct_0070` | 2 | PKG-030 | BRG-001, BRG-006, BRG-037 | 规格 '600宽 25丝 600毫米*25微米*400m' 与最高相似候选 BRG-001（6000-2RS）存在冲突 |
| `mfg_auto_correct_0070` | 20 | ELC-044 | ELC-032, ELC-008, ELC-020 | 规格 'CJX2-1210 AC380V' 缺少区分候选 ELC-032（CJX2-1210 AC380V 01）的关键属性 |
| `mfg_auto_correct_0079` | 1 | PNE-020 | PNE-020, PNE-005, PNE-010 | 物料名称 'SC缸径50行程100' 与最高相似候选 PNE-020（气缸）不兼容 |
| `mfg_auto_correct_0079` | 2 | FST-002 | FST-002, FST-007, FST-022 | 物料名称 '304内六角螺丝 M5*12' 与最高相似候选 FST-002（不锈钢内六角圆柱头螺钉）不兼容 |
| `mfg_auto_correct_0080` | 1 | VLV-052 | VLV-054, VLV-053, VLV-059 | 规格 'Q61F-25PDN20全通径' 与最高相似候选 VLV-054（Q61F-25P DN32 全通径）存在冲突 |
| `mfg_auto_correct_0080` | 2 | MET-019 | MET-017, MET-002, MET-032 | 规格 '3.0毫米*1000*2440' 与最高相似候选 MET-017（1.5mm×1000×2440）存在冲突 |
| `mfg_auto_correct_0089` | 1 | CUT-035 | BRG-005, BRG-017, BRG-053 | 规格 'D6*1004刃' 与最高相似候选 BRG-005（6004-2RS）存在冲突 |
| `mfg_auto_correct_0089` | 2 | FST-025 | FST-025, FST-055, FST-010 | 物料名称 '304内六角螺丝 M10*30' 与最高相似候选 FST-025（不锈钢内六角圆柱头螺钉）不兼容 |
| `mfg_auto_correct_0090` | 1 | VLV-013 | VLV-013, VLV-018, VLV-033 | 物料名称 '304球阀 DN25' 与最高相似候选 VLV-013（不锈钢球阀）不兼容 |
| `mfg_auto_correct_0090` | 2 | ELC-041 | ELC-053, ELC-050, ELC-041 | 规格 'CJX2-3210AC220V22' 与最高相似候选 ELC-053（CJX2-3210 AC220V 31）存在冲突 |
| `mfg_auto_correct_0099` | 1 | SNS-020 | SNS-020, SNS-010, SNS-005 | 物料名称 'M30接近开关 5mm' 与最高相似候选 SNS-020（接近传感器）不兼容 |
| `mfg_auto_correct_0099` | 2 | SNS-054 | SNS-052, SNS-054, SNS-055 | 规格 'LJ18A3-1-Z/EX' 与最高相似候选 SNS-052（LJ8A3-1-Z/EX）存在冲突 |
| `mfg_auto_correct_0100` | 1 | SAF-021 | SAF-021, SAF-051, SAF-025 | 物料名称 '丁腈手套 S码' 与最高相似候选 SAF-021（丁腈防护手套）不兼容 |
| `mfg_auto_correct_0100` | 2 | MET-060 | MET-002, MET-012, MET-032 | 规格 '4.0毫米*1500*6000' 与最高相似候选 MET-002（1.5mm×1000×2000）存在冲突 |
| `mfg_auto_correct_0109` | 1 | BRG-040 | BRG-040, BRG-038, BRG-041 | 物料名称 '轴承60032RZ' 与最高相似候选 BRG-040（深沟球轴承）不兼容 |
| `mfg_auto_correct_0109` | 2 | MET-018 | MET-017, MET-018, MET-002 | 规格 '2.0毫米*1000*2440' 与最高相似候选 MET-017（1.5mm×1000×2440）存在冲突 |
| `mfg_auto_correct_0110` | 1 | FST-050 | FST-047, FST-052, FST-042 | 规格 '316M10*25' 与最高相似候选 FST-047（316 M5×25）存在冲突 |
| `mfg_auto_correct_0110` | 2 | ELC-049 | ELC-013, ELC-001, ELC-025 | 规格 'CJX2-0910AC220V31' 与最高相似候选 ELC-013（CJX2-0910 AC220V 11）存在冲突 |
| `mfg_auto_correct_0119` | 1 | FST-014 | FST-019, FST-014, FST-009 | 规格 '304M8*20' 与最高相似候选 FST-019（304 M8×25）存在冲突 |
| `mfg_auto_correct_0119` | 2 | FST-026 | FST-026, FST-021, FST-011 | 物料名称 '304内六角螺丝' 与最高相似候选 FST-026（不锈钢内六角圆柱头螺钉）不兼容 |
| `mfg_auto_correct_0120` | 1 | TRN-025 | TRN-010, TRN-025, TRN-040 | 规格 'HTD-3M-36齿-10mm' 与最高相似候选 TRN-010（HTD-3M-36齿-8mm）存在冲突 |
| `mfg_auto_correct_0120` | 2 | MET-035 | MET-032, MET-002, MET-012 | 规格 '4.0毫米*1000*3000' 与最高相似候选 MET-032（1.5mm×1000×3000）存在冲突 |
| `mfg_auto_correct_0129` | 1 | TRN-030 | TRN-015, TRN-030, TRN-060 | 规格 'HTD-8M-40齿-10mm' 与最高相似候选 TRN-015（HTD-8M-40齿-8mm）存在冲突 |
| `mfg_auto_correct_0129` | 2 | CBL-037 | CBL-009, CBL-029, CBL-049 | 规格 'RVVP2*2.5毫米²柔性屏蔽' 与最高相似候选 CBL-009（RVVP 2×1.0mm² 普通屏蔽）存在冲突 |
| `mfg_auto_correct_0130` | 1 | PNE-050 | PNE-050, PNE-040, PNE-035 | 物料名称 'SDA缸径50行程100' 与最高相似候选 PNE-050（气缸）不兼容 |
| `mfg_auto_correct_0130` | 2 | CUT-015 | BRG-053, BRG-005, BRG-017 | 规格 'D6*604刃' 与最高相似候选 BRG-053（6004-C3）存在冲突 |
| `mfg_auto_correct_0139` | 1 | CBL-021 | CBL-009, CBL-029, CBL-049 | 规格 'RVVP2*0.5mm²柔性屏蔽' 与最高相似候选 CBL-009（RVVP 2×1.0mm² 普通屏蔽）存在冲突 |
| `mfg_auto_correct_0139` | 2 | BRG-059 | BRG-059, BRG-060, BRG-058 | 物料名称 '轴承6204C3' 与最高相似候选 BRG-059（深沟球轴承）不兼容 |
| `mfg_auto_correct_0139` | 17 | ELC-004 | ELC-028, ELC-004, ELC-040 | 规格 'CJX2-2510 AC220V' 缺少区分候选 ELC-028（CJX2-2510 AC220V 01）的关键属性 |
| `mfg_auto_correct_0140` | 1 | TRN-028 | TRN-013, TRN-028, TRN-058 | 规格 'HTD-3M-40齿-10mm' 与最高相似候选 TRN-013（HTD-3M-40齿-8mm）存在冲突 |
| `mfg_auto_correct_0140` | 2 | CUT-031 | CUT-033, CUT-031, CUT-043 | 规格 'D2*1004刃' 与最高相似候选 CUT-033（D4×100 4刃）存在冲突 |
| `mfg_auto_correct_0149` | 1 | MET-013 | MET-012, MET-002, MET-032 | 规格 '2.0mm*1500*2000' 与最高相似候选 MET-012（1.5mm×1500×2000）存在冲突 |
| `mfg_auto_correct_0149` | 2 | ELC-012 | ELC-012, ELC-048, ELC-036 | 物料名称 'CJX2 40A 380V' 与最高相似候选 ELC-012（交流接触器）不兼容 |
| `mfg_auto_correct_0150` | 1 | CBL-041 | CBL-009, CBL-029, CBL-049 | 规格 'RVVP2*0.5mm²耐油屏蔽' 与最高相似候选 CBL-009（RVVP 2×1.0mm² 普通屏蔽）存在冲突 |
| `mfg_auto_correct_0150` | 2 | PKG-059 | BRG-037, BRG-006, BRG-001 | 规格 '500毫米*25微米*600m' 与最高相似候选 BRG-037（6000-2RZ）存在冲突 |
| `mfg_auto_correct_0150` | 12 | ELC-005 | ELC-029, ELC-005, ELC-041 | 规格 'CJX2-3210 AC220V' 缺少区分候选 ELC-029（CJX2-3210 AC220V 01）的关键属性 |
| `mfg_auto_correct_0159` | 1 | TRN-023 | TRN-053, TRN-008, TRN-023 | 规格 'HTD-5M-30齿-10mm' 与最高相似候选 TRN-053（HTD-5M-30齿-15mm）存在冲突 |
| `mfg_auto_correct_0159` | 2 | TRN-059 | TRN-029, TRN-026, TRN-017 | 规格 'HTD-5M-40齿-15毫米' 与最高相似候选 TRN-029（HTD-5M-40齿-10mm）存在冲突 |
| `mfg_auto_correct_0160` | 1 | BRG-024 | BRG-024, BRG-022, BRG-020 | 物料名称 '轴承6205ZZ' 与最高相似候选 BRG-024（深沟球轴承）不兼容 |
| `mfg_auto_correct_0160` | 2 | SAF-004 | SAF-004, SAF-034, SAF-029 | 物料名称 '丁腈手套 XL码' 与最高相似候选 SAF-004（丁腈防护手套）不兼容 |
| `mfg_auto_correct_0169` | 1 | MET-015 | MET-012, MET-002, MET-032 | 规格 '4.0mm*1500*2000' 与最高相似候选 MET-012（1.5mm×1500×2000）存在冲突 |
| `mfg_auto_correct_0169` | 2 | MET-020 | MET-020, MET-017, MET-005 | 物料名称 '304板 4.0mm' 与最高相似候选 MET-020（304不锈钢板）不兼容 |
| `mfg_auto_correct_0170` | 1 | ELC-053 | ELC-053, ELC-050, ELC-056 | 物料名称 'CJX2 32A 220V' 与最高相似候选 ELC-053（交流接触器）不兼容 |
| `mfg_auto_correct_0170` | 2 | FST-038 | FST-038, FST-053, FST-058 | 物料名称 '316内六角螺丝 M6*16' 与最高相似候选 FST-038（不锈钢内六角圆柱头螺钉）不兼容 |
| `mfg_auto_correct_0179` | 1 | PNE-003 | PNE-002, PNE-007, PNE-012 | 规格 'SC-32*25' 与最高相似候选 PNE-002（SC-25×25）存在冲突 |
| `mfg_auto_correct_0179` | 2 | SNS-022 | SNS-022, SNS-007, SNS-025 | 物料名称 'M8接近开关 8mm' 与最高相似候选 SNS-022（接近传感器）不兼容 |
| `mfg_auto_correct_0180` | 1 | MET-001 | MET-002, MET-032, MET-012 | 规格 '1.0mm*1000*2000' 与最高相似候选 MET-002（1.5mm×1000×2000）存在冲突 |
| `mfg_auto_correct_0180` | 2 | CUT-060 | PNE-022, PNE-012, FST-046 | 规格 'D20*1504刃' 与最高相似候选 PNE-022（SC-25×125）存在冲突 |
| `mfg_auto_correct_0189` | 1 | FST-018 | FST-018, FST-023, FST-022 | 规格 'M6*25' 与最高相似候选 FST-018（304 M6×25）存在冲突 |
| `mfg_auto_correct_0189` | 2 | MET-019 | MET-004, MET-034, MET-019 | 规格 '3.0毫米*1000*2440' 与最高相似候选 MET-004（3.0mm×1000×2000）存在冲突 |
| `mfg_auto_correct_0190` | 1 | VLV-058 | VLV-053, VLV-058, VLV-038 | 规格 'Q61F-25PDN25缩径' 与最高相似候选 VLV-053（Q61F-25P DN25 全通径）存在冲突 |
| `mfg_auto_correct_0190` | 2 | MET-005 | MET-002, MET-012, MET-005 | 规格 '4.0毫米*1000*2000' 与最高相似候选 MET-002（1.5mm×1000×2000）存在冲突 |
| `mfg_auto_correct_0199` | 1 | BRG-008 | BRG-008, BRG-009, BRG-012 | 物料名称 '轴承62012RS' 与最高相似候选 BRG-008（深沟球轴承）不兼容 |
| `mfg_auto_correct_0199` | 2 | CBL-059 | CBL-011, CBL-031, CBL-051 | 规格 'RVVP4*2.5毫米²耐油屏蔽' 与最高相似候选 CBL-011（RVVP 4×1.0mm² 普通屏蔽）存在冲突 |
| `mfg_auto_correct_0200` | 1 | VLV-041 | VLV-041, VLV-046, VLV-044 | 物料名称 '304球阀 DN15' 与最高相似候选 VLV-041（不锈钢球阀）不兼容 |
| `mfg_auto_correct_0200` | 2 | FST-046 | FST-046, FST-051, FST-036 | 物料名称 '316内六角螺丝 M4*25' 与最高相似候选 FST-046（不锈钢内六角圆柱头螺钉）不兼容 |
| `mfg_auto_correct_0209` | 1 | PNE-057 | PNE-037, PNE-042, PNE-032 | 规格 'SDA-25*150' 与最高相似候选 PNE-037（SDA-25×50）存在冲突 |
| `mfg_auto_correct_0209` | 2 | CUT-011 | CUT-013, BRG-005, CUT-033 | 规格 'D2*604刃' 与最高相似候选 CUT-013（D4×60 4刃）存在冲突 |
| `mfg_auto_correct_0210` | 1 | ELC-057 | ELC-045, ELC-057, ELC-021 | 规格 'CJX2-1810AC380V31' 与最高相似候选 ELC-045（CJX2-1810 AC380V 22）存在冲突 |
| `mfg_auto_correct_0210` | 2 | SAF-035 | SAF-005, SAF-035, SAF-010 | 规格 'NBR-XXL-6mil黑色' 与最高相似候选 SAF-005（NBR-XXL-6mil 蓝色）存在冲突 |
| `mfg_auto_correct_0219` | 1 | MET-041 | MET-032, MET-042, MET-012 | 规格 '1.0mm*1500*3000' 与最高相似候选 MET-032（1.5mm×1000×3000）存在冲突 |
| `mfg_auto_correct_0219` | 2 | CUT-018 | PNE-025, CUT-038, CUT-048 | 规格 'D12*604刃' 与最高相似候选 PNE-025（SC-50×125）存在冲突 |
| `mfg_auto_correct_0220` | 1 | VLV-034 | VLV-034, VLV-039, VLV-024 | 物料名称 '304球阀 DN32' 与最高相似候选 VLV-034（不锈钢球阀）不兼容 |
| `mfg_auto_correct_0220` | 2 | VLV-055 | VLV-035, VLV-055, VLV-040 | 规格 'Q61F-25PDN40全通径' 与最高相似候选 VLV-035（Q41F-25P DN40 全通径）存在冲突 |
| `mfg_auto_correct_0229` | 1 | CUT-058 | CUT-038, CUT-048, PNE-025 | 规格 'D12*1504刃' 与最高相似候选 CUT-038（D12×100 4刃）存在冲突 |
| `mfg_auto_correct_0229` | 2 | MET-058 | MET-012, MET-002, MET-032 | 规格 '2.0毫米*1500*6000' 与最高相似候选 MET-012（1.5mm×1500×2000）存在冲突 |
| `mfg_auto_correct_0230` | 1 | PNE-025 | PNE-015, PNE-005, PNE-025 | 规格 'SC-50*125' 与最高相似候选 PNE-015（SC-50×75）存在冲突 |
| `mfg_auto_correct_0230` | 2 | VLV-010 | VLV-025, VLV-005, VLV-030 | 规格 'Q11F-16PDN40缩径' 与最高相似候选 VLV-025（Q41F-16P DN40 全通径）存在冲突 |
| `mfg_auto_correct_0239` | 1 | PNE-037 | PNE-037, PNE-035, PNE-032 | 物料名称 'SDA缸径25行程50' 与最高相似候选 PNE-037（气缸）不兼容 |
| `mfg_auto_correct_0239` | 2 | ELC-033 | ELC-045, ELC-033, ELC-009 | 规格 'CJX2-1810AC380V01' 与最高相似候选 ELC-045（CJX2-1810 AC380V 22）存在冲突 |
| `mfg_auto_correct_0240` | 1 | PNE-012 | PNE-012, PNE-002, PNE-007 | 物料名称 'SC缸径25行程75' 与最高相似候选 PNE-012（气缸）不兼容 |
| `mfg_auto_correct_0240` | 2 | VLV-056 | VLV-051, VLV-056, VLV-041 | 规格 'Q61F-25PDN15缩径' 与最高相似候选 VLV-051（Q61F-25P DN15 全通径）存在冲突 |
| `mfg_auto_correct_0249` | 1 | PNE-009 | PNE-009, PNE-010, PNE-005 | 物料名称 'SC缸径40行程50' 与最高相似候选 PNE-009（气缸）不兼容 |
| `mfg_auto_correct_0249` | 2 | MET-053 | MET-017, MET-002, MET-032 | 规格 '2.0毫米*1220*6000' 与最高相似候选 MET-017（1.5mm×1000×2440）存在冲突 |
| `mfg_auto_correct_0250` | 1 | CBL-049 | CBL-009, CBL-029, CBL-049 | 规格 'RVVP2*1.0mm²耐油屏蔽' 与最高相似候选 CBL-009（RVVP 2×1.0mm² 普通屏蔽）存在冲突 |
| `mfg_auto_correct_0250` | 2 | PNE-043 | PNE-043, PNE-033, PNE-038 | 物料名称 'SDA缸径32行程75' 与最高相似候选 PNE-043（气缸）不兼容 |
| `mfg_auto_correct_0259` | 1 | TRN-011 | TRN-011, TRN-056, TRN-041 | 物料名称 'HTD5M 36齿带轮' 与最高相似候选 TRN-011（同步带轮）不兼容 |
| `mfg_auto_correct_0259` | 2 | TRN-037 | TRN-022, TRN-037, TRN-025 | 规格 'HTD-3M-30齿-12毫米' 与最高相似候选 TRN-022（HTD-3M-30齿-10mm）存在冲突 |
| `mfg_auto_correct_0260` | 1 | CBL-001 | CBL-009, CBL-029, CBL-049 | 规格 'RVVP2*0.5mm²普通屏蔽' 与最高相似候选 CBL-009（RVVP 2×1.0mm² 普通屏蔽）存在冲突 |
| `mfg_auto_correct_0260` | 2 | FST-048 | FST-053, FST-048, FST-052 | 规格 '316M6*25' 与最高相似候选 FST-053（316 M6×30）存在冲突 |
| `mfg_auto_correct_0269` | 1 | SNS-053 | SNS-053, SNS-058, SNS-060 | 物料名称 'M12接近开关 1mm' 与最高相似候选 SNS-053（接近传感器）不兼容 |
| `mfg_auto_correct_0269` | 2 | FST-040 | FST-040, FST-055, FST-060 | 物料名称 '316内六角螺丝 M10*16' 与最高相似候选 FST-040（不锈钢内六角圆柱头螺钉）不兼容 |
| `mfg_auto_correct_0270` | 1 | TRN-037 | TRN-037, TRN-052, TRN-007 | 物料名称 'HTD3M 30齿带轮' 与最高相似候选 TRN-037（同步带轮）不兼容 |
| `mfg_auto_correct_0270` | 2 | SNS-033 | SNS-033, SNS-028, SNS-008 | 物料名称 'M12接近开关 2mm' 与最高相似候选 SNS-033（接近传感器）不兼容 |
| `mfg_auto_correct_0279` | 1 | PKG-051 | PKG-026, PKG-021, PKG-036 | 规格 '300mm*23μm*600m' 与最高相似候选 PKG-026（300mm×25μm×400m）存在冲突 |
| `mfg_auto_correct_0279` | 2 | MET-001 | MET-002, MET-032, MET-012 | 规格 '1.0毫米*1000*2000' 与最高相似候选 MET-002（1.5mm×1000×2000）存在冲突 |
| `mfg_auto_correct_0280` | 1 | FST-052 | FST-052, FST-051, FST-047 | 规格 'M5*30' 与最高相似候选 FST-052（316 M5×30）存在冲突 |
| `mfg_auto_correct_0280` | 2 | PKG-011 | BRG-049, BRG-001, PNE-030 | 规格 '300毫米*17微米*300m' 与最高相似候选 BRG-049（6000-C3）存在冲突 |
| `mfg_auto_correct_0289` | 1 | CUT-020 | PNE-022, PNE-025, FST-041 | 规格 'D20*604刃' 与最高相似候选 PNE-022（SC-25×125）存在冲突 |
| `mfg_auto_correct_0289` | 2 | VLV-031 | VLV-031, VLV-036, VLV-021 | 物料名称 '304球阀 DN15' 与最高相似候选 VLV-031（不锈钢球阀）不兼容 |
| `mfg_auto_correct_0290` | 1 | FST-004 | FST-003, FST-004, FST-002 | 规格 '304M8*12' 与最高相似候选 FST-003（304 M6×12）存在冲突 |
| `mfg_auto_correct_0290` | 2 | FST-002 | FST-002, FST-003, FST-007 | 物料名称 '304内六角螺丝' 与最高相似候选 FST-002（不锈钢内六角圆柱头螺钉）不兼容 |
| `mfg_auto_correct_0299` | 1 | TRN-054 | TRN-054, TRN-009, TRN-060 | 物料名称 'HTD8M 30齿带轮' 与最高相似候选 TRN-054（同步带轮）不兼容 |
| `mfg_auto_correct_0299` | 2 | CUT-030 | PNE-022, PNE-012, FST-041 | 规格 'D20*754刃' 与最高相似候选 PNE-022（SC-25×125）存在冲突 |
| `mfg_auto_correct_0300` | 1 | PKG-053 | PKG-028, PKG-038, PKG-023 | 规格 '450mm*23μm*600m' 与最高相似候选 PKG-028（450mm×25μm×400m）存在冲突 |
| `mfg_auto_correct_0300` | 2 | ELC-034 | ELC-058, ELC-034, ELC-046 | 规格 'CJX2-2510AC380V01' 与最高相似候选 ELC-058（CJX2-2510 AC380V 31）存在冲突 |
| `mfg_auto_correct_0309` | 1 | PKG-054 | PKG-029, PKG-039, PKG-024 | 规格 '500mm*23μm*600m' 与最高相似候选 PKG-029（500mm×25μm×400m）存在冲突 |
| `mfg_auto_correct_0309` | 2 | VLV-011 | VLV-011, VLV-016, VLV-031 | 物料名称 '304球阀 DN15' 与最高相似候选 VLV-011（不锈钢球阀）不兼容 |
| `mfg_auto_correct_0310` | 1 | PKG-047 | PKG-057, PKG-027, PKG-047 | 规格 '400mm*20μm*600m' 与最高相似候选 PKG-057（400mm×25μm×600m）存在冲突 |
| `mfg_auto_correct_0310` | 2 | VLV-007 | VLV-004, VLV-009, VLV-003 | 规格 'Q11F-16PDN20缩径' 与最高相似候选 VLV-004（Q11F-16P DN32 全通径）存在冲突 |
| `mfg_auto_correct_0319` | 1 | SNS-002 | SNS-002, SNS-022, SNS-007 | 物料名称 'M8接近开关 1mm' 与最高相似候选 SNS-002（接近传感器）不兼容 |
| `mfg_auto_correct_0319` | 2 | PKG-013 | BRG-006, PNE-030, BRG-001 | 规格 '450毫米*17微米*300m' 与最高相似候选 BRG-006（6005-2RS）存在冲突 |
| `mfg_auto_correct_0320` | 1 | TRN-001 | TRN-001, TRN-046, TRN-031 | 物料名称 'HTD3M 20齿带轮' 与最高相似候选 TRN-001（同步带轮）不兼容 |
| `mfg_auto_correct_0320` | 2 | BRG-059 | BRG-059, BRG-060, BRG-058 | 物料名称 '轴承6204C3' 与最高相似候选 BRG-059（深沟球轴承）不兼容 |
| `mfg_auto_correct_0329` | 1 | TRN-010 | TRN-010, TRN-055, TRN-040 | 物料名称 'HTD3M 36齿带轮' 与最高相似候选 TRN-010（同步带轮）不兼容 |
| `mfg_auto_correct_0329` | 2 | SAF-002 | SAF-002, SAF-032, SAF-005 | 物料名称 '丁腈手套 M码' 与最高相似候选 SAF-002（丁腈防护手套）不兼容 |
| `mfg_auto_correct_0330` | 1 | SAF-021 | SAF-021, SAF-051, SAF-025 | 物料名称 '丁腈手套 S码' 与最高相似候选 SAF-021（丁腈防护手套）不兼容 |
| `mfg_auto_correct_0330` | 2 | TRN-035 | TRN-020, TRN-035, TRN-041 | 规格 'HTD-5M-24齿-12毫米' 与最高相似候选 TRN-020（HTD-5M-24齿-10mm）存在冲突 |
| `mfg_auto_correct_0339` | 1 | TRN-051 | TRN-051, TRN-006, TRN-036 | 物料名称 'HTD8M 24齿带轮' 与最高相似候选 TRN-051（同步带轮）不兼容 |
| `mfg_auto_correct_0339` | 2 | PNE-056 | PNE-041, PNE-036, PNE-031 | 规格 'SDA-20*150' 与最高相似候选 PNE-041（SDA-20×75）存在冲突 |
| `mfg_auto_correct_0340` | 1 | MET-058 | MET-012, MET-032, MET-002 | 规格 '2.0mm*1500*6000' 与最高相似候选 MET-012（1.5mm×1500×2000）存在冲突 |
| `mfg_auto_correct_0340` | 2 | MET-027 | MET-012, MET-027, MET-017 | 规格 '1.5毫米*1500*2440' 与最高相似候选 MET-012（1.5mm×1500×2000）存在冲突 |
| `mfg_auto_correct_0349` | 1 | ELC-036 | ELC-036, ELC-048, ELC-060 | 物料名称 'CJX2 40A 380V' 与最高相似候选 ELC-036（交流接触器）不兼容 |
| `mfg_auto_correct_0349` | 2 | CUT-038 | CUT-038, PNE-025, CUT-048 | 物料名称 '四刃铣刀 D12' 与最高相似候选 CUT-038（硬质合金立铣刀）不兼容 |
| `mfg_auto_correct_0350` | 1 | PNE-048 | PNE-048, PNE-038, PNE-043 | 物料名称 'SDA缸径32行程100' 与最高相似候选 PNE-048（气缸）不兼容 |
| `mfg_auto_correct_0350` | 2 | TRN-037 | TRN-022, TRN-037, TRN-025 | 规格 'HTD-3M-30齿-12毫米' 与最高相似候选 TRN-022（HTD-3M-30齿-10mm）存在冲突 |
| `mfg_auto_correct_0359` | 1 | FST-038 | FST-038, FST-053, FST-058 | 物料名称 '316内六角螺丝 M6*16' 与最高相似候选 FST-038（不锈钢内六角圆柱头螺钉）不兼容 |
| `mfg_auto_correct_0359` | 2 | ELC-002 | ELC-014, ELC-002, ELC-026 | 规格 'CJX2-1210AC220V10' 与最高相似候选 ELC-014（CJX2-1210 AC220V 11）存在冲突 |
| `mfg_auto_correct_0360` | 1 | FST-011 | FST-007, FST-016, FST-011 | 规格 '304M4*20' 与最高相似候选 FST-007（304 M5×16）存在冲突 |
| `mfg_auto_correct_0360` | 2 | BRG-030 | BRG-030, BRG-028, BRG-029 | 物料名称 '轴承6005OPEN' 与最高相似候选 BRG-030（深沟球轴承）不兼容 |
| `mfg_auto_correct_0369` | 1 | VLV-059 | VLV-054, VLV-059, VLV-044 | 规格 'Q61F-25PDN32缩径' 与最高相似候选 VLV-054（Q61F-25P DN32 全通径）存在冲突 |
| `mfg_auto_correct_0369` | 2 | VLV-027 | VLV-029, VLV-024, VLV-022 | 规格 'Q41F-16PDN20缩径' 与最高相似候选 VLV-029（Q41F-16P DN32 缩径）存在冲突 |
| `mfg_auto_correct_0370` | 1 | TRN-015 | TRN-015, TRN-060, TRN-045 | 物料名称 'HTD8M 40齿带轮' 与最高相似候选 TRN-015（同步带轮）不兼容 |
| `mfg_auto_correct_0370` | 2 | ELC-060 | ELC-060, ELC-048, ELC-036 | 物料名称 'CJX2 40A 380V' 与最高相似候选 ELC-060（交流接触器）不兼容 |
| `mfg_auto_correct_0379` | 1 | CUT-020 | PNE-022, PNE-025, FST-041 | 规格 'D20*604刃' 与最高相似候选 PNE-022（SC-25×125）存在冲突 |
| `mfg_auto_correct_0379` | 2 | VLV-035 | VLV-035, VLV-040, VLV-025 | 物料名称 '304球阀 DN40' 与最高相似候选 VLV-035（不锈钢球阀）不兼容 |
| `mfg_auto_correct_0380` | 1 | CBL-028 | CBL-008, CBL-028, CBL-048 | 规格 'RVVP5*0.75mm²柔性屏蔽' 与最高相似候选 CBL-008（RVVP 5×0.75mm² 普通屏蔽）存在冲突 |
| `mfg_auto_correct_0380` | 2 | PNE-033 | PNE-032, PNE-037, PNE-033 | 规格 'SDA-32*25' 与最高相似候选 PNE-032（SDA-25×25）存在冲突 |
| `mfg_auto_correct_0389` | 1 | VLV-026 | VLV-021, VLV-026, VLV-031 | 规格 'Q41F-16PDN15缩径' 与最高相似候选 VLV-021（Q41F-16P DN15 全通径）存在冲突 |
| `mfg_auto_correct_0389` | 2 | VLV-005 | VLV-025, VLV-005, VLV-030 | 规格 'Q11F-16PDN40全通径' 与最高相似候选 VLV-025（Q41F-16P DN40 全通径）存在冲突 |
| `mfg_auto_correct_0390` | 1 | BRG-024 | BRG-024, BRG-022, BRG-020 | 物料名称 '轴承6205ZZ' 与最高相似候选 BRG-024（深沟球轴承）不兼容 |
| `mfg_auto_correct_0390` | 2 | ELC-038 | ELC-038, ELC-014, ELC-026 | 物料名称 'CJX2 12A 220V' 与最高相似候选 ELC-038（交流接触器）不兼容 |
| `mfg_auto_correct_0399` | 1 | FST-001 | FST-001, FST-003, FST-006 | 物料名称 '304内六角螺丝' 与最高相似候选 FST-001（不锈钢内六角圆柱头螺钉）不兼容 |
| `mfg_auto_correct_0399` | 2 | MET-053 | MET-033, MET-003, BRG-049 | 规格 '2.0毫米*1220*6000' 与最高相似候选 MET-033（2.0mm×1000×3000）存在冲突 |
| `mfg_auto_correct_0400` | 1 | CUT-014 | PNE-022, CUT-034, PNE-025 | 规格 'D5*604刃' 与最高相似候选 PNE-022（SC-25×125）存在冲突 |
| `mfg_auto_correct_0400` | 2 | VLV-009 | VLV-004, VLV-009, VLV-044 | 规格 'Q11F-16PDN32缩径' 与最高相似候选 VLV-004（Q11F-16P DN32 全通径）存在冲突 |
| `mfg_manual_review_0010` | 4 | ELC-011 | ELC-035, ELC-059, ELC-011 | 规格 'CJX2-3210 AC380V' 缺少区分候选 ELC-035（CJX2-3210 AC380V 01）的关键属性 |
| `mfg_manual_review_0010` | 20 | ELC-042 | ELC-030, ELC-006, ELC-042 | 规格 'CJX2-4011 AC220V' 缺少区分候选 ELC-030（CJX2-4011 AC220V 01）的关键属性 |
| `mfg_manual_review_0019` | 1 | ELC-009 | SAF-011, SAF-041, SAF-015 | 规格 '—' 与最高相似候选 SAF-011（NBR-S-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0030` | 2 | VLV-006 | VLV-057, VLV-047, VLV-017 | 规格 '—' 与最高相似候选 VLV-057（Q61F-25P DN20 缩径）存在冲突 |
| `mfg_manual_review_0040` | 2 | CUT-006 | CUT-006, CUT-026, CUT-036 | 规格 'D8×50' 缺少区分候选 CUT-006（D8×50 4刃）的关键属性 |
| `mfg_manual_review_0049` | 1 | SAF-002 | SAF-011, SAF-041, SAF-015 | 规格 '—' 与最高相似候选 SAF-011（NBR-S-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0059` | 1 | CUT-032 | CUT-032, CUT-002, CUT-012 | 规格 'D3×100' 缺少区分候选 CUT-032（D3×100 4刃）的关键属性 |
| `mfg_manual_review_0060` | 2 | SAF-010 | SAF-011, SAF-041, SAF-015 | 规格 '—' 与最高相似候选 SAF-011（NBR-S-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0060` | 6 | ELC-012 | ELC-036, ELC-012, ELC-060 | 规格 'CJX2-4011 AC380V' 缺少区分候选 ELC-036（CJX2-4011 AC380V 01）的关键属性 |
| `mfg_manual_review_0070` | 2 | CBL-043 | CBL-011, CBL-031, CBL-051 | 规格 'RVVP' 缺少区分候选 CBL-011（RVVP 4×1.0mm² 普通屏蔽）的关键属性 |
| `mfg_manual_review_0079` | 1 | CUT-031 | CUT-030, CUT-010, CUT-020 | 规格 '—' 与最高相似候选 CUT-030（D20×75 4刃）存在冲突 |
| `mfg_manual_review_0090` | 2 | SAF-057 | SAF-011, SAF-041, SAF-015 | 规格 '—' 与最高相似候选 SAF-011（NBR-S-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0109` | 1 | MET-060 | FST-013, FST-014, FST-019 | 规格 '—' 与最高相似候选 FST-013（304 M6×20）存在冲突 |
| `mfg_manual_review_0119` | 7 | ELC-004 | ELC-028, ELC-004, ELC-040 | 规格 'CJX2-2510 AC220V' 缺少区分候选 ELC-028（CJX2-2510 AC220V 01）的关键属性 |
| `mfg_manual_review_0119` | 13 | ELC-057 | ELC-033, ELC-009, ELC-057 | 规格 'CJX2-1810 AC380V' 缺少区分候选 ELC-033（CJX2-1810 AC380V 01）的关键属性 |
| `mfg_manual_review_0120` | 2 | MET-047 | FST-013, FST-014, FST-019 | 规格 '—' 与最高相似候选 FST-013（304 M6×20）存在冲突 |
| `mfg_manual_review_0130` | 2 | VLV-051 | VLV-057, VLV-052, VLV-056 | 规格 'Q61F-25P' 缺少区分候选 VLV-057（Q61F-25P DN20 缩径）的关键属性 |
| `mfg_manual_review_0139` | 1 | TRN-015 | SAF-011, SAF-041, SAF-001 | 规格 '—' 与最高相似候选 SAF-011（NBR-S-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0150` | 2 | SAF-021 | SAF-011, SAF-041, SAF-015 | 规格 '—' 与最高相似候选 SAF-011（NBR-S-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0160` | 2 | CBL-052 | CBL-011, CBL-031, CBL-051 | 规格 'RVVP' 缺少区分候选 CBL-011（RVVP 4×1.0mm² 普通屏蔽）的关键属性 |
| `mfg_manual_review_0169` | 1 | PNE-055 | SAF-015, SAF-045, SAF-011 | 规格 '—' 与最高相似候选 SAF-015（NBR-XXL-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0179` | 1 | FST-039 | FST-044, FST-041, FST-034 | 规格 '316' 缺少区分候选 FST-044（316 M8×20）的关键属性 |
| `mfg_manual_review_0180` | 2 | FST-055 | FST-014, FST-004, FST-012 | 规格 '—' 与最高相似候选 FST-014（304 M8×20）存在冲突 |
| `mfg_manual_review_0180` | 20 | ELC-048 | ELC-036, ELC-012, ELC-060 | 规格 'CJX2-4011 AC380V' 缺少区分候选 ELC-036（CJX2-4011 AC380V 01）的关键属性 |
| `mfg_manual_review_0180` | 22 | ELC-013 | ELC-025, ELC-001, ELC-013 | 规格 'CJX2-0910 AC220V' 缺少区分候选 ELC-025（CJX2-0910 AC220V 01）的关键属性 |
| `mfg_manual_review_0190` | 2 | VLV-050 | VLV-047, VLV-042, VLV-046 | 规格 'Q61F-16P' 缺少区分候选 VLV-047（Q61F-16P DN20 缩径）的关键属性 |
| `mfg_manual_review_0199` | 1 | FST-059 | FST-014, FST-004, FST-012 | 规格 '—' 与最高相似候选 FST-014（304 M8×20）存在冲突 |
| `mfg_manual_review_0209` | 1 | VLV-053 | VLV-057, VLV-052, VLV-056 | 规格 'Q61F-25P' 缺少区分候选 VLV-057（Q61F-25P DN20 缩径）的关键属性 |
| `mfg_manual_review_0210` | 2 | PKG-036 | SAF-008, SAF-038, SAF-015 | 规格 '—' 与最高相似候选 SAF-008（NBR-L-8mil 蓝色）存在冲突 |
| `mfg_manual_review_0229` | 1 | SAF-034 | SAF-011, SAF-041, SAF-015 | 规格 '—' 与最高相似候选 SAF-011（NBR-S-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0240` | 2 | FST-029 | FST-014, FST-004, FST-012 | 规格 '—' 与最高相似候选 FST-014（304 M8×20）存在冲突 |
| `mfg_manual_review_0250` | 2 | CBL-045 | CBL-011, CBL-031, CBL-051 | 规格 'RVVP' 缺少区分候选 CBL-011（RVVP 4×1.0mm² 普通屏蔽）的关键属性 |
| `mfg_manual_review_0259` | 1 | TRN-025 | SAF-011, SAF-041, SAF-001 | 规格 '—' 与最高相似候选 SAF-011（NBR-S-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0269` | 1 | ELC-033 | ELC-033, ELC-009, ELC-027 | 规格 'CJX2-1810' 缺少区分候选 ELC-033（CJX2-1810 AC380V 01）的关键属性 |
| `mfg_manual_review_0270` | 2 | MET-044 | FST-013, FST-014, FST-019 | 规格 '—' 与最高相似候选 FST-013（304 M6×20）存在冲突 |
| `mfg_manual_review_0289` | 1 | TRN-015 | SAF-011, SAF-041, SAF-001 | 规格 '—' 与最高相似候选 SAF-011（NBR-S-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0299` | 1 | ELC-015 | ELC-033, ELC-009, ELC-027 | 规格 'CJX2-1810' 缺少区分候选 ELC-033（CJX2-1810 AC380V 01）的关键属性 |
| `mfg_manual_review_0300` | 2 | CBL-038 | BRG-041, BRG-040, SAF-011 | 规格 '—' 与最高相似候选 BRG-041（6004-2RZ）存在冲突 |
| `mfg_manual_review_0319` | 1 | ELC-001 | SAF-011, SAF-041, SAF-015 | 规格 '—' 与最高相似候选 SAF-011（NBR-S-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0330` | 2 | PNE-033 | SAF-015, SAF-045, SAF-011 | 规格 '—' 与最高相似候选 SAF-015（NBR-XXL-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0340` | 2 | CUT-017 | CUT-017, CUT-007, CUT-037 | 规格 'D10×60' 缺少区分候选 CUT-017（D10×60 4刃）的关键属性 |
| `mfg_manual_review_0349` | 1 | PKG-024 | SAF-008, SAF-038, SAF-015 | 规格 '—' 与最高相似候选 SAF-008（NBR-L-8mil 蓝色）存在冲突 |
| `mfg_manual_review_0360` | 2 | CUT-021 | CUT-030, CUT-010, CUT-020 | 规格 '—' 与最高相似候选 CUT-030（D20×75 4刃）存在冲突 |
| `mfg_manual_review_0379` | 1 | MET-030 | FST-013, FST-014, FST-019 | 规格 '—' 与最高相似候选 FST-013（304 M6×20）存在冲突 |
| `mfg_manual_review_0390` | 2 | PNE-055 | SAF-015, SAF-045, SAF-011 | 规格 '—' 与最高相似候选 SAF-015（NBR-XXL-10mil 蓝色）存在冲突 |
| `mfg_manual_review_0400` | 2 | VLV-051 | VLV-057, VLV-052, VLV-056 | 规格 'Q61F-25P' 缺少区分候选 VLV-057（Q61F-25P DN20 缩径）的关键属性 |
