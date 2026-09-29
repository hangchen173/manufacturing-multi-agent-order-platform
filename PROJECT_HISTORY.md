# 项目历史纪录

> **本文件是本仓库唯一的历史纪录文档。**
> 由以下 7 份阶段性报告合并而成，合并后原文件已删除（内容要点全部保留在本文件内）：
> `PROJECT_ANALYSIS.md`、`PROJECT_EVALUATION.md`、`P0_FIX_REPORT.md`、`IMPLEMENTATION_REPORT.md`、
> `PROBLEM_ANALYSIS.md`、`UI_TEST_REPORT.md`、`FIX_REPORT.md`，
> 并吸收了 `MANUFACTURING_ORDER_PLATFORM_GOALS.md`（目标文档）的要点。
>
> 活跃的规范类文档仍然独立存在，不在本文件范围内：
> `MULTI_AGENT_DESIGN.md`（设计文档）、`evaluation/EVALUATION_PLAN.md`（评测方案）、
> `README.md`、`AGENTS.md` 与各目录 `README.md`。

---

## 1. 项目是什么

制造业采购订单解析平台：把 PDF / Excel / 图片 / 文本订单，经多智能体协作转化为**可执行的业务决策**
（自动通过 / 归一化后通过 / 人工审核），而非仅做字段抽取。

**三大目标**（来自原目标文档，是本项目一切取舍的依据）：

1. **可靠执行** —— 订单处理异步化，重复提交、进程重启、任务重试都不破坏状态。
2. **可靠决策** —— 能识别抽取错误、SKU 歧义与业务风险，**不靠模型自报置信度**决定自动通过。
3. **可靠评测** —— 明确区分「请求成功 / 抽取正确 / 匹配正确 / 业务决策正确」。

明确**不做**的事：为「多 Agent」而增加角色数量或引入自由对话。多 Agent 是手段，不是目标。

---

## 2. 里程碑时间线

| 阶段 | 内容 | 测试规模 |
|---|---|---|
| 基线 | 线性单 Agent 流水线 | — |
| 多智能体改造 | 改为**黑板 + 任务 DAG + 对抗协议**；10 个业务 Agent + 1 个 Supervisor；V1–V7 共 14 条架构断言；DeepSeek 与阿里云百炼两家真实 API 端到端跑通 | **199** 用例全绿 |
| P0 缺陷修复 | 修复 4 项 P0（见 §5.1）；CI 补 `services: postgres:16` 与模型缓存，消除集成测试静默跳过 | **209** |
| 架构收口 | 端口上移至 `application/ports/`，消除向量库与文档加载的直达依赖，加分层守卫测试 | **212**（0 跳过） |
| 代码与仓库问题分析 | 全量 AST 静态扫描 + 分层审计 + 凭据扫描 + 历史 blob 扫描 + 测试复跑，产出 P0×1 / P1×6 / P2×10 / P3×3 风险清单 | 212 |
| 真实浏览器端到端测试 | Playwright 驱动真实 Chrome 跑通核心流程，发现 3 个真实缺陷 + 3 个产品缺口；成本 ¥0.02 | 222 |
| 缺陷修复（本轮） | 修复 BUG-1/2/3 与 GAP-3，含变异验证 6/6 与真实环境复测；成本 ¥0.05 | **231**（1 跳过） |

---

## 3. 架构现状

六边形分层，方向严格单向：`interfaces → application → domain`，`infrastructure` 实现 `application/ports/`
中的端口；**唯一**允许跨层装配的地点是组合根 `application/container.py`。

- **三层黑板**：L3 控制状态（仅 Supervisor 可写）/ L2 主张与证据（只追加）/ L1 订单事实（仅 Adjudicator 可写）。
- **7 种言后行为**：REQUEST / INFORM / PROPOSE / CHALLENGE / VERDICT / REFUSE / ESCALATE，无自由对话。
- **对抗协议**：PROPOSE → CHALLENGE（须给可复现反证）→ VERDICT。
- **10 个 Agent 节点**：`structure_scout`、`extractor`、`catalog_matcher`、`semantic_matcher`、
  `disambiguator`、`grounding_verifier`、`policy_risk`、`schedule_risk`、`adjudicator`（+ Supervisor）。
  其中只有 `extractor` 与 `review_assistant` 是 LLM 角色，其余为确定性节点（0 token）。
