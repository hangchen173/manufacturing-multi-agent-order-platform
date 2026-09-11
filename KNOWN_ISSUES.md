# 已知问题记录

记录时间：2026-09-10
记录范围：Docker 一键启动实测（`docker compose up -d --build`）+ HTTP 接口回归

状态更新：2026-09-10，P0-1 / P0-2 已修复并通过测试与端到端验证。

状态更新：2026-09-11，评测契约与评测基线已核验；移除已过时的待复核项（详见第四节）。

状态更新：2026-09-11，CORD 公开集补跑完成，100/100 成功（原 16 条外部原因失败全部消解，详见第五节）。

状态更新：2026-09-11，新增第六节「评测暴露的行为缺陷」：过度送审、auto_correct 通路缺失、思考模式开关未暴露等，均待修复。

状态更新：2026-09-11，更正第六节版本归因：240 条自建集基线跑的是旧版 `00f4656`，其过度送审、auto_correct 缺失反映**旧版逻辑**，不得归因于当前新增的 HIGH 严重度规则；撤销「当前 AUTO_CORRECT 分支不可达」的判断；并明确「旧端到端基线 / 当前下游重放 / 待执行的新端到端评测」三个口径（见第六节）。

---

## 一、已复现缺陷（P0-1 / P0-2 已修复）

### P0-1 空订单 / 垃圾订单被静默判定为「已完成」（已修复）

- **复现步骤**：`POST /api/upload_text`，`order_text` 为无有效物料信息的乱码文本。
- **实际结果**：

```json
{
  "success": true,
  "status": "completed",
  "matched_order": { "items": [] },
  "risk_result": { "issues": [], "needs_confirmation": false, "overall_confidence": 1.0 }
}
```
  HTTP 状态码 `200`。
