# 课程设计评审报告

> 评审对象：制造业多 Agent 智能订单解析系统
> 评审基准：本科/硕士课程设计「优秀」等级
> 评审方式：全量代码阅读 + AST 静态分析 + 测试实跑 + git 历史扫描
> 所有结论均附可复现证据（文件:行号 / 实测数字 / 命令）

---

## 0. 结论先行

**达到优秀标准，且处于「优秀」档位的上沿。**

这个判断不是基于代码量，而是基于三件多数课程设计做不到的事：

1. **架构有强制力，不是纸面架构。** 六边形分层由 AST 测试守卫（`tests/test_layering.py`），跨层违规实测 **0**；`domain` 层的外部依赖只剩 stdlib + pydantic。
2. **架构主张可证伪。** `tests/test_verification_v1_v7.py` 的 V1–V7 是**架构断言**而非功能回归：V3 用注入幻觉证明独立验证者的召回率**严格高于**自我确认基线；V5 逐个禁用 Agent 验证**无装饰性角色**；V6 实测 DAG 扇出延迟随行数摊薄。这是把「我们做了多 Agent」变成「我们证明了多 Agent 有效」。
3. **评测有出处。** `evaluation/run_manifest.json` 记录代码版本、工作区指纹、提示词指纹、模型与阈值、物料/FAISS 摘要、数据集指纹、评测时点；版本不一致时**拒绝 resume**（`evaluation/README.md:28`）。这是研究级而非作业级的可复现性实践。

**距离「优秀上沿的天花板」还差三件事**（详见 §5）：设计文档 §4.3 承诺的单 Agent 对比矩阵缺失、生产并发上限=1、以及文档中的自报指标已落后于代码。

---

## 1. 总评表

| 维度 | 评级 | 一句话结论 | 核心判断 |
|---|---|---|---|
| **功能完整性** | **优秀** | 订单全生命周期闭环，10 个 Agent 全链路可跑通，人工确认与故障恢复均已落地 | 主干完整，缺的是「把已实现的能力露出来」（协作轨迹未接入前端）与运维收尾（上传文件不清理） |
| **技术难度** | **优秀** | 六边形架构 + 任务 DAG + 租约 + CAS 状态机 + 对抗协议 + 预算熔断 + 上下文切片，任一单项都够做课程设计 | 难度显著高于课程设计常规水位，且不是堆砌——每项机制都有对应的测试或断言 |
| **代码质量** | **良+** | 分层零违规、domain 绝对纯净、241 项测试全绿、债务标记 0；扣分在长函数与并发模型 | 骨架质量是 A 级；「最后一公里」的工程收口未完成 |
| **创新性** | **优秀** | 「用独立验证者对抗自我确认」是可证伪的设计主张，配套 V1–V7 断言形成完整证据链 | 这是本项目最突出的部分，也是最能拿到答辩高分的部分 |
| **文档与可维护性** | **良+** | 设计文档 32 KB + 历史纪录 19 KB + 逐目录 README + 评测方案，密度罕见；扣分在缺 LICENSE 与自报指标失真 | 文档**多**且**好**，但存在与代码不同步的条目，反而构成可信度风险 |

**综合：优秀（86–90 / 100 区间）。** 若补上 §5 的前三项，可稳定进入 93+ 的「优秀上沿」。

---

## 2. 客观指标（实测）

### 2.1 代码规模

| 层 | 行数 | 说明 |
|---|---:|---|
| `domain` | 716 | 纯领域模型，无框架依赖 |
| `application` | 5,116 | Agent 11 个 + 黑板 + 协议 + 编排 |
| `infrastructure` | 1,118 | 仓储、文档解析、向量库 |
| `interfaces` | 229 | Flask 适配层 |
| `tests` | 4,080 | 测试代码 ≈ 业务代码的 55% |
| `evaluation` | 1,700 | 独立评测体系 |
| `scripts` | 899 | 运维与验证脚本 |
| **Python 合计** | **13,858** | 排除 `.venv` / `node_modules` / `__pycache__` |
| `frontend/src` | 2,235 | 含本轮 Win98 换肤新增的 `components.css` 901 行 |

> **与文档的差异（需修正）**：`PROJECT_HISTORY.md` §4.1 记录 `application` 5,062 / `infrastructure` 1,097 / `interfaces` 212，合计 7,087。实测为 5,116 / 1,118 / 229。代码在文档写成之后又增长过，文档未同步。

