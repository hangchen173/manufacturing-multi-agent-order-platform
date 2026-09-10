# 已知问题记录

记录时间：2026-09-10
记录范围：Docker 一键启动实测（`docker compose up -d --build`）+ HTTP 接口回归

状态更新：2026-09-10，P0-1 / P0-2 已修复并通过测试与端到端验证。

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

## 四、待复核事项

- 评测数据契约字段命名不一致：标注侧使用 `business_decision`，评测代码读取 `confirmation`，可能导致指标为空或统计失真（来自前期代码核对，尚未在本次运行中复核）。
- `evaluation/results/` 缺真实基线报告。

---

## 本次实测已确认正常的链路

- 一键启动：`postgres` → `api` → `web` 三容器均 healthy，`GET /api/health` 返回 200。
- 完美订单：解析 → 匹配（`FST-013` 0.99 / `BRG-009` 0.99）→ 风控无风险 → `completed`，符合预期。
- 需人工确认订单：触发 `low_match_score` / `price_abnormal` / `past_delivery`，状态 `needs_confirmation`，`POST /api/confirm` 确认后转 `completed`，符合预期。
- 人工确认端到端（浏览器）：订单 `PO-2026-9001`（`243e9e66-5506-4b50-a99d-61d951e8227f`）在前端展示风险项与明细，人工点击「确认通过」后：
  - 接口状态 `needs_confirmation` → `completed`；
  - 状态流转新增一条 `needs_confirmation -> completed | manually_confirmed`（2026-09-10 15:08:59）；
  - 前端刷新后状态显示「已完成」，确认按钮消失，流转历史完整（6 条）。
