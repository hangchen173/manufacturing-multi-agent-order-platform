# 制造业多 Agent 智能订单解析系统 — 项目全面分析

> 分析对象：`/Users/cmh/Documents/AGENT_project`
> 分析方式：静态阅读全部业务源码、配置、测试与评测脚本（未运行容器）
> 参照基准：仓库内 `MANUFACTURING_ORDER_PLATFORM_GOALS.md` 自定的六阶段目标

---

## 一、整体目标

系统解决的是**制造业采购订单从非结构化文档到可执行业务决策**的问题。完整链路是：

```
订单文档（PDF / Excel / 图片 / TXT / CSV）
  → LLM 结构化抽取（Qwen，含自检与有限自纠错）
  → 标准物料库匹配（确定性目录匹配 + FAISS 向量检索兜底）
  → 确定性业务风控（金额、价格、交期、包装、规格、歧义）
  → 业务动作三分类：自动通过 / 归一化后通过 / 人工审核
  → 人工确认闭环（确认通过 / 拒绝）+ 全量历史与状态流转留痕
```

设计哲学（与常见的“多智能体自由对话”不同）：**能用确定性规则解决的绝不交给模型**。系统里只有两个真正调用 LLM 的节点（解析、审核辅助），匹配与风控全部是规则代码。项目自述定位是**求职作品集**，面向「后端开发 + Agent 开发」双岗位，强调可证明的可靠性而非功能数量。

---

## 二、主要功能模块

| 模块 | 位置 | 职责 |
| --- | --- | --- |
| 领域模型 | `domain/models.py` | Pydantic 模型：`OrderItem` / `ParsedOrder` / `MatchedOrder` / `RiskCheckResult` / `BusinessDecision` / `FinalOrderResult`；含数值有限性、置信度区间校验 |
| 状态机 | `domain/order_state_machine.py` | 7 状态流转白名单 + 非法流转校验 |
| 业务常量 | `domain/constants.py` | 风险枚举、阈值、缺失字段政策 `FIELD_MISSING_POLICY`、包装约束、支持格式 |
| 解析 Agent | `application/agents/parser_agent.py` | 文本 / 图片两场景；`PydanticOutputParser` 结构化输出；自检（行数一致性、名称可在原文定位、Excel 单元格逐格比对）；最多 2 次自纠错 |
| 匹配 Agent | `application/agents/matching_agent.py` | 归一化（全半角、×、单位别名）→ 目录精确匹配 → 向量 Top-3 兜底；规格硬约束、名称兼容、歧义拒识、阈值拒识；按 SKU 取参考价 |
| 风控 Agent | `application/agents/risk_control_agent.py` | 11 类确定性检查：低置信度、未知物料、歧义、缺规格、缺数量/单价、非包装数量、价格异常、价格超政策、交期、非法数量、行合计不一致、解析遗留问题 |
| 审核辅助 Agent | `application/agents/review_assistant_agent.py` | 只读 RAG：检索标准物料资料 + 确定性风险事实 → 生成中文审核参考，明确禁止替人工做决定 |
| 编排器 | `application/orchestrators/order_processing.py` | 串联 4 阶段；业务动作判定与归一化记录；确认/拒绝；审核建议入口 |
| 阶段协议 | `application/pipeline/stages.py` | `AgentPipelineStage`：状态前置条件 → 执行 → 诊断记录 → 结果持久化，任一失败即置错 |
| 订单服务 | `application/services/order_manager.py` | 订单上下文、快照序列化、乐观并发控制（CAS）、状态流转、归档、僵死订单兜底 |
| 容器 | `application/container.py` | 懒加载装配、索引校验、就绪探针 |
| 文档加载 | `infrastructure/document_processing/document_loader.py` | PDF（PyMuPDF，表格与正文分离）、Excel（pandas）、文本、图片 |
| 仓储 | `infrastructure/repositories/order_repository.py` | 抽象端口 + PostgreSQL 实现（JSONB 快照 + 可查询元数据列 + 归档表） |
| 向量库 | `infrastructure/vector_store/` | FAISS `IndexFlatL2` + pickle 元数据；`catalog.py` 负责物料 CSV 加载与「CSV ↔ 索引」一致性校验 |
| HTTP 接口 | `interfaces/http/flask_app.py` | 7 个路由 + 就绪前置拦截 + 统一 JSON 序列化 |
| 评测 | `evaluation/` | 批量评测、下游重放、指标累加器、运行身份指纹、断点续跑 |
| 前端 | `frontend/src/` | React + TS 单页工作台：提交、结果面板、历史列表、确认/拒绝 |
| 基础设施 | `Dockerfile` / `compose.yaml` / `nginx.conf` / `.github/workflows/` | 三容器编排 + CI/发布流水线 |