### 2.2 质量信号

| 指标 | 实测 | 评价 |
|---|---|---|
| 后端测试 | **231 通过 / 8 跳过**（5.5s） | 好 |
| 前端测试 | **10 通过 / 10**（Vitest 4.1.11） | 好 |
| 测试声明数 | 224 个 `def test_`，分布在 19 个文件 | 好 |
| 跨层违规（非组合根） | **0** | 好 |
| 跨层违规（组合根豁免） | 5（全部在 `application/container.py`） | 可接受，依赖倒置的正常代价 |
| `domain` 外部依赖 | 仅 `typing` / `enum` / `uuid` / `datetime` / `math` / pydantic | 优 |
| `TODO` / `FIXME` / `HACK` / `XXX` | **0** | 好（债务写在报告里，不写在代码里） |
| 长函数（>60 行） | 业务层 **6** 个，全仓 **12** 个 | 一般 |
| 密钥泄漏（全 git 历史） | **0** | 优 |
| `.env` 是否入库 | 否（`.gitignore` 命中） | 优 |
| `LICENSE` | **缺失** | 差 |

> **长函数明细（实测）**：`create_app` 162 行（`interfaces/http/flask_app.py:23`）、`build_slice` 98 行（`application/blackboard/slices.py:42`）、`catalog_matcher.handle` 70 行、`disambiguator.decide` 66 行、`stages.execute` 65 行、`source_map.excel_source_items` 61 行；评测侧另有 6 个（`run_evaluation.run` 170 行等，属一次性脚本，影响较小）。
> **与文档的差异**：`PROJECT_HISTORY.md` §4.2 记「长函数 4 个」，与实测不符（阈值与统计范围不同所致，但文档未说明口径）。

### 2.3 跳过测试归因（重要）

8 项跳过不是「不重要」，而是**本地环境缺条件**：

- 7 项 `PostgresStorageTests` —— 未设 `TEST_DATABASE_URL`
- 1 项 `RuntimeIntegrationTests` —— 未设 `RUN_EMBEDDING_INTEGRATION=1`

CI 中这两组**均已打开**（`.github/workflows/ci.yml` 使用 `services: postgres:16` 并注入两个环境变量），因此跳过是本地现象而非 CI 假绿。这一点在 `PROJECT_HISTORY.md` §5.2 有明确教训记录，属于团队已识别的坑。

### 2.4 密钥安全（全历史扫描）

```
git log --all -- .env                    → 空（从未提交）
git log --all -p | grep 'sk-...'         → 0 命中
git log --all -p | grep 'QWEN_API_KEY='  → 仅占位符 your_qwen_api_key_here / 空值
```

**结论：当前仓库无密钥泄漏。** 历史上曾进入本地 git 历史的密钥已按 `PROJECT_HISTORY.md` §6 清除（`.git` 40 MB → 3.1 MB），且从未推送至远端。**仅剩人工动作**：到控制台轮换密钥——这是唯一能真正止损的一步。

---

## 3. 架构评价

### 3.1 做得好的地方（带证据）

**① 分层不是口号，是自动化约束。**
`tests/test_layering.py` 用 AST 检查 import 的**层名**（而非字符串匹配，因此注释里出现关键字不会误报），唯一豁免点是组合根 `application/container.py`。实测 5 处 `infrastructure` 导入全部落在该文件内 —— 这是依赖倒置的正确代价，不是违规。

**② `domain` 层真正纯净。**
716 行领域代码，外部依赖仅 stdlib 与 pydantic。`order_state_machine.py` 把状态迁移规则表达成一张显式表（`ALLOWED_ORDER_TRANSITIONS`），非法迁移抛领域异常并带上「期望值 / 实际值」——领域规则与框架完全解耦。

**③ 端口上移是正确的架构决策。**
`application/ports/` 定义了仓储、文档加载、向量库三个端口，`infrastructure` 提供实现。更细的一点：`application/ports/repositories.py:88` 的 `collaboration_repositories()` 让「四个仓储必须同源」成为**结构性保证**，而不是调用方需要记住的约定——这是有经验的架构写法。