- **失败语义明确**：预算耗尽 → ESCALATE 到人工，绝不静默通过；结构错误带反馈重抽，超时/截断不带反馈。

**做得好的部分（应保持）：**

1. 分层是真实的，不是文档承诺——`tests/test_layering.py` 用 AST 检查 import 的层名（而非子串匹配），
   不会因注释里出现 "infrastructure" 而误报。
2. 依赖倒置用类型系统兜底——`OrderRepository.collaboration_repositories() -> CollaborationRepositories`
   让「四个仓储必须同源」成为**结构性保证**，而非调用方要记住的约定。
3. Agent 契约克制——`handle(task) -> list[AgentMessage]` 近似纯函数，协作过程可重放、可单测、可追溯。

**结构性弱点：**

1. **运行时是「单线程多智能体」**：协作模型可并行扇出，但部署形态（`workers=1` + `threaded=False`）
   把并发压到 1，DAG 的并行价值在运行时被抹平。
2. **就绪探针与业务写入耦合**：`readiness()` 同时承担健康检查、全表扫描、状态修复三重职责，
   且挂在每请求的 `before_request` 上。
3. **组合根略胖**：`container.initialize()` 内联了加载目录 → 建索引 → 校验 → 装配仓储 → 装配编排器 → 恢复任务，
   是唯一无法被分层守卫约束的地方，也是最容易出现启动竞态的地方。

---

## 4. 客观指标

### 4.1 代码规模（`scripts/audit_layers.py`）

| 层 | 文件数 | 行数 |
|---|---:|---:|
| domain | 8 | 716 |
| application | 35 | 5,062 |
| infrastructure | 12 | 1,097 |
| interfaces | 4 | 212 |
| **合计** | **59** | **7,087** |

### 4.2 质量信号

| 指标 | 实测 | 评价 |
|---|---|---|
| 测试用例 | **231 通过 / 1 跳过** | 好 |
| 跨层违规（非组合根） | **0** | 好 |
| 跨层违规（组合根，已豁免） | 5 | 可接受（依赖倒置的正常代价） |
| 长函数（>60 行） | 4 | 一般 |
| `TODO` / `FIXME` / `HACK` / `XXX` | **0** | 好（债务写在报告里而非代码里） |
| 宽泛 `except Exception` | 25 | 一般（4 处丢失因果链） |
| 死代码 | 1（`assert_no_agent_references`） | 一般 |
| 已跟踪大文件（>500 KB） | 8 个 / 28.7 MB | 差 |
| `.git` 体积 | 40 MB | 差 |
| 未锁定依赖（`>=`） | 3 | 一般 |

### 4.3 真实环境实测

| 项 | 结果 |
|---|---|
| 浏览器端到端（真实 Chrome） | 核心流程全通；10 个 Agent 节点全部执行；成本 ¥0.02 |
| 缺陷修复复测 | 3 个缺陷 + 1 个缺口全部修复；变异验证 6/6；成本 ¥0.05 |
| 单请求延迟 / 吞吐 | 单 worker 串行，实测约 0.12–0.37 单/秒 |

### 4.4 评价结论（原评价报告）

> 整体架构 **优**（零跨层违规，domain 层绝对纯净）；代码质量 **良**；功能完成度 **良**；
> 运行风险 **中偏高**（默认生产路径零测试覆盖 + 持久化策略不一致 + 单 worker 串行）。
>
> **核心判断：架构设计水平明显高于工程完成度。** 骨架立得很正且有自动化验证兜底，
> 但「最后一公里」——生产路径的测试覆盖、持久化一致性、并发容量——尚未收口。
> 总评：**架构 A-，工程完成度 B，生产就绪度 C。**

---

## 5. 缺陷与修复

### 5.1 第一批 P0（已修复）