### HTTP API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 存活探针（不触碰依赖） |
| GET | `/api/ready` | 就绪探针（校验物料库/索引/数据库） |
| POST | `/api/upload` | 文件上传，**同步**返回完整结果 |
| POST | `/api/upload_text` | 文本订单，**同步**返回完整结果 |
| GET | `/api/orders` | 全量订单摘要（无分页） |
| GET | `/api/orders/{id}` | 订单完整快照 |
| POST | `/api/orders/{id}/review-suggestion` | 生成人工审核参考（触发 LLM） |
| POST | `/api/confirm/{id}` | 人工确认/拒绝 |

---

## 三、技术栈

**后端**：Python 3.11 · Flask 3.0.2 · Gunicorn 23 · Pydantic 2.6 · PostgreSQL 16（psycopg3）· FAISS-CPU · sentence-transformers 2.5.1（`all-MiniLM-L6-v2`，384 维）· PyMuPDF · pandas/openpyxl · LangChain 0.1.x + `langchain-openai`（走 Qwen 的 OpenAI 兼容端点，`enable_thinking=false`）

**前端**：React + TypeScript + Vite + lucide-react + Vitest/jsdom；Nginx 1.27 静态托管并同源代理 `/api`

**工程**：Docker Compose 三服务（postgres / api / web）· GitHub Actions（后端 unittest、前端 vitest+build、双镜像 docker build）· GHCR 发布流水线

**关键设计取舍**：`gunicorn workers=1`（CPU 推理单线程，`torch.set_num_threads(1)` + `faiss.omp_set_num_threads(1)`）；嵌入模型烘进镜像并离线加载（`HF_HUB_OFFLINE=1`）；物料索引与上传文件放 `./data` 挂载卷；PostgreSQL 命名卷持久化订单。

---

## 四、目录结构

```
AGENT_project/
├── app.py                      # 极薄入口，仅导出 Flask app
├── config.py                   # 环境变量 → 5 个 dataclass 配置分组
├── domain/                     # ① 领域层：零外部依赖的纯业务概念
│   ├── models.py  constants.py  exceptions.py  order_state_machine.py
├── application/                # ② 应用层：用例编排
│   ├── agents/                 #    4 个 Agent
│   ├── orchestrators/          #    订单处理编排器
│   ├── pipeline/               #    可复用阶段协议
│   ├── services/               #    OrderManager
│   └── container.py            #    依赖装配
├── infrastructure/             # ③ 基础设施层：外部系统适配
│   ├── document_processing/    #    DocumentLoader
│   ├── repositories/           #    OrderRepository / PostgresOrderRepository
│   └── vector_store/           #    FAISSManager / catalog
├── interfaces/http/            # ④ 接口层：Flask 路由 + 序列化
├── evaluation/                 # 独立评测体系（不混入业务）
│   ├── run_evaluation.py  replay_downstream.py  metrics.py  contracts.py
│   ├── results/  templates/  manifests/  notes/
├── scripts/                    # bootstrap 初始化 + HTTP/重启验证脚本
├── tests/                      # 16 个 unittest 文件，约 2750 行
├── frontend/                   # React 工作台 + Nginx 配置
├── data/                       # 物料 CSV、FAISS 索引、上传文件、样例订单
├── datasets/                   # 公开/自建评测数据集（约 2600 文件）
└── Dockerfile  compose.yaml  gunicorn.conf.py  requirements.txt
```

**分层依赖方向严格单向**：`interfaces → application → domain`，`application → infrastructure`（通过 `OrderRepository` 抽象端口反转依赖），`domain` 不 import 任何框架。`evaluation/` 作为旁路消费者复用 application/infrastructure，不反向污染。

---

## 五、模块依赖与调用关系

### 5.1 装配链（启动）