**④ 对抗协议直指真问题。**
`application/protocol/adversarial.py` 的注释写得很清楚：这个机制是为了「把自我确认彻底修掉」。关键在于 `build_counter_evidence_feedback()` **只回灌可复现证据（locator + 原文值），不回灌验证者的自然语言措辞**——避免生产者被措辞说服而放弃核对原文。这个细节说明设计者理解 LLM 协作的真实失效模式。

**⑤ 预算与熔断把「无限反思循环」从架构上排除。**
`application/protocol/budget.py`：订单级 token / 调用次数 / 墙钟三重预算 + 任务级重试计数，超限即 `ESCALATE` 转人工，**而不是静默通过**。V7 的 `test_budget_exhaustion_escalates_instead_of_passing_silently` 直接断言了这一点。

**⑥ 架构断言可证伪，这是最高分项。**
V5 反事实归因：逐个禁用 8 个管线 Agent，要求贡献矩阵**无全零行**，否则判定为「装饰性角色」。这条测试的写法本身就体现了批判性思维——它在主动寻找「多 Agent 是表面拆分」的反例。

### 3.2 架构层面的不足

**① 生产并发上限 = 1，DAG 的并行价值在部署形态下无法体现。**
`gunicorn.conf.py` 是 `workers = 1`，`flask_app.py:197` 是 `threaded=False`。V6 在**进程内**证明了扇出收益，但线上一次只处理一个订单。

**② `readiness()` 承担了三重职责，且挂在请求路径与健康检查上。**（详见 §4.1 P1-3）

---

## 4. 不足清单

> 按技能要求区分三类：**真实缺陷**（会导致错误行为）/ **验证缺口**（验证能力不足）/ **文档问题**（不影响运行但影响可信度）。

### 4.1 真实缺陷

| ID | 问题 | 证据 | 后果 |
|---|---|---|---|
| **D-1** | `FLASK_DEBUG` 代码默认 `True` | `config.py:75`：`default=True`；而 `.env.example` 写 `false` | 直接 `python app.py` 会把 Werkzeug 调试器暴露在 `0.0.0.0` → **任意代码执行**。容器路径被 `compose.yaml` 的 `FLASK_DEBUG: "false"` 掩盖 |
| **D-2** | `readiness()` 在请求路径上做全表扫描 + 写操作 | `flask_app.py:56-63` 的 `before_request` 对 `/api/upload`、`/api/upload_text` 调 `container.readiness()`；`container.py:70-71` 内 `repository.load_index()`（两次 `GROUP BY` 全表聚合）+ `fail_stale_processing_orders()`（`_load_orders()` 全表加载后逐条判断并可能 UPDATE） | 每次上传前 O(N) 全表读 + 潜在写；与单 worker 串行叠加放大排队 |
| **D-3** | 上传文件永不清理 | 全仓无 `os.remove` / `unlink`；`data/` 是持久化卷 | 磁盘无界增长，容器重建也不消失 |

> **D-2 的一处补充（原文档未指出）**：`compose.yaml` 的 `api` 健康检查每 **10 秒**请求一次 `/api/ready`，即 `readiness()` 的全表扫描与写操作**在系统空闲时也每 10 秒执行一次**。两处问题叠加，实际影响比单独看任一处更大。

### 4.2 验证缺口

| ID | 问题 | 证据 | 后果 |
|---|---|---|---|
| **V-1** | 设计文档 §4.3 承诺的**单 Agent vs 多 Agent 对比矩阵缺失** | `MULTI_AGENT_DESIGN.md:497` 有 §4.3 标题；`PROJECT_HISTORY.md` §9 自认「设计文档 §4.3 的对比矩阵缺失」 | **创新性主张缺少自己的证伪实验**。V1–V7 证明了「机制按设计运行」，但没证明「多 Agent 比单 Agent 更好」。这是答辩最容易被问倒的一处 |
| **V-2** | V1「Agent 之间不持有引用」无运行期强制 | 断言函数存在但未接线（`PROJECT_HISTORY.md` §9、P2-3） | 静态断言有效，运行期无兜底 |
| **V-3** | 并发与吞吐无基线标定 | `PROJECT_HISTORY.md` §9 | 无法回答「这套架构值多少性能」 |

### 4.3 文档问题