| 编号 | 问题 | 性质 |
|---|---|---|
| P0-1 | 订单仓储与协作状态仓储后端不一致 | **潜在陷阱**（生产路径不可达） |
| P0-2 | 7 个集成测试在 CI 中被永久跳过 | **真实缺口**（绿灯无意义） |
| P0-3 | 3 个端点零测试覆盖 | **真实缺口** |
| P0-4 | `ESCALATE` 从不发出、`ReviewAssistant` 游离于任务 DAG 之外 | **真实缺陷**（设计与实现不符） |

> 诚实说明：只有 P0-4 是会导致设计承诺落空的真实功能缺陷；P0-1 是拆陷阱而非修线上故障；
> P0-2/P0-3 是验证能力缺口。

### 5.2 第二批：浏览器测试发现的缺陷（已修复）

| 编号 | 问题 | 根因位置 | 复测证据 |
|---|---|---|---|
| BUG-1 | 非法订单号 → HTTP 500 | `infrastructure/repositories/order_repository.py` | `/api/orders/not-a-uuid` → **404** |
| BUG-2 | 非法 `order_text` 会落一条垃圾 `failed` 订单 | `interfaces/http/flask_app.py` | 6 种畸形入参 → 400，**新增订单 0** |
| BUG-3 | 以「已登记别名」书写的订单无法匹配 | `catalog_matcher.py` / `match_keys.py` / `policy_risk.py` / `adjudicator.py` | 两种抽取形态均 → **auto_correct / FST-004** |
| GAP-3 | 413/405 返回 HTML | `interfaces/http/flask_app.py` | 413/405 均 `application/json` |

**关键修复要点：**

- **BUG-2** 原守卫只做真值判断 `if not order_text`，而 `process_order_from_text` **先落订单再跑流水线**，
  于是返回 400 却留下一条注定失败、界面上又无法清理的记录。改为在进入业务链路前做类型与空白校验。
- **BUG-3 是两处独立闸门，只修一个不够：**
  1. 标准库别名是「含规格的整串」（如 FST-004 的 `304内六角螺丝 M8*12`），而原匹配只在名称与规格
     都非空时才查目录，别名索引**从未被查询**。修复：把「名称 + 规格」拼成一个键查别名索引，
     使别名在整串、半拆、拆开三种书写下都能命中；两路各自至多命中一个且指向同一 SKU 才算唯一确定。
  2. 即便匹配成功，`PolicyRisk.check_ambiguous_specification` 仍会因抽取规格为空报 HIGH。
     修复：加**窄豁免**——仅当已接受 SKU 且标准库该行登记了规格时豁免。该豁免**可证明安全**：
     向量路径在规格为空时一律 REFUSE，因此这个状态只可能来自目录行。
  3. 不补造抽取字段——标准规格只记录在 `matched_specification` 与归一化记录中，
     与 `total_amount`「缺失表示未知，禁止补造」的口径一致。

**验证方式**：全量回归 231 项 + **变异验证 6/6**（逐个把修复回退成缺陷形态，确认回归用例确实失败再恢复）
+ 真实 Chrome 与真实 API 复测。修复拆为 4 个逻辑提交，每个中间提交都在临时 worktree 中验证为绿。

**过程中的两个教训**（已固化进团队技能）：

- 集成测试会因环境变量名不符而**静默跳过**，套件照样报 `OK`——只看 `OK` 会得到假绿的回归结论。
  必须先确认跳过项数与原因。
- **服务不会热重载**。改完代码不重启后端就复测，测的是旧代码，会把「修复无效」误判为「修复不完整」。
- LLM 抽取**非确定性**：同一段文本可能整串保留、也可能把规格拆进另一字段。
  只覆盖一种切法等于修了一半——这正是发现第二处闸门的契机。

---

## 6. 风险清单（尚未处理）

### P0 —— 必须立即处理

**泄露的 API 密钥尚未轮换。** 实测两个真实密钥仍存活：

```
backup-before-secret-purge        -> 2 hit(s) [DeepSeek key, DashScope key]
refs/original/refs/heads/develop  -> 2 hit(s) [DeepSeek key, DashScope key]
origin/develop                    -> 0 hit(s)
HEAD                              -> 0 hit(s)
```