```
app.py
  └─ interfaces/http/flask_app.py: create_app()
       ├─ ApplicationContainer(config)          # 仅构造，不初始化
       └─ app.extensions["container"] = container
gunicorn post_worker_init
  └─ container.initialize()                     # RLock 保护，幂等
       ├─ config.require_model_api_key()        # 无 Key 直接失败
       ├─ load_material_catalog(CSV)            # 读标准物料库
       ├─ FAISSManager(index_path)              # 加载/创建索引 + 嵌入模型
       ├─ validate_catalog_index(...)           # CSV ↔ 向量 ↔ 元数据 三方一致
       └─ OrderProcessingOrchestrator(
              matching_agent= MatchingAgent(faiss=store),   # 共享同一 store
              review_assistant= ReviewAssistantAgent(faiss=store),
          )
            └─ order_manager.fail_stale_processing_orders()
```

### 5.2 订单处理主链（一次上传）

```
POST /api/upload
 └─ before_request: container.readiness()          # 每次上传前全量校验
 └─ container.orchestrator.process_order_from_document(path)
      ├─ DocumentLoader.load_document()            # → 统一 JSON 文本表示
      ├─ OrderManager.create_order()               # PENDING，落库
      └─ _run_order_pipeline()
           ├─ [PARSING]  ParserAgent.run()
           │     ├─ LLM 抽取 → PydanticOutputParser
           │     ├─ 自检 → 最多 2 次带反馈重抽
           │     └─ persist: OrderManager.update_parsed_order()
           ├─ [MATCHING] MatchingAgent.run()
           │     ├─ 归一化 → 目录精确匹配 → FAISS Top-3 → 约束校验
           │     └─ persist: update_matched_order()
           ├─ MatchingAgent.get_reference_prices()  # 按 SKU 取参考价
           ├─ [RISK_CHECKING] RiskControlAgent.run()
           │     └─ persist: update_risk_result()
           └─ _finalize_order()
                 ├─ _decide_business_action()       # 三分类 + 归一化记录
                 └─ OrderManager.finalize_order()   # 状态机 → COMPLETED / NEEDS_CONFIRMATION
```

阶段执行统一由 `AgentPipelineStage.execute()` 包裹，固定四步：**状态前置条件校验 → 执行 → 诊断落库 → 结果落库**，任一步失败即 `set_error()` 转 `FAILED`。

### 5.3 状态机与并发控制

```
PENDING → PARSING → MATCHING → RISK_CHECKING → COMPLETED
   ↓         ↓          ↓             ↓        ↘ NEEDS_CONFIRMATION → COMPLETED / FAILED
 FAILED ←────┴──────────┴─────────────┘
```

- **状态权威源是数据库**：`OrderManager._update()` 每次从 DB 重新读取快照。
- **乐观并发**：`updated_at` 兼作 CAS 令牌，`UPDATE ... WHERE snapshot->>'updated_at' = %s`，`rowcount==1` 才算成功。两人同时确认只有一次生效。
- **`updated_at` 单调递增**：`max(now, prev + 1µs)`，避免同微秒碰撞。
- **僵死兜底**：`fail_stale_processing_orders(180s)` 把超时未推进的中间态订单置为 `FAILED`。

### 5.4 评测链

`run_evaluation.py`（端到端批量）与 `replay_downstream.py`（固定旧 `ParsedOrder`，只重放匹配/风控/动作）共用 `EvaluationAccumulator`；`build_run_identity()` 对代码版本、工作区文件、Prompt、模型配置、物料/索引摘要、数据集/标注做 SHA256 指纹，身份不一致则拒绝续跑；`attempts.jsonl` 逐条 fsync 落盘支持断点恢复。

---

## 六、当前实现的问题、风险与可优化之处

### A. 架构与可靠性（P0，与项目自定目标差距最大）

1. **上传接口仍是同步阻塞，未实现目标中的异步化。**
   `POST /api/upload` 直接调用 `orchestrator.process_order_from_document()`，把 LLM 全流程跑完才返回。项目目标文档「阶段二」明确要求返回 `202 Accepted` + 持久化任务队列 + Worker，并点名批评「用增加超时时间代替异步化」——但当前 `nginx.conf` 的 `proxy_read_timeout 190s`、`gunicorn timeout = 180` 正是该反模式。**这是全项目最大的目标—实现缺口。**