| ID | 问题 | 证据 |
|---|---|---|
| **DOC-1** | **README 的 API 表只列 6 个接口，实际有 10 个** | `README.md:57-64` 缺 `/api/ready`、`/api/orders/{id}/trace`、`/api/orders/{id}/tasks`、`/api/orders/{id}/review-suggestion`；实测 `grep -c '@app.route' interfaces/http/flask_app.py` = **10** |
| **DOC-2** | 自报指标落后于代码 | §2.1、§2.2 已列：分层行数、长函数数量均与实测不符 |
| **DOC-3** | 无 `LICENSE` | 影响合规与外部复用；素材授权核查做得很好（OFL-1.1 已随包分发），但项目自身反而没有许可证 |
| **DOC-4** | README 未链接设计文档 | `MULTI_AGENT_DESIGN.md`（32 KB）是本项目最有价值的文档，README 里没有任何入口 |

### 4.4 产品功能缺口

| ID | 问题 | 影响 |
|---|---|---|
| **G-1** | `/trace` 与 `/tasks` 已实现且返回丰富数据（含 `claims`、`messages`、`verdicts`、任务的 `lease_owner`/`attempts`），但前端从未调用 | **协作轨迹是设计文档 §2.3/§5 的核心交付物，用户却看不到**。这是答辩演示的最大损失——最能体现创新性的东西藏在了 API 里 |
| **G-2** | 无任何 DELETE 路由 | 失败订单在侧栏滞留至 `ORDER_AUTO_ARCHIVE_DAYS = 30` 天 |

---

## 5. 提升到「优秀上沿」的改进建议

> 按「收益 ÷ 成本」排序。前三项做完即可稳定进入 93+ 区间。

### 第 1 梯队 —— 立即（小时级，零风险）

**1. `FLASK_DEBUG` 默认改 `False`（D-1）**
一行改动，消除一个 RCE 面。答辩时若被问到「生产配置」，这是最容易被翻出来的问题。

**2. 补 `LICENSE`（DOC-3）**
项目对第三方素材的授权核查（98.css 仅作规范参考未引入、像素字体 OFL-1.1 已随包分发、图标为原创 SVG）做得相当严谨——**但自己反而没有许可证**，这个反差在评审时很扎眼。

**3. README 补全 API 表并链接设计文档（DOC-1、DOC-4）**
把 10 个路由补全，在开头加一行「架构设计见 `MULTI_AGENT_DESIGN.md`」。README 是评审者的第一入口，目前它没有反映项目的真实规模。

### 第 2 梯队 —— 短期（天级，高收益）

**4. 补上单 Agent vs 多 Agent 对比矩阵（V-1）—— 这是最高价值的一项**
设计文档 §4.3 已经承诺，评测基础设施（`evaluation/run_evaluation.py` + `replay_downstream.py` + run manifest）**已经具备**，缺的只是跑一次基线。

建议做法：用同一评测集，跑「线性单 Agent 流水线」与「多 Agent 协作」两条路径，对比四个口径——**请求成功 / 抽取正确 / 匹配正确 / 业务决策正确**（这正是项目自己定义的三大目标之三）。重点看**幻觉漏检率**与**需要人工干预的比例**。

**为什么这项最重要**：V1–V7 证明的是「机制按设计运行」，属于**内部一致性**；对比矩阵证明的是「这套机制比替代方案更好」，属于**外部有效性**。课程设计的创新性评分，最终落在后者。有了它，「我们做了多 Agent」就升级为「我们测出多 Agent 在这个任务上把幻觉漏检率从 X 降到 Y」。

**5. `readiness()` 瘦身，把写操作移出请求路径（D-2）**
拆成两件事：`/api/ready` 只做只读探测；`fail_stale_processing_orders()` 与 `recover_orphan_tasks()` 移到启动期（`container.initialize()` 里已有调用）或独立的后台定时任务。同时把健康检查从 10 秒一次的 `/api/ready` 换成轻量的 `/api/health`。

**6. 上传文件清理（D-3）**
订单处理完成后删除临时文件，或加定时清理 + 磁盘水位告警。

**7. 把协作轨迹接进前端（G-1）**
侧栏订单详情加一个「协作轨迹」页签，渲染 `/api/orders/{id}/trace` 返回的 `messages` 与 `verdicts`。**这是性价比最高的一项演示改进**——答辩时能让评委直接看到 10 个 Agent 谁在什么时候对谁说了什么、依据是什么。数据已经在 API 里，前端 `api.ts` 只需加两个方法。