DeepSeek 与 DashScope（阿里云）两把密钥仍以明文存在于两个本地 ref（均指向 `8eb3943`）；
同一把 DashScope 密钥亦以明文存在于未跟踪的 `.env`（`.gitignore:21`，从未入库）。

> 本节刻意**不写出密钥前缀**——风险清单本身不应成为新的泄露载体。
> 需要定位时按 ref 名与 `8eb3943` 查即可，不必依赖密钥字面量。

- **后果**：额度被消耗、产生实际账单；若该阿里云密钥同时具备其他服务权限，可能升级为资源滥用。
- **为什么历史重写不够**：重写只能让**未来的** clone 拿不到密钥，**无法 un-leak 已经泄露的值**。
  **轮换是唯一有效补救。**
- **修复**：① 到 DeepSeek / 阿里云控制台吊销并重建密钥；② `git branch -D backup-before-secret-purge`
  与 `git update-ref -d refs/original/refs/heads/develop`；③ `git reflog expire --expire=now --all && git gc --prune=now`。

### P1 —— 高优先级

| ID | 问题 | 要点 |
|---|---|---|
| P1-1 | 单进程串行，并发上限 = 1 | `workers=1` + `threaded=False`；一次处理含多次 LLM 调用，期间其他请求排队；超 `timeout=180` 的 worker 被强杀 → 502 且订单停在中间态。**不可直接调大 `workers`**（会触发 P1-2） |
| P1-2 | 索引构建存在启动竞态（阻塞 P1-1） | 每个 worker 都执行 `container.initialize()`，check-then-act 判定「索引为空」→ 并发 `add_documents` 互相覆盖；**仅在 `workers > 1` 时暴露**。修复：`preload_app = True` 或文件锁 + 幂等校验 |
| P1-3 | `readiness()` 在每次上传请求里做全表扫描与写操作 | 每请求 O(N) 全表读 + 潜在写，与 P1-1 叠加放大排队 |
| P1-4 | 上传文件永不清理 | 全仓库无 `os.remove`/`unlink`；`data/` 持久化，容器重建也不消失 → 磁盘无界增长 |
| P1-5 | `FLASK_DEBUG` 代码默认为 `True` | `config.py:75` 默认 `True`，而 `.env.example` 写 `false`；直接 `python app.py` 会把 Werkzeug 调试器暴露在 `0.0.0.0` → **任意代码执行**。容器路径被 `compose.yaml` 掩盖 |
| P1-6 | 依赖锁定与供应链 | `torch` 未入 `requirements.txt`；3 个依赖未锁版本；LangChain 停在 2 年前且已停止维护 |

### P2 —— 中优先级

| ID | 问题 | 修复方向 |
|---|---|---|
| P2-1 | 索引写非原子（先写 `index.faiss` 再写 `metadata.pkl`） | 临时文件 + `os.replace()` 原子替换；metadata 记录 `ntotal` 交叉校验 |
| P2-2 | `pickle` 反序列化 metadata | 改存 JSON / numpy |
| P2-3 | V1 拓扑断言未接线（死代码） | 加测试接线，或删除该函数 |
| P2-4 | 仓库膨胀 28.7 MB（`.git` 40 MB） | 评估产物改 CI artifact 或 LFS；PDF 夹具保留（有内容哈希依赖） |
| P2-5 | 全表读重复（单请求内多次 `load_all`） | 单请求内复用一次快照 |
| P2-6 | `OrderManager.__init__` 有副作用（构造时归档） | 移出构造函数，由组合根显式调用 |
| P2-7 | 异常处理丢失因果链（4 处未 `from e`） | 统一 `raise ... from e` |
| P2-8 | 长函数（`create_app` 144 行等 4 处） | 按蓝图拆分路由；抽策略函数 |
| P2-9 | 本地开发静默跳过集成测试 | 固化环境变量；对「预期应跑却跳过」发 warning |
| P2-10 | `interfaces` 依赖组合根 | 观察项而非缺陷；建议在分层守卫中显式声明豁免 |

### P3 —— 低优先级