2. **无任务队列、无重试、无幂等键、无人工重跑入口。**
   `FAILED` 是终态，API 层没有任何重新处理入口；重复提交同一文件会创建全新订单（`create_order` 每次都生成新 UUID），没有幂等键去重。目标文档「阶段二」的验收项（并发幂等、Worker 重启恢复、有限重试）目前均无法演示。

3. **单 Worker 使吞吐成为硬瓶颈且无横向扩展路径。**
   `workers=1` + 单请求同步等待 LLM（最长约 2×60s 重抽 + 风控），单实例吞吐约「分钟级 1 单」。多 Worker 会带来每进程重复加载嵌入模型（约 90MB+ 模型 + torch）与各自独立索引副本，成本陡增。

4. **就绪探针被放在每个上传请求前，且做了 O(N) 全表扫描。**
   `before_request` 对 `/api/upload`、`/api/upload_text` 调用 `container.readiness()`，其中包含 `validate_catalog_index()`（重读 CSV 并逐字段比对 720 行）、`repository.load_index()`、`fail_stale_processing_orders()`（`_load_orders()` 拉取**全部订单完整快照**）。健康检查每 10s 触发一次同样的逻辑。**每次业务请求都附带一次全量数据校验 + 全表读取**，随订单量线性劣化。

5. **`fail_stale_processing_orders` 的 180s 阈值与 180s Gunicorn 超时存在竞态。**
   订单在 LLM 调用期间不会刷新 `updated_at`；一旦单阶段耗时逼近阈值（如超时配置调大、模型变慢），健康检查可能把**正在处理**的订单误判为僵死并置 `FAILED`，随后真实结果又试图写入，造成状态语义混乱。

6. **错误处理退化为字符串，异常类型形同虚设。**
   `domain/exceptions.py` 中 `MatchingException`、`RiskControlException`、`OrchestratorException`、`ValidationException`、`OrderManagerException` **定义了但全项目零引用**（仅 `ParserException`、`DocumentLoadException`、`VectorStoreException`、`InvalidOrderStatusException`、`ConfigurationException` 在用）。Agent 层统一 `except Exception` 后返回 `{"success": False, "message": ...}`，异常被吞成字符串，丢失类型与堆栈，不利于告警与按错误分类统计。

### B. 文档处理能力（P1，与「阶段三」目标差距明显）

7. **Excel 只读第一张 Sheet。** `_load_excel()` 取 `workbook.sheet_names[0]`，目标文档明确要求「XLSX 按工作表和区域读取，不再只读第一张表」。首 Sheet 为封面、明细在多 Sheet 的真实模板会直接失败。

8. **Excel 中间表示丢失单元格坐标与合并区域。** 经 `pandas.read_excel(header=None)` → `to_json(orient="values")` 后只剩二维值数组，没有单元格地址、合并区域、隐藏表信息，无法满足目标中「每个输出物料行能定位到源 Sheet/行」的可追溯性要求。

9. **Excel 强校验依赖单一模板形态。** `_excel_source_items()` 要求存在唯一「序号/行号」列、表头别名精确命中、序号恰为 `1..N` 连续整数；任一不满足即返回 `None`，**静默跳过**整格交叉校验。列顺序变化或表头业务名不同时，最强的确定性护栏会无声失效。

10. **PDF 混合扫描页被整体拒绝。** `_load_pdf()` 中 `if not page.get_text().strip(): raise ValueError(...)`，只要任一页无可提取文字就整份失败；目标要求「PDF 先判断文本可用性，对缺少可用文本的页面走图像解析」。跨页明细、重复表头、扫描页与文本页混排均未覆盖。

11. **公式金额缺缓存值时无显式标记。** 目标要求「公式没有可用结果时显式标记，不编造金额」，当前 Excel 路径由 pandas 求值，缺缓存值时的行为未做显式建模。

### C. 匹配与风控（P1）

12. **置信度门槛实际由模型自报，且字段可空导致检查可能静默失效。**
    `RiskControlAgent._check_parsing_confidence()` 读 `item.confidence_score`，该字段 `Optional`，由 LLM 按 Prompt 里的口语化说明（「信息清晰设为 0.9–1.0」）自行填写；为 `None` 时检查直接跳过。这恰好落回目标文档明确反对的「靠模型自报置信度决定自动通过」。订单级 `parsing_confidence` 则**计算后从未参与任何决策**，属装饰性字段。