### 第 3 梯队 —— 中期（周级，需设计）

**8. 并发模型升级（架构 §3.2-①、V-3）**
`preload_app = True`（消除多 worker 下的索引构建竞态）→ `workers = 4` → 重新标定 `timeout` → 补并发与吞吐基线。这样 V6 的并行收益才能在生产形态下兑现。

**9. 文档与代码对齐（DOC-2）**
把 `PROJECT_HISTORY.md` §4.1 / §4.2 的数字重跑一遍 `scripts/audit_layers.py` 后更新，并注明统计口径（阈值、是否含 `evaluation/`）。**自报指标与实测不符，比没有指标更危险**——评审者一旦抽查，会连带怀疑其他结论。

**10. 拆分 `create_app`（162 行）**
按蓝图拆路由；顺带解决 P2-8。这是全仓最长的业务函数，也是唯一一个「看一眼就知道该拆」的地方。

---

## 6. 如果我是答辩老师，我会问的三个问题

**Q1：「你怎么证明这 11 个 Agent 不是把线性流水线换了个名字？」**
→ 用 V1（零直接调用）+ V5（反事实归因无全零行）+ V6（扇出延迟摊薄）回答。**准备充分。**

**Q2：「多 Agent 比单 Agent 好在哪里？有数据吗？」**
→ 目前**答不上来**（V-1）。这是唯一的硬伤，也是为什么 §5 第 4 项优先级最高。

**Q3：「线上一次只能处理一个订单，那 DAG 的并行有什么意义？」**
→ 需要承认（架构 §3.2-①）：并行在进程内有效（V6 已证），但生产部署是单 worker 串行；`preload_app` 是解锁扩容的前置条件。

---

## 7. 复现命令

```bash
cd /Users/cmh/Documents/AGENT_project

# 测试基线
.venv/bin/python -m unittest discover -s tests -v      # 231 通过 / 8 跳过
cd frontend && npm test && cd ..                       # 10 通过

# 分层审计（跨层违规、domain 纯净度、长函数、债务标记）
python3 scripts/audit_layers.py

# 代码规模（排除依赖）
find domain application infrastructure interfaces -name "*.py" -exec wc -l {} +

# 密钥全历史扫描
git log --all -p | grep -nE "sk-[a-zA-Z0-9]{20,}"      # 0 命中
git log --all -- .env                                  # 空

# 路由清单（对比 README 的 API 表）
grep -c '@app.route' interfaces/http/flask_app.py      # 10

# 长函数（AST，>60 行）
python3 - <<'PY'
import ast, os
SKIP={".venv","node_modules","__pycache__",".git","frontend","datasets"}
for root,dirs,files in os.walk("."):
    dirs[:]=[d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith(".py"):
            p=os.path.join(root,f)
            try: tree=ast.parse(open(p,encoding="utf-8").read())
            except Exception: continue
            for n in ast.walk(tree):
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    L=(n.end_lineno or 0)-n.lineno+1
                    if L>60: print(f"{L:>4} 行  {p}:{n.lineno}  {n.name}")
PY
```

---

## 附：本次评审修正的既往结论

| 原说法 | 核实结果 |
|---|---|
| `PROJECT_HISTORY.md` §6 P1-3：「readiness 挂在**每请求**的 `before_request` 上」 | **成立**，但措辞需精确：钩子虽注册为全局，实际仅对 `/api/upload` 与 `/api/upload_text` 生效。**另发现**：`compose.yaml` 健康检查每 10 秒调 `/api/ready`，使该开销在空闲时也持续发生（原文档未指出） |
| §4.2「长函数 4 个」 | **不成立**。实测业务层 6 个、全仓 12 个（阈值/范围口径不同，文档未说明） |
| §4.1 分层行数 7,087 | **已过期**。实测 Python 合计 13,858 行（含 tests/evaluation/scripts 后） |
| §6 P0「曾进入本地 git 历史的 API 密钥」 | **已处置干净**。当前全历史扫描 0 命中，`.env` 从未提交 |
| §4.2「测试 231 通过 / 1 跳过」 | 实测 **231 通过 / 8 跳过**（本地缺 `TEST_DATABASE_URL` 与 `RUN_EMBEDDING_INTEGRATION`，CI 中已打开） |