- **P3-1** 无 `LICENSE`（影响合规与外部复用）
- **P3-2** `app.py` 仅做 re-export（可合并进 `flask_app.py`）
- **P3-3** 推理参数按子串匹配 host（`if marker in host`，实际风险极低）

### 产品功能缺口（非崩溃，但影响可用性）

- **GAP-1** `/api/orders/<id>/trace` 与 `/tasks` 已实现且返回丰富数据（含 `claims`、`messages`、
  `verdicts`、任务的 `lease_owner`/`attempts`），但前端 `api.ts` 只暴露 5 个方法，**从未调用**——
  协作轨迹是设计文档 §2.3/§5 的核心交付物，用户却看不到。
- **GAP-2** 无任何 DELETE 路由；`OrderManager.delete_order` / `clear_completed_orders` 均无 HTTP 出口。
  失败订单会在侧栏滞留至 `ORDER_AUTO_ARCHIVE_DAYS = 30` 天。

---

## 7. 确认「无问题」的项（避免重复排查）

- `.env` **未被跟踪**（`.gitignore` 命中），且 `.dockerignore` 显式排除 `.env`、`data/uploads`、
  `evaluation/results` → **密钥不会被烤进镜像**。
- `compose.yaml` 用 `${POSTGRES_PASSWORD:?...}` 强制显式提供，失败即拒绝启动（fail-fast，正确）。
- `tests/*` 中的 "hardcoded password" 命中均为 `api_key="test-only"` 之类的测试替身，非真实凭据。
- 分层守卫用 AST 检查 import 层名，不会因注释含关键字而误报。
- 汇总金额显示 `-` 是**设计如此**（`total_amount` 注明「缺失表示未知，禁止补造」）。
- 输入框占位符「看起来已填入」**不是问题**（实测占位符灰度与正文色不同，且 `textarea` 值为空）。
- 17 MB 上传「连接断开」**不是问题**，服务端正确返回 413（是测试客户端未处理提前响应）。
- 远端 `origin/develop` 与当前 `HEAD` 的密钥扫描命中数均为 **0**。

---

## 8. 改进路线（按「风险 × 修复成本」排序）

**第 1 梯队 —— 立即（小时级，纯运维，零代码风险）**
1. **轮换两把密钥**（P0）——唯一能真正止损的动作。
2. 删除两个持有密钥的本地 ref 并 gc。
3. `FLASK_DEBUG` 默认改 `False`（P1-5）——一行改动，消除一个 RCE 面。

**第 2 梯队 —— 短期（天级，小改动高收益）**
4. `readiness()` 瘦身，`fail_stale_processing_orders()` 移出请求路径（P1-3，同时缓解 P2-5）。
5. 上传文件清理（P1-4）。
6. `preload_app = True`（P1-2）——**解锁横向扩容的前置条件**。
7. `OrderManager.__init__` 去副作用（P2-6）。
8. 补 V1 断言测试接线或删除死代码（P2-3）。

**第 3 梯队 —— 中期（周级，需设计）**
9. 并发模型升级：`workers=4` + 线程/异步 + `timeout` 重新标定（P1-1，依赖第 6 项）。
10. 索引原子写 + metadata 去 pickle（P2-1、P2-2）。
11. 依赖全量锁定 + `torch` 入册（P1-6 前半）。
12. 评估产物出库（P2-4，需重写历史或改 LFS）。
13. 异常链统一 `from e`（P2-7）。

**第 4 梯队 —— 长期（需专项）**
14. LangChain 0.1.x → 现行版本升级 + `supervisor` 拆分（P1-6 后半）——改动面大，应单独立项并配回归基线。
15. 长函数重构（P2-8）。
16. 补齐对比矩阵与实测基线。

---

## 9. 未闭合的设计承诺

- `ReviewAssistant` 已接入任务 DAG（P0-4 已修），但 `REQUEST` 言后行为仍未实际发出。
- 设计文档 §4.3 的对比矩阵缺失。
- V1「Agent 之间不持有引用」目前**无运行期强制**（断言函数存在但未接线，见 P2-3）。
- 并发与吞吐未做基线标定，DAG 的并行价值在 `workers=1` 下无法体现。