13. **任一 HIGH 风险即整单转人工，自动处理覆盖率天然偏低。**
    `needs_confirmation = any(severity == HIGH)`，而 HIGH 覆盖未知物料、歧义、缺规格、缺数量、缺单价、非包装数量、超政策价格、过期交期、行合计不符、解析遗留问题等十余种情形。目标文档要求「不以全部转人工换取好看的风险召回率」，当前设计在该取舍上明显偏向保守。

14. **参考价按 SKU 线性扫描。** `get_reference_prices()` 与 `ReviewAssistantAgent._find_doc_by_sku()` 均用 `next(row for row in metadata if ...)` 做 O(N) 遍历，未建 `sku_code → row` 字典索引（目标「阶段一」明确要求「参考价按 SKU 精确查询」）。

15. **相似度阈值缺乏依据支撑。** `_calculate_match_score = 1 - L2/2` 是自定义映射，0.8 阈值在此映射下的语义（对应多大 L2 距离）没有标定；虽然未错误命名为「概率」，但阈值本身缺少 dev 集调优记录。

### D. 安全（P1，几乎完全空白）

16. **全系统零认证、零授权。** 全仓库检索 `auth / token / login / jwt / permission` 在业务代码中**无任何命中**。任何能访问 `:8080` 的人都可以：列出全部订单、读取任意订单的完整快照（含 `order_text` 原始客户订单内容与 `document_path` 服务器路径）、确认或拒绝任意订单、并触发 LLM 调用。目标文档「阶段五」要求的「无鉴权用户不能读取或确认其他用户的订单」完全未实现。

17. **无速率限制 → 直接的 LLM 成本攻击面。** 匿名用户可无限次上传，每次消耗 Qwen token，且仅受 `MAX_CONTENT_LENGTH = 16MB` 约束，无并发/频率/日额度控制。

18. **文件校验只看扩展名，不看真实格式。** `allowed_file()` 仅比对后缀白名单，未校验 magic bytes；目标要求「文件扩展名与实际格式校验」。同时缺少 XLSX 解压大小、Sheet 数、行列规模等资源限制（解压炸弹防护）。

19. **上传文件无保留策略且路径外泄。** 文件以 `uuid_原名` 存于 `./data/uploads`（bind mount 到宿主机），**永不清除**；`document_path` 随订单详情返回前端并展示文件名。目标要求「上传文件保留策略与订单记录关联，不能当普通缓存随意删除」。

20. **`FLASK_DEBUG` 默认值为 `True`。** `config.py` 中 `_get_bool_env("FLASK_DEBUG", default=True)`；Compose 显式设为 `false` 掩盖了该问题，但本地直跑（无 `.env`）时会以 debug 模式启动。

21. **`RISK_EVALUATION_AS_OF` 可静默改变生产行为。** 该变量本意是评测时点冻结，一旦在生产环境被设置，交期判断将永久固定在某个历史日期而无人察觉，且无启动期告警。

### E. 性能与可观测性（P1/P2）

22. **`GET /api/orders` 无分页且反序列化全量快照。** `list_order_summaries()` 走 `_load_orders()` → 对每张订单执行 `OrderProcessingContext.from_snapshot()`（含 Pydantic 全量校验 `parsed_order`/`matched_order`/`risk_result`/`final_result`），只为产出十几个摘要字段。订单量增长后响应体与 CPU 均线性膨胀；仓储层其实已有 `load_index()` 聚合查询可用而未用。

23. **`OrderManager.__init__` 中执行归档副作用。** 构造即调用 `archive_terminal_orders()`（全表读取 + 逐条 CAS 归档）。容器初始化、评测构造都会触发；评测用的内存仓储也会跑一遍，属意外耦合。

24. **FAISSManager 懒加载存在重复加载嵌入模型的风险。** `MatchingAgent` 与 `ReviewAssistantAgent` 各自持有 `_faiss_manager` 且默认懒建。容器正确注入了共享 store，但任何绕过容器直接构造编排器/Agent 的路径（如 `create_evaluation_orchestrator` 未传 `review_assistant`）都会让每个 Agent 各自加载一份 `SentenceTransformer`，内存成倍增长。建议把向量库改为显式必需依赖，去掉懒加载兜底。