- **期望结果**：解析不出任何明细时应拒识，转为 `needs_confirmation` 或 `failed`，并返回 `success=false`，不能用 200 掩盖失败。
- **根因位置**：[order_processing.py](file:///Users/cmh/Documents/AGENT_project/application/orchestrators/order_processing.py#L181-L196)
  `_finalize_order` 只依据「是否存在低匹配分项」和「风控结果是否要求确认」决定终态：

```python
low_match_score = any(
    item.match_score < self.config.risk.match_threshold
    for item in matched_order.items
)
needs_confirmation = low_match_score or risk_check_result.needs_confirmation
```

  当 `matched_order.items` 为空列表时，`any(...)` 恒为 `False`，风控对空订单也不会产生 issue，于是直接进入 `COMPLETED`。**缺少「解析结果为空 / 明细缺失」这一拒识判断。**

- **影响**：垃圾输入或解析失败会被当作成功订单落库，直接违背项目「避免服务返回 200 掩盖失败」的目标，评测中会虚增自动处理覆盖率。

- **修复**：
  1. [order_processing.py](file:///Users/cmh/Documents/AGENT_project/application/orchestrators/order_processing.py#L147-L154) 的 `_process_order_with_parser` 在进入匹配阶段前拦截空明细，调用 `set_error` 将订单置为 `failed` 并返回 `success=false`。
  2. 同文件 `_finalize_order` 增加空 `items` 防御性判断，兜底拒绝。
- **验证**：垃圾文本请求返回 `HTTP 400`，`success=false`，订单状态 `failed`，驳回原因 `未从订单中解析出任何物料明细，已拒绝处理`。

### P0-2 空订单的风控整体置信度为满分（已修复）

- **现象**：与 P0-1 同一次请求中，`risk_result.overall_confidence = 1.0`。
- **问题**：没有任何明细、没有任何证据时给出最高置信度，信号方向相反，容易误导下游与前端展示。
- **关联**：与 P0-1 同源，均在 `_finalize_order` / 风控阶段缺少空订单处理。
- **修复**：[risk_control_agent.py](file:///Users/cmh/Documents/AGENT_project/application/agents/risk_control_agent.py#L108-L116) 的 `_calculate_overall_confidence` 在 `item_count == 0` 时返回 `0.0` 而非 `1.0`，空订单因此落入「置信度低于阈值 → 需要人工确认」分支。
- **验证**：单元测试 `tests/test_order_flow.py::RiskControlEmptyOrderTests` 断言空订单 `overall_confidence == 0.0` 且 `needs_confirmation == True`。

---

## 二、运行与部署风险（前次实测发现，本次因代理可达未复现）

### P1-1 运行时不启用 HuggingFace 离线模式，可能阻塞至 worker 超时

- **现象**：模型已预烤进镜像 `/opt/huggingface`，但服务每次初始化 `SentenceTransformer` 仍会联网访问 `huggingface.co` 校验。网络不可达时首个请求阻塞，直至 gunicorn worker 超时被杀（`WORKER TIMEOUT`），接口返回 500 且响应体是 HTML，破坏 JSON 契约。
- **证据**：
  - 不设置离线变量：首个 `POST /api/upload_text` 返回 500（HTML）；
  - 设置 `HF_HUB_OFFLINE=1` 后：模型 3.6s 加载完成，同一请求返回 200。
- **位置**：[faiss_manager.py](file:///Users/cmh/Documents/AGENT_project/infrastructure/vector_store/faiss_manager.py#L39-L49) 的 `_load_model`；[Dockerfile](file:///Users/cmh/Documents/AGENT_project/Dockerfile) 中已设置 `HF_HOME=/opt/huggingface` 但未设置离线变量。
- **备注**：本次测试时宿主代理可用，未复现；但网络波动时风险仍在。

### P1-2 一键启动强依赖外网

- 构建阶段需访问 Docker Hub 拉取基础镜像，并需访问 HuggingFace 下载嵌入模型。任一不可达都会导致 `docker compose up -d --build` 失败。
- 影响：一键启动不具备离线可复现性。

### P1-3 运行镜像与源码可能不一致

- 前次排查发现容器内 `config.py` 字段与仓库源码不同（`ModelConfig` 结构差异），原因是 Docker Hub 不可达只能使用旧缓存镜像。
- 影响：测试结果可能对不上源码，需在验证前确认镜像确为当前源码构建。

---

## 三、接口与性能（观察项）

### P2-1 订单列表接口返回完整订单原文

- **现象**：`GET /api/orders` 返回的每条摘要中带有完整 `order_text`（含整张 Excel 展开文本），响应体极大。
- **问题**：列表接口返回了远超列表展示所需的数据，`OrderSummary` 前端类型中并无该字段，属于过度取数。

---

## 四、已复核并关闭的事项（2026-09-11）

- **评测数据契约字段命名不一致（已关闭）**：标注与评测代码此前分别使用 `business_decision` 与 `confirmation`，现已统一为 `business_decision`；[contracts.py](file:///Users/cmh/Documents/AGENT_project/evaluation/contracts.py) 对已废弃的 `confirmation` 字段显式报错，并由 `tests/test_evaluation_contract.py` 覆盖。
- **`evaluation/results/` 缺真实基线报告（已关闭）**：已归档自建集基线与公开数据集（CORD）真实评测结果，见第五节。

---

## 五、评测结果归档

### 5.1 公开数据集（CORD v2 test，100 条）

- 归档路径：[cord_v2_test_20260911_012942/summary.md](file:///Users/cmh/Documents/AGENT_project/evaluation/results/cord_v2_test_20260911_012942/summary.md)
- 数据来源：`datasets/public/cord/processed/`（图片输入 + 标注），非自造集。
- 总览：100 条样本全部成功，成功率 **100%**，平均单条耗时 173.8s。
- 字段抽取准确率（分子为命中数、分母为标注中出现的条数）：
  - `quantity`：212/224（**94.64%**）
  - `total_amount`：64/89（**71.91%**）
  - `material_name_raw`：120/257（**46.69%**，明细名称存在模型抽取方差，非指标口径问题）
  - `unit_price`：34/67（50.75%）
  - 明细条数完全一致：73/100（73.00%）
- `needs_confirmation_rate` 为 100%：CORD 票据商品不在本项目 SKU 主数据内，按设计全部转人工确认。
- `specification_raw` / `unit` / `delivery_date` / `order_number` / `customer_name` 均为 0/0：CORD 标注未提供对应字段，指标按契约自动跳过。
- `SKU Top-1` / `confirmation` / `business_decision` 均为 0/0：CORD 为公开数据集，标注不含 `golden_sku_code` 与 `business_decision`，决策类指标整体跳过——这正是评测契约收敛（字段缺失即跳过、不虚增分母）的设计目标。
- 首跑曾因上游账号欠费中断 15 条（`cord_v2_test_083`~`099`，DashScope `type: Arrearage`）、另 1 条模型输出非法 JSON（`cord_v2_test_008`）；账号恢复后用 `--resume-run` 复用 84 条成功行、仅重跑 16 条，**16 条全部转成功**。结论：原失败均为外部账号状态与模型输出稳定性因素，非流水线缺陷。

### 5.2 自建集基线

- 归档路径：[baseline_generated_complex_test_20260910_234250/summary.md](file:///Users/cmh/Documents/AGENT_project/evaluation/results/baseline_generated_complex_test_20260910_234250/summary.md)
- 240 条样本，成功率 100%；`material_name_raw` 99.78%、`specification_raw` 99.25%、`quantity`/`unit`/`unit_price` 均 100%；`sku_top1_accuracy` 80.52%、`business_decision_accuracy` 35.00%。
- 说明：自建集用于回归与鲁棒性验证，公开集（5.1）用于避免「自造集自证」。
- 版本提示：本基线 `run_manifest.json` 的 `code_version = 00f4656`（旧版，无 `business_decision` 字段），其 35.00% 动作命中与 80.52% SKU 均为旧版端到端结果，不能代表当前代码，详见第六节「三个评测口径」。

---

## 六、评测暴露的行为缺陷（2026-09-11 记录，待修复）

来源：[baseline_generated_complex_test_20260910_234250](file:///Users/cmh/Documents/AGENT_project/evaluation/results/baseline_generated_complex_test_20260910_234250/summary.md)（240 条自建集评估结果）+ 代码静态分析。以下逐条区分「已实测」与「待验证假设」。

**版本前提（务必先读）**：该基线报告的 `run_manifest.json` 记录 `code_version = 00f4656b96536b96c1dd2ce3bbc23c9a53a5cedd`（提交信息 "Add dataset"），即**旧版代码**。该版本的预测输出中**不存在 `business_decision` 字段**（`grep` 命中 0 次），也**不存在 `_decide_business_action`**（该符号首现于 `8e06bed`，晚于 `00f4656`）。因此本节 P1-4 / P1-5 的**数字属于旧版行为，不能当作当前代码的实测结论**。

旧版（`00f4656`）风控送审判定为：

```python
needs_confirmation = (
    len(all_issues) > 0 or
    overall_confidence < self.confidence_threshold
)
```

即**任一明细产生任一 issue 即整单送审**，且当时仅有 5 个检查（parsing_confidence / match_score / price_abnormality / delivery_date / quantity）。基线 240 条的 issue 分布为 `price_abnormal 486 / low_match_score 121 / invalid_date_format 2`（共 609 条，几乎每单至少一条），这正是 93.75% 送审的直接来源。

当前版本已改为 `needs_confirmation = any(issue.severity == HIGH)`（见 [risk_control_agent.py](file:///Users/cmh/Documents/AGENT_project/application/agents/risk_control_agent.py#L331-L333)），**与产生上述数字的旧逻辑不同**；当前代码的真实行为需由新一轮端到端评测（P2-8）重新测量，不能沿用旧基线数字。

### P1-4 严重过度送审，自动化率仅 6.25%（旧版 00f4656 已实测；当前代码待重测）

- 数据（旧版 `00f4656`）：`needs_confirmation_rate` 93.75%（225/240）；实际自动放行 15/240 = **6.25%**。
- 交叉表（标注三类各 80 条，均衡）：
  - 标注 `auto_approve` 80 条 → 72 条被误送审，误报率 **90%**；
  - 标注 `auto_correct` 80 条 → 77 条被送审；
  - 标注 `manual_review` 80 条 → 76 条被送审，真风险召回 95%。
- 影响：旧版系统几乎把所有订单转人工，「自动处理」名存实亡；该基线的 `business_decision_accuracy` 被压到 35.00%。
- 归因更正：其根因是**旧版** [risk_control_agent.py](file:///Users/cmh/Documents/AGENT_project/application/agents/risk_control_agent.py#L331-L333) 的「任一 issue 即送审」判定，**不是**当前新增的 HIGH 严重度规则（`any(issue.severity == HIGH)`）。当前 HIGH 规则是否仍过度送审，须由 P2-8 的端到端评测确认。

### P1-5 auto_correct 通路缺失（旧版无该动作；当前分支可达性已更正）

- 事实：基线（旧版 `00f4656`）240 条中输出 `auto_correct` **0 次**。
- 归因更正：`00f4656` 中**根本没有 `business_decision` 字段与 `_decide_business_action`**，动作空间只有「送审 / 自动放行」两类；当时 [contracts.py](file:///Users/cmh/Documents/AGENT_project/evaluation/contracts.py) 的 `predicted_action` 也是「无 `business_decision` 时按 `needs_confirmation` 回退」，所以旧基线既无法产生 `auto_correct`，其 35.00% 动作命中也是**字段回退口径**的产物，而非动作逻辑本身。
- **撤销**此前「[order_processing.py](file:///Users/cmh/Documents/AGENT_project/application/orchestrators/order_processing.py#L252-L279) 的 AUTO_CORRECT 分支因 `needs_confirmation` 为真时提前返回 MANUAL_REVIEW 而不可达」的判断：当前实现中，`needs_confirmation` 为假且存在归一化时，AUTO_CORRECT 分支**可达**。当前下游重放已实测存在自动纠错动作与 `auto_handle_coverage 149/240`（见「三个口径」一节的当前重放列），故「不可达」结论不成立。
- 影响（仅对旧版成立）：旧版基线标注含 80 条 `auto_correct`，其动作指标理论最高被锁在 160/240 = **66.7%**。当前代码的可达性由 P2-8 端到端评测给出真实值。

### 三个评测口径（不得混称）

| 口径 | 版本 / 方法 | SKU 指标 | 动作指标 | 性质 |
|---|---|---|---|---|
| 旧端到端基线 | `00f4656`，真实 Qwen 端到端，240 条自建集 | `sku_top1_accuracy` 80.52% | `business_decision_accuracy` 35.00%（字段回退口径） | 旧版端到端，仅作历史对照 |
| 当前下游重放 | 当前 HEAD，固定旧 `ParsedOrder` 只重放 Matching/Risk/动作，不调 Qwen，240 条 | `sku_accuracy` 98.86%（5789/5856） | `business_decision_accuracy` 92.92%（223/240） | **下游重放，非端到端** |
| 待执行的新端到端 | 冻结修复版本 + 真实 Qwen 全链路，240 条自建集 + 独立验收样本 | 待测 | 待测 | P2-8，唯一可称「新版端到端」的结果 |

- 归属：[旧端到端基线](file:///Users/cmh/Documents/AGENT_project/evaluation/results/baseline_generated_complex_test_20260910_234250/summary.md)；[当前下游重放](file:///Users/cmh/Documents/AGENT_project/evaluation/results/downstream_replay_generated_complex_20260911_202838/replay_summary.json)。
- 口径纪律：下游重放（不调 Parser / Qwen）的 SKU 与动作命中**不等于**端到端准确率；在 P2-8 产出结果前，不得用 98.86% / 92.92% 宣称新版端到端指标，也不得以 80.52% / 35.00% 描述当前代码。

### P1-6 软信号被标为 HIGH 严重度（待验证假设）

- 8 个风控检查中有 6 个直接产 HIGH：[risk_control_agent.py](file:///Users/cmh/Documents/AGENT_project/application/agents/risk_control_agent.py) 的 `_check_non_pack_quantity`（数量非 `PACK_QUANTITY_MULTIPLE`=10 的整数倍）、`_check_price_policy`（单价 > 参考价 1.5 倍）、`_check_unknown_material`（`match_score` < 0.8）、`_check_ambiguous_specification`（规格为空）、`_check_line_total`、`_check_price_abnormality`。
- 其中「非包装数量」「价格超政策」「缺规格」在业务上多为业务事实，当前却与「单价非法」「过期交期」同级别，直接触发整单送审。
- 待验证：需先统计 240 条结果的 `issue_type` 分布，确认哪条规则贡献送审最多，再决定降级范围，避免盲改。

### P1-7 spec-only 兜底匹配无条件打满分（待验证假设）

- 位置：[matching_agent.py](file:///Users/cmh/Documents/AGENT_project/application/agents/matching_agent.py#L58-L80) 的 `_match_by_catalog_key` 在仅命中规格、名称不匹配时仍返回候选；调用方 `_match_item` 对其**无条件赋 `match_score = 1.0`**。
- 风险：可能匹配到错误 SKU → 参考价失真 → 误报价格异常/超政策 → 送审；也可能因分数虚高掩盖真问题。

### P2-2 解析阶段未暴露思考模式开关，单条延迟高（已实测）

- 位置：[parser_agent.py](file:///Users/cmh/Documents/AGENT_project/application/agents/parser_agent.py) 的 `_get_llm_for_scenario` 构造 `ChatOpenAI` 未传 `enable_thinking`；全仓库检索无 `enable_thinking` / `reasoning_effort`。
- 实测（`qwen3.7-plus`，单条 xlsx 订单）：

  | 配置 | total_tokens | 单次调用耗时 |
  |---|---|---|
  | 默认（带思考） | 10739 | 102.1s |
  | `enable_thinking=False` | 5650（-47%） | 30.5s（**-70%**） |

- 链路插桩：整链 113.3s，LLM 仅调用 1 次，占约 **90%**；其余约 11s 为嵌入模型加载 + 读文件 + 匹配 + 风控。
- 备注：关闭思考对字段抽取准确率的影响**尚未实测**，需 A/B 验证后再改（见下）。

### P2-3 参考价查询为线性扫描（代码分析）

- 位置：[matching_agent.py](file:///Users/cmh/Documents/AGENT_project/application/agents/matching_agent.py) 的 `get_reference_prices` 对每条明细在 `faiss_manager.metadata` 上做 `next((row for row in ... if row["sku_code"] == item.sku_code), None)`，复杂度 O(明细数 × 物料库大小)。
- 建议：按 `sku_code` 预建字典索引。

### P2-4 嵌入模型冷启动约 11s（已实测）

- 位置：[faiss_manager.py](file:///Users/cmh/Documents/AGENT_project/infrastructure/vector_store/faiss_manager.py) 的 `_load_model`。链路插桩中 LLM 之外的约 11s 主要来自首次加载 SentenceTransformer。
- 建议：服务启动时预热并常驻。

### 待办：思考模式对抽取准确率的 A/B 验证

- 现状：关闭思考的速度收益已实测（-70%），但准确率影响未知，不能直接全量切换。
- 建议方案：从自建集抽 30 条（三类决策各 10 条）+ CORD 抽 20 条，分别跑「思考开 / 思考关」两配置，对比：字段抽取率（`material_name_raw` / `specification_raw` / `quantity` / `unit_price` / `total_amount`）、`sku_top1_accuracy`、JSON 非法/重试率、单条耗时。
- 预判：干净结构化 xlsx 大概率不受影响；图片 OCR、多明细切分、合计金额类字段风险较高，可考虑按文档类型分层开关。

## 本次实测已确认正常的链路

- 一键启动：`postgres` → `api` → `web` 三容器均 healthy，`GET /api/health` 返回 200。
- 完美订单：解析 → 匹配（`FST-013` 0.99 / `BRG-009` 0.99）→ 风控无风险 → `completed`，符合预期。
- 需人工确认订单：触发 `unknown_material`（匹配分低于阈值）/ `price_abnormal` / `past_delivery`，状态 `needs_confirmation`，`POST /api/confirm` 确认后转 `completed`，符合预期。
- 人工确认端到端（浏览器）：订单 `PO-2026-9001`（`243e9e66-5506-4b50-a99d-61d951e8227f`）在前端展示风险项与明细，人工点击「确认通过」后：
  - 接口状态 `needs_confirmation` → `completed`；
  - 状态流转新增一条 `needs_confirmation -> completed | manually_confirmed`（2026-09-10 15:08:59）；
  - 前端刷新后状态显示「已完成」，确认按钮消失，流转历史完整（6 条）。