25. **审核辅助链路无用量统计，与解析链路不对称。** `ReviewAssistantAgent._get_llm()` 未挂 `UsageHandler` 回调，不记录 token 消耗，无法纳入成本核算。

26. **缺少结构化日志与指标端点。** 目标「阶段五」要求按 `order_id`、阶段、排队/解析/匹配/总耗时、模型错误与重试定位问题。当前 `processing_diagnostics` 确实按订单落库（设计不错），但服务侧只有自由文本日志，无 `/metrics`、无 trace id、无按阶段聚合的错误率。

### F. 代码质量与一致性（P2）

27. **前端 `main.tsx` 的 `App` 返回语句是单行巨型 JSX**（第 73 行，数百字符），`ResultPanel` 已抽组件但主布局未拆分，可读性与可测性差；`api.ts` 的 `submitFile(file as File)` 存在不必要的类型断言。

28. **`replay_downstream.py` 直接调用私有方法 `orchestrator._process_matching_phase()`**，评测脚本耦合业务私有 API，重构时易静默失效。

29. **仓储 schema 用 `CREATE TABLE IF NOT EXISTS` 在构造函数里建**，无迁移工具；后续加列/改约束需手工介入。

30. **依赖版本偏旧且部分未锁定。** LangChain 0.1.12 / Pydantic 2.6.4 / torch 2.2.2（2024 年初代际），`faiss-cpu>=1.8.0` 未固定，`frontend/package.json` 大量 `"latest"`（依赖 lockfile 兜底）。虽然评测用文件指纹保证了单次运行可追溯，但重建环境时版本漂移风险偏高。

31. **仓库卫生。** `data/`、`scripts/`、`frontend/` 下存在已提交的 `.DS_Store`；`datasets/`（约 2600 文件）与 `frontend/node_modules` 体量庞大，克隆成本高。

---

## 七、优先级建议

| 优先级 | 事项 | 对应问题 |
| --- | --- | --- |
| **P0** | 上传接口异步化（202 + 持久化任务队列 + Worker + 幂等键 + 有限重试 + 人工重跑） | A1、A2、A3 |
| **P0** | 加认证与订单级授权，上传加限流 | D16、D17 |
| **P0** | 就绪探针与业务请求解耦；僵死判定与执行超时统一口径 | A4、A5 |
| **P1** | Excel 多 Sheet + 单元格坐标中间表示；PDF 按页文本可用性路由 | B7–B11 |
| **P1** | 置信度改为「候选分差 + 规格冲突 + 信息完整度」的组合判据，移除模型自报依赖 | C12 |
| **P1** | 文件真实格式校验 + XLSX 资源限制 + 上传保留策略 | D18、D19 |
| **P1** | `sku_code → row` 索引；`/api/orders` 分页与投影查询 | C14、E22 |
| **P2** | 恢复异常类型语义、结构化日志、审核链路用量统计、前端拆分 | A6、E25、E26、F27 |

---

## 八、总体评价

**做得好的地方**：分层边界干净且依赖方向正确；状态机 + `updated_at` CAS 乐观锁是正确且可证明的并发方案；`FIELD_MISSING_POLICY` 把「缺失即未知、禁止猜测」贯彻到了 Prompt、模型校验与风控三处；匹配层的「规格硬约束 + 名称兼容 + 歧义拒识」不迷信向量 Top-1；评测体系（运行身份指纹、逐条 fsync 落盘、断点续跑、端到端与下游重放严格区分口径）在同类个人项目中属于明显高于平均的水准；CI 覆盖后端测试、前端测试与构建、双镜像构建。

**核心判断**：这是一个**业务规则与评测工程做得扎实、但生产化程度仍停留在「单机同步原型」**的系统。项目目标文档自己已经把差距写得很清楚——异步化、多 Sheet/混合 PDF、拒识判据、安全边界、可观测性五项基本都还是「待做」。当前状态距离文档定义的「完成标准」（有可信基线、有可靠任务执行、有可解释拒识、有真实格式回归，并能用测试和报告证明）还有明确距离，其中**异步化与认证**是两条最值得优先补齐的主线。
