# CCF 会议投稿候选清单（面向「多智能体 + 结构化文档抽取」项目）

> 检索日期：**2026-10-01**
> 筛选条件：**有明确截稿日期**、**审稿周期短于期刊**（会议 2–4 个月 vs 期刊 6–12 个月）、方向与本项目相关
> 项目关键词：多智能体 / LLM 幻觉 / 结构化文档抽取 / 信息抽取 / 对抗验证 / 制造业订单
> **重要**：带「预估」的日期来自第三方汇总或按往年规律推算，**投稿前必须到会议官网核实**。CCF 目录有 2019 版与 2022 版，各校采用版本不同。

---

## 0. 结论先行：三个推荐档位

> ⭐ **决策已定（2026-10-02 第二轮）：主投目标 = ICDAR 2027。**
> 执行口径以 `../paper/08_SUBMISSION_PLAN.md` 为准；改判理由见该文件 §0.1。
> 本表保留为**候选池对比**用途。

| 档位 | 会议 | 核心理由 |
|---|---|---|
| **首选（已定）** | **ICDAR 2027**（CCF-C，文档分析） | **领域最对口**（文档分析识别顶会，审稿人理解问题域）；**main track 明文征稿** *agents for document AI* / *multimodal LLMs for documents*；截稿 **2027-02-20**（**写作期落在初试后空窗**，不侵占 10–11 月冲刺期）；**17 页 LNCS**；录用率 **40.3% × 最高对口度**；会期 2027-08-18~22 **吉隆坡（免签、¥1.5–3k）** |
| **次选** | **PAKDD 2027**（CCF-C，数据挖掘） | 截稿 **2026-11-20**；**录用通知 2027-02-26**——正好卡在初试（2026-12-19/20）之后、复试（2027-03~04）之前；设 **LLM & Agentic AI 专轨**。**未选原因**：① 专轨附带「无 data science 焦点则 out of scope」排除条款；② 11-20 截稿使**工作量压在 10–11 月**（考研冲刺期）；③ 12 页 + 惠灵顿强制现场（差旅 ¥12–20k） |
| **备选（串行）** | **PAKDD 2028** / **ACM MM Asia 2027** / **ICDAR–IJDAR 期刊轨** | 均为 CCF-C 或同社区出口，用于 ICDAR 被拒（2027-05-15）之后的**串行**改投 |

**一个必须点出的发现**：在 AI / NLP / DM / 文档理解方向，**截稿落在 2026 年 11–12 月的 CCF-C 会议只有 PAKDD 2027（2026-11-20）**。
若此前设想的「12 月截稿」指的是 2026-12，那么 **PAKDD 2027 是唯一能同时满足「CCF-C + 早于初试投出」的选项**。
（12 月截稿的 CCF-C 会议其余集中在安全/系统方向：PETS、DIMVA、ASIACCS、ISPASS、IFIP SEC、GMP，与本项目无关。）

---

## 1. CCF-C 会议对比表（主表）

> 「周期」= 截稿 → 录用通知的天数。★ = 与本项目的方向相关度（5 星最对口）。
> 状态：✅ 官网/权威源已确认 ｜ ⚠️ 预估，需核实

| 会议 | 方向相关度 | 方向 | CCF | 截稿日期 | 录用通知 | 周期 | 会议日期 | 地点 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| **PAKDD 2027** | ★★★★ | 数据挖掘 / LLM & Agentic AI | **C** | **2026-11-20** | **2027-02-26** | **~3.2 月** | 2027-06-29 ~ 07-02 | 新西兰 惠灵顿 | ✅ |
| **ICDAR 2027** | ★★★★★ | 文档分析与识别 | **C** | **2027-02-20**（摘要 2027-01-31） | **2027-05-15** | **~2.8 月** | 2027-08-18 ~ 22 | 马来西亚 吉隆坡 | ✅ **三源交叉核实（2026-10-02）** |
| **ECIR 2027** | ★★★ | 信息检索 / 文档抽取 | **C** | **2026-10-05** | 约 2026-12 | ~2 月 | 2027-03-21 ~ 25 | 英国 南安普顿 | ✅ |
| **IJCNN 2027** | ★★★ | 神经网络 | **C** | **2027-01-31** | 约 2027-03/04 | ~2–3 月 | 2027 年（待核实） | 待核实 | ✅（截稿）/ ⚠️（通知） |
| **ICIP 2027** | ★★ | 图像处理 | **C** | 约 2027-01（**未公布**） | 约 2027-04 | ~3 月 | 2027-11-29 ~ 12-03 | 新加坡 | ⚠️ |
| **NLPCC 2027** | ★★★★ | 自然语言处理（中文） | **C** | 约 2027-05 | 约 2027-07 | ~2 月 | 约 2027-08 | 中国 | ⚠️（依 2026 届推算） |
| **PRCV 2027** | ★★★ | 模式识别与计算机视觉（国内） | **C** | 约 2027-04 | 约 2027-06 | ~1.7 月 | 约 2027-08 | 中国 | ⚠️（依 2026 届推算） |
| **BMVC 2027** | ★★ | 计算机视觉 | **C** | 约 2027-05 | 约 2027-07 | ~2 月 | 约 2027-09 | 英国 | ⚠️（依 2026 届推算） |
| **ACML 2027** | ★★ | 机器学习 | **C** | 约 2027-06 | 约 2027-08 | ~2 月 | 约 2027-11 | 亚洲 | ⚠️ |
| **ICONIP 2027** | ★★ | 神经网络与信息处理 | **C** | 约 2027-06 | 约 2027-08 | ~2 月 | 约 2027-11 | — | ⚠️ |
| **ACM MM Asia 2027** | ★★ | 多媒体 | **C** | 约 2027-07 | 约 2027-09 | ~2 月 | 约 2027-11 | — | ⚠️ |
| **PAKDD 2028** | ★★★★ | 数据挖掘 | **C** | 约 2027-11 | 约 2028-02 | ~3 月 | 2028 年 | — | ⚠️ |

**注**：`IROS 2027`（CCF-C，机器人，截稿约 2027-03）与本项目方向不符，不推荐。

### 1.1 ⭐ ICDAR 2027 完整日期链（2026-10-02 三源交叉核实）

> 来源：`mldeadlines.com/conference/icdar-2027`、`aiwhatson.com/event/icdar-2027-*`、
> `beri.net/events/icdar-2027`（三者均引 `icdar2027.org` 官方 CFP，**互相一致**）。
> ⚠️ **官网 `icdar2027.org` 有 Cloudflare 反爬，本次未能直接抓取**——投稿前必须人工打开
> `/call-for-papers` 与 `/important-dates` 复核一遍。

| 节点 | 日期 | 备注 |
|---|---|---|
| **摘要截稿** | **2027-01-31 23:59 AoE** | ⚠️ **不可省**，同样 **"no extension"** |
| **全文截稿** | **2027-02-20 23:59 AoE** | = 北京时间 2027-02-21 19:59，**严格无延期** |
| **审稿意见返还** | **2027-04-20** | — |
| **Rebuttal 截止** | **2027-04-27** | 窗口仅 **7 天** |
| **录用通知** | **2027-05-15** | ⚠️ **落在复试（2027-03~04）之后** |
| **Camera-ready** | **2027-06-05** | ⚠️ 单源，需复核 |
| **会期 / 地点** | **2027-08-18 ~ 22，吉隆坡** | 约 450 人；紧接 2027-09 入学前 |

| 其他关键项 | 值 |
|---|---|
| **页数** | **最多 17 页**，Springer LNCS 单栏 |
| **审稿** | **双盲 + rebuttal 环节** |
| **出版 / 检索** | Springer LNCS 论文集；EI / Scopus 收录 |
| **另有轨道** | **ICDAR–IJDAR journal track**（独立期刊轨，可作备投） |
| **录用率** | 历史平均约 **40.3%** |
| **现场要求** | **in-person**；每篇录用论文至少一名作者完成 **full main conference registration** |
| **签证** | ✅ **免签**——《中马互免持公务普通护照和普通护照人员签证的协定》**2025-07-17 生效**（条约级），单次停留 ≤30 日 |

**⭐ main track 明文征稿方向**（一等公民议题，非 workshop 边角）：
*agents for document AI* ｜ *multimodal LLMs for documents* ｜ *document reasoning models* ｜
*foundation models for document understanding* ｜ *information extraction and document retrieval* ｜
table and formula recognition ｜ document forensics and provenance ｜
private and secure document understanding ｜ historical / medical documents。

> **与本项目的关系**：本文「多智能体做结构化文档抽取」**正是 ICDAR 的正题**，
> 不需要像投 PAKDD 专轨那样额外包装「data science 焦点」。

---

## 2. CCF-B 补充选项（周期同样短，相关度高）

> 若认可 CCF-B，以下两个会议的方向相关度**高于多数 CCF-C**，且周期同样只有 2–3 个月。

| 会议 | 方向相关度 | 方向 | CCF | 截稿日期 | 录用通知 | 周期 | 会议日期 | 地点 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| **AAMAS 2027** | ★★★★★ | **自主智能体与多智能体系统** | **B** | **2026-10-08**（AoE） | 约 2027-01 | ~3 月 | 2027-05-03 ~ 07 | 越南 河内 | ✅ |
| **NAACL 2027** | ★★★★ | 自然语言处理 | **B** | **2026-10-12**（ARR 10 月轮） | 约 2027-01 | ~3 月 | 2027-06-01 ~ 05 | 美国 旧金山 | ✅ |

**AAMAS 值得特别注意**：它是**多智能体领域的主场会议**，本项目「11 个 Agent + 对抗协议 + 黑板」的架构正是其核心议题；
但它是 CCF-B，且更看重智能体机制的理论贡献，工程系统类工作需重新包装。

**已错过的相关会议（供对照）**：ICASSP 2027（B，2026-09-16）、WSDM 2027（B，2026-08-25）、EMNLP 2026（B，2026-06 中）、PRICAI 2026（C，2026-06-13）、ACCV 2026（C，2026-07-05）、BMVC 2026（C，2026-05-29）、ICPR 2026（C，2026-01-10）。

---

## 3. 非 CCF 但领域最对口：DAS（文档分析系统）

| 会议 | 相关度 | 等级 | 说明 |
|---|---|---|---|
| **DAS（IAPR International Workshop on Document Analysis Systems）** | ★★★★★ | **不在 CCF 目录**（ICORE B） | 文档分析领域老牌 workshop，与 ICDAR 同一学术社区。**DAS 2026 已在维也纳举办**，下一届（DAS 2028）截稿约在 2027 年底。若学校只认 CCF，此项不可用；若认可领域顶会，值得关注 |

---

## 4. 为什么会议周期比期刊短（对照说明）

| 维度 | 会议（本清单） | 期刊（`CCF_C_SUBMISSION_GAP.md` 所列） |
|---|---|---|
| 一审周期 | **2–4 个月** | 6–12 个月 |
| 是否需要「见刊」 | **否，录用即成果** | 录用后仍需 2–6 个月出版 |
| 录用后能否再扩刊 | 可以（需 30%+ 实质增量） | — |
| 与「投出即可」口径的匹配度 | **高**（录用函即终态） | 中（多为在审状态） |

> 依据：`docs/KYAN_RETEST_STRATEGY.md` §4、`docs/GRADUATION_TIMELINE.md` §3。

---

## 5. 按用途的推荐排序

| 场景 | 推荐 | 理由 |
|---|---|---|
| **追求领域对口 + 中稿概率最大** ⭐ | **ICDAR 2027**（2027-02-20） | **（现主投）** 文档分析顶会，`§9.3` 列为「**最易命中**」档；main track 明文征稿 agentic document AI；写作期落在初试后空窗，不侵占冲刺期 |
| 必须在初试（2026-12-19/20）前投出 | ~~PAKDD 2027~~（2026-11-20） | **已放弃**：截稿虽早于初试，但**工作量压在 10–11 月**；且专轨有排除条款、仅 12 页、惠灵顿强制现场（¥12–20k） |
| **认可 CCF-B、想要更强主题匹配** | **AAMAS 2027**（2026-10-08） | 多智能体主场；但需重写为机制类论文。**已来不及** |
| **想要中文场景认可度** | **NLPCC 2027**（约 2027-05） | 中文订单场景契合，CCF 主办 |
| **被拒后的串行备投** | **PAKDD 2028**（约 2027-11）、**ACM MM Asia 2027**（约 2027-07）、**ICDAR–IJDAR 期刊轨** | ⚠️ IJCNN / ICIP 2027 与 ICDAR 截稿重叠，**不可并行** |

**注意**：**一稿多投是禁区**。上述会议按「第一投 → 被拒后改投第二」的顺序使用，不可同时投。
**ICDAR（2027-02-20）与 IJCNN 2027（2027-01-31）、ICIP 2027（约 2027-01）截稿重叠**，
因此这三者**不能**互为并行备投，备投必须**串行**。

---

## 6. 信息来源

| # | 信息 | 来源 | 链接 | 检索日期 |
|---|---|---|---|---|
| 1 | PAKDD 2027 截稿 2026-11-20 / 通知 2027-02-26 / 会议 2027-06-29 / CCF-C / LLM & Agentic AI 专轨 | 会伴 myhuiban（会议信息聚合） | https://www.myhuiban.com/conference/157 | 2026-10-01 |
| 2 | PAKDD 2027 官方重要日期页 | PAKDD 2027 官网 | https://www.pakdd2027.org/pages/dates | 2026-10-01 |
| 3 | ICDAR 2027 全文截稿 2027-02-20、摘要 2027-01-31、会期 2027-08-18~22、吉隆坡 | AI Conference Deadlines（引 icdar2027.org） | https://mldeadlines.com/conference/icdar-2027/ | 2026-10-01 |
| 4 | ICDAR 2027 官网 CFP | ICDAR 2027 官网 | https://icdar2027.org/call-for-papers | 2026-10-01 |
| 5 | ECIR 2027 截稿 2026-10-05、会期 2027-03-21~25 | AI Conference Deadlines / ECIR 2027 官网 | https://mldeadlines.com/conference/ecir-2027/ ；https://www.ecir2027.co.uk/ | 2026-10-01 |
| 6 | IJCNN 2027 截稿 2027-01-31 | AI Conference Deadlines / IJCNN 2027 官网 | https://mldeadlines.com/conference/ijcnn-2027/ ；https://ijcnn.org/2027/authors/call-for-papers | 2026-10-01 |
| 7 | ICIP 2027 会期 2027-11-29~12-03、截稿未公布 | IEEE Signal Processing Society | https://signalprocessingsociety.org/event-names/icip | 2026-10-01 |
| 8 | AAMAS 2027 截稿 2026-10-08/09、会期 2027-05-03~07、河内 | AI Conference Deadlines / 华威大学 AAMAS 2027 主页 | https://mldeadlines.com/conference/aamas-2027/ ；https://warwick.ac.uk/fac/sci/dcs/aamas2027/ | 2026-10-01 |
| 9 | NAACL 2027 截稿 2026-10-12、会期 2027-06-01~05、旧金山、与 COLING 2027 共用 ARR 10 月轮 | NAACL 2027 官网 / ACL 官方公告 | https://2027.naacl.org/calls/main_conference_papers/ ；https://www.aclweb.org/portal/content/call-main-conference-papers-naacl-2027 | 2026-10-01 |
| 10 | NLPCC 2026 截稿 2026-06-20（用于推算 2027） | CCF NLPCC 官网 / PaperPilot | http://tcci.ccf.org.cn/conference/2026/ | 2026-10-01 |
| 11 | PRCV 2026 截稿 2026-04-30（延至 5-30）、通知 2026-06-20 | PRCV 官网 / 搜狐转载 | http://www.prcv.cn/ | 2026-10-01 |
| 12 | BMVC 2026 截稿 2026-05-29/30 | BMVC 2026 官网 / AI Conference Deadlines | https://bmvc2026.bmva.org/dates/ ；https://mldeadlines.com/conference/bmvc-2026/ | 2026-10-01 |
| 13 | 2027 年 CCF A/B/C 类 AI 会议截稿汇总（含 NLPCC/PRCV/BMVC/ACML/ICONIP/ACM MM Asia 预估） | AC 学术平台（第三方汇总） | http://www.academicenter.com/knowledge/details/2094240371683659776.html | 2026-10-01 |
| 14 | 12 月截稿 CCF-C 会议清单（安全/系统方向为主） | 知乎（第三方汇总） | https://zhuanlan.zhihu.com/p/1976949091578709540 | 2026-10-01 |
| 15 | CCFDDL 顶会截止同步（CVPR 2027 = 2026-11-17 等） | CCFDDL 社区镜像 | https://2-mo.github.io/ccfddl_deadlines.html | 2026-10-01 |
| 16 | DAS 2026 会议与论文集信息 | Springer / 会伴 | https://link.springer.com/conference/das | 2026-10-01 |

---

## 7. 使用提醒

1. **所有「预估」日期必须到官网核实**——第三方汇总经常滞后或出错，`KYAN_RETEST_STRATEGY.md` §11 已明确此点。
2. **时区**：多数会议截止为 **AoE（UTC-12）**，换算北京时间约为「次日 19:59」，比直觉多出近一天；但摘要注册通常比全文早 1–2 周，**不能省**。
3. **CCF 等级版本**：确认目标院校采用 2019 版还是 2022 版目录。
4. **学校是否认可会议**：部分院校只认期刊（`KYAN_RETEST_STRATEGY.md` §2），投稿前必须确认。
5. **与初试的关系**：`KYAN_RETEST_STRATEGY.md` §10 的红线不变——**冲刺期不碰论文**。
   ⚠️ **一处需要修正的旧认识**：「截稿早于初试」只保证**截止日在初试前**，
   **不保证工作量不在初试前**。PAKDD 的 2026-11-20 截稿实际把工作量压在 **10–11 月**（考研冲刺期），
   而旧版提醒只写了「不占用 12 月」，**漏掉了 11 月**。
   现主投 **ICDAR 2027（2027-02-20）** 使 **2026-10-01 ~ 12-20 整体归还初试**，
   论文工作集中在初试后的空窗期（2026-12-21 ~ 2027-02-16）。执行口径见 `../paper/08_SUBMISSION_PLAN.md` §5。

---

## 8. 与既有文档的关系

| 文档 | 关系 |
|---|---|
| `CCF_C_CONFERENCE_PREP_PLAN.md` | 本清单为其 §2 缺失项 **M1（会议名与截稿日）** 的候选答案来源 |
| `CCF_C_SUBMISSION_GAP.md` | 期刊路线；本清单为其**会议替代路线** |
| `KYAN_RETEST_STRATEGY.md` | §4 路径一（CCF-C 会议）的候选池扩充与日期更新 |
| `PUBLICATION_TIERS.md` | 提供 CCF 等级与中科院分区的坐标系 |

---

## 9. 录用难度评估（高 → 低）

### 9.1 评估口径

用三个维度判断，**不能只看录用率**：

1. **录用率** —— 最直接的量化指标，但受投稿池质量影响（投稿池强则同录用率下更难）。
2. **审稿严格程度** —— 是否有 rebuttal 环节、审稿轮次、PC 规模、是否双盲、是否两阶段（如 ARR）。
3. **领域竞争与对口度** —— 同领域头部实验室密度；以及**本项目与该会议的匹配度**。
   **对口度高会显著降低实际难度**——审稿人理解问题域，不会把「结构化文档抽取」误判为「没新意」。

> ⚠️ **关键提醒**：录用率与难度不等价。ICDAR 录用率约 40%，但它是文档分析领域的**顶会**；
> ECIR 录用率仅约 19%，却只是 CCF-C。**同为 C 类，实际门槛差异极大。**

### 9.2 难度排序表（含评估依据）

| 排名 | 会议 | CCF | 录用率 | 难度判定依据 |
|---|---|---|---|---|
| **1** | **NAACL 2027** | B | **22.6%**（2025 主会 719/3185） | ACL 家族，NLP 领域竞争最激烈；ARR 两阶段审稿，审稿意见质量要求高。**注**：Findings 通道另收 477 篇（15.0%），「有产出」的实际概率高于 22.6% |
| **2** | **AAMAS 2027** | B | **约 20–25%**（2024 约 20%） | 多智能体领域**顶会**；审稿严（2024 PC 达 595 人）；对**机制/理论贡献**的要求高于工程系统类工作。2025 收 250 full + 158 ext，2026 收 338 full + 193 ext |
| **3** | **ECIR 2027** | C | **18.9%**（近 5 年 23.8%） | **CCF-C 中录用率最低者之一**；欧洲信息检索旗舰。等级虽为 C，但审稿严格 + 竞争密度高 → **实际难度接近 CCF-B** |
| **4** | **PAKDD 2027** | C | **23%**（2024：175/720） | 亚太 DM 主会；投稿量增长而录用数基本不变（720 篇投稿量级），审稿严。**但设有 LLM & Agentic AI 专轨，对口度高** |
| **5** | **ACM MM Asia 2027** | C | **29%**（2025：59/204） | SIGMM 旗下多媒体会议；投稿基数小、年际波动大 |
| **6** | **NLPCC 2027** | C | **30.1%**（2025：152/505） | 历史波动极大（2019 年 17.3% → 2024 年 35.7% → 2025 年 30.1%）；中文场景对口，国内竞争集中 |
| **7** | **BMVC 2027** | C | **31.7%**（近 5 年平均 32.3%） | 英国 CV 主会；CV 领域整体竞争强，但比 CVPR/ICCV 低一档 |
| **8** | **PRCV 2027** | C | **37.9%**（2024：579/1526） | 国内 CV 会议；投稿量三年翻倍（2022 年 564 → 2024 年 1526），竞争在上升，但录用率仍宽松 |
| **9** | **ICDAR 2027** | C | **约 40.3%**（历史平均） | **文档分析领域顶会**——录用率不低，但「顶会」地位意味着质量标准是「**扎实且有明确增量**」；**对本项目最对口**，审稿人懂问题域 |
| **10** | **ICIP 2027** | C | **41.5%**（近 5 年平均） | IEEE SPS 旗舰之一，投稿量极大；录用率高，属「好中」档 |
| **11** | **ICONIP 2027** | C | **48.3%**（近 5 年平均；2021 曾 20.7%） | 亚太神经网络年会，年发文量大，**近年明显放宽** |
| **12** | **IJCNN 2027** | C | **54.6%**（2023 54.8% / 2024 52.0% / **2025 38.9%**） | 录用率最高的一档；**但无 rebuttal 环节**（一次定生死）；2025 年骤降至 38.9%，门槛在上升 |
| **13** | **ACML 2027** | C | **数据缺失** | 公开渠道未查到可靠的历年录用率；按同类 CCF-C ML 会议估约 30–35%，**需向组委会或近期投稿者核实** |
| — | **DAS**（IAPR） | 非 CCF | 数据缺失 | 文档分析领域 workshop，规模小、社区紧密；不在 CCF 目录，是否可用取决于院校认定 |

### 9.3 面向本项目的「实际难度」修正

**纯录用率排序 ≠ 对本项目的实际难度。** 叠加「方向对口度」后重排：

| 修正后档位 | 会议 | 说明 |
|---|---|---|
| **最易命中** | **ICDAR 2027** | 40% 录用率 × **最高对口度**。领域顶会 + 审稿人理解「结构化文档抽取」→ **性价比最高** |
| 较易 | ICIP / ICONIP / IJCNN / PRCV | 录用率 40–55%，但**方向对口度一般**，需把工作包装成 CV / NN 叙事，属「改叙事换概率」 |
| 中等 | PAKDD / NLPCC / ACM MM Asia / BMVC | 录用率 23–32%；其中 **PAKDD 有对口专轨**，是这一档里的最优解 |
| 较难 | ECIR / AAMAS / NAACL | 录用率均 <24%；且 ECIR、AAMAS 对**方法机制**的要求高于工程实现 |

**三个结论**：
1. 以「**中稿概率最大化**」为目标 → **ICDAR 2027**；
2. 以「**初试（2026-12-19/20）前必须投出**」为硬约束 → **PAKDD 2027**（11-20 截稿、录用率 23%、有对口专轨）；
3. 愿意冲 CCF-B → **AAMAS 2027**（主题最贴，但需把系统重写为机制类论文）。

---

## 10. 录用后的到会政策（必须现场 vs 可远程）

### 10.1 三条通用底线

1. **至少一名作者必须完成注册**，且通常是 **full / main conference registration**（不能只买 workshop 票）。
2. **论文必须被「实际报告」（actually presented）**，否则：
   - **IEEE 系会议**：明确保留将论文**从 IEEE Xplore 移除**的权利（IJCNN 2027 写入官方条款）；
   - **ACM 系会议**：未报告论文可能不进入 ACM Digital Library。
3. **「不报告」的后果是录用函仍在、但论文不算正式发表**——对「投出即可」的口径影响不大，
   但对「录用后用于毕业要求 / 评奖」影响很大。

### 10.2 各会议到会政策对照表

| 会议 | 会议形式 | 可否远程报告 | 依据 |
|---|---|---|---|
| **PAKDD 2027** | **纯线下** | ❌ **明确不可** | 官方 CFP：「held **exclusively in person**. All accepted presentations **must be delivered on-site**」 |
| **IJCNN 2027** | **纯线下** | ❌ **明确不可** | 官方：「At least one author per paper must be registered **AND attend the conference** to present their paper」；IJCNN 2025 官方说明「**is not a hybrid conference**」 |
| **ACM MM / MM Asia** | **纯线下** | ❌ **明确不可** | 官方：「ACM Multimedia 2026 **is not a hybrid conference**. We expect everyone presenting a paper to do it **on-site**」 |
| **ICIP 2027** | 现场为主 | ⚠️ **无远程通道** | 官方报告指引全为现场设备与流程；替代报告人须经**技术程序主席批准**，且需证明所有作者均无法出席 |
| **ECIR 2027** | 线下 | ⚠️ 未提供 | 官网：「ECIR 2027 will take place **in-person**」 |
| **ICDAR 2027** | 线下（**吉隆坡**） | ⚠️ 未提供 | 每篇录用论文需至少一名作者完成 **full main conference registration**；ICDAR 2026 为 in-person 活动。**✅ 中国公民免签**（中马互免签证协定 2025-07-17 生效，单次 ≤30 日）；机票约 ¥1.5–3k；会期 2027-08-18~22 紧接 9 月入学前 |
| **PRCV 2027** | 线下（国内） | ⚠️ 未提供 | 国内会议，历届均为线下；需查当届注册页 |
| **BMVC 2027** | 线下 | ⚠️ 未提供 | 官网未见远程政策说明 |
| **ACML 2027** | 待核实 | ⚠️ 未提供 | 官网未见明确说明 |
| **ICONIP 2027** | 待核实 | ⚠️ 未提供 | 官网未见明确说明；历届多为混合形式 |
| **DAS** | 线下 | ⚠️ 未提供 | — |
| **NAACL 2027** | **混合** | ✅ **可以** | ACL 家族有《Guidelines on Remote Conference Presentation》，作者可**按论文逐篇申请远程报告**；底线仍是至少一名作者注册 |
| **AAMAS 2027** | **混合** | ✅ **可以** | 官方设 Hybrid FAQ：主 track / extended abstract 等均可申请远程报告，需填表并提交预录视频 |

> ⚠️ 标注「未提供」= 官网未检索到明确条款，**不等于禁止**，但也**不能假定允许**。
> 投稿前务必查该会议官网的 *Presentation Instructions* / *Author Policies* / *Hybrid FAQ* 三处页面，或直接致信组委会。

### 10.3 对本项目的实际含义

- **选 PAKDD 2027 或 IJCNN 2027** → 录用后**必须有人到场**（惠灵顿 / 待定）。
  对本科生而言，**签证 + 差旅成本 + 时间**（会议多在 2027 年 6–7 月，可能与复试或毕业冲突）必须提前计入。
- **选 NAACL 2027 或 AAMAS 2027** → **支持远程报告**，成本可控，适合「录用后仍需兼顾学业」的情形。
- **以「低成本拿到录用函」为目标** → 优先选**明确支持远程**的会议（NAACL / AAMAS）。

---

## 11. 信息来源（录用率与到会政策）

| # | 信息 | 来源 | 链接 | 检索日期 |
|---|---|---|---|---|
| 17 | NAACL 2025 主会 719/3185 = 22.57%；Findings 477/3185 = 14.98% | OpenAccept | https://openaccept.org/zh-CN/c/ai/naacl/2025/ | 2026-10-01 |
| 18 | NLPCC 历年录用率（2025 30.10% / 2024 35.70% / 2023 29.92% / 2022 25.38% / 2021 23.32% / 2020 21.88% / 2019 17.28% / 2018 17.86% / 2017 18.65%） | OpenAccept | https://openaccept.org/zh-CN/c/ai/nlpcc/ | 2026-10-01 |
| 19 | PAKDD 2024：720 投稿 / 175 录用 = 23%；PC 595 人 | The Data Blog（Philippe Fournier-Viger） | https://data-mining.philippe-fournier-viger.com/a-brief-report-about-pakdd-2024/ | 2026-10-01 |
| 20 | ECIR 平均录用率 18.9%（近 5 年 23.8%） | OpenResearch | https://www.openresearch.org/wiki/ECIR | 2026-10-01 |
| 21 | ICDAR 平均录用率 40.3% | OpenResearch | https://www.openresearch.org/wiki/ICDAR | 2026-10-01 |
| 22 | BMVC 平均录用率 32.3%（近 5 年 31.7%）；BMVC 官方统计页 | OpenResearch / BMVA | https://www.openresearch.org/wiki/BMVC ；https://www.bmva.org/bmvc/statistics/ | 2026-10-01 |
| 23 | ICIP 平均录用率 41.5% | OpenResearch | https://www.openresearch.org/wiki/ICIP | 2026-10-01 |
| 24 | IJCNN 录用率 2023 54.8% / 2024 52.0% / 2025 38.9%；平均 54.6% | AI Deadlines / OpenResearch | http://aideadlines.org/conference/?id=ijcnn2025 ；https://www.openresearch.org/wiki/IJCNN | 2026-10-01 |
| 25 | ICONIP 平均录用率 48.3%（2021 为 20.68%） | OpenResearch / 知乎转载 | https://www.openresearch.org/wiki/ICONIP | 2026-10-01 |
| 26 | PRCV 2024 1526 投稿 / 579 录用 = 37.9%；2023 37.5%；2022 41.3% | CSDN（会议之眼） | https://blog.csdn.net/ConferenceEye/article/details/148288836 | 2026-10-01 |
| 27 | ACM MM Asia 2025：59/204 = 29% | ACM Digital Library | https://dl.acm.org/doi/proceedings/10.1145/3743093 | 2026-10-01 |
| 28 | AAMAS 2025 收 250 full + 158 ext；AAMAS 2026 收 338 full + 193 ext | IFAAMAS 官方欢迎辞 / ACM DL | https://www.ifaamas.org/Proceedings/aamas2025/pdfs/welcome.pdf ；https://dl.acm.org/action/showFmPdf?doi=10.5555%2F3776572 | 2026-10-01 |
| 29 | IJCNN 2027 到会要求（至少一名作者注册并到场；未报告可从 Xplore 移除）；IJCNN 2025 非混合会议 | IJCNN 2027 官网 / 博客园转述官方回复 | https://ijcnn.org/2027/presentation-instructions ；https://www.cnblogs.com/xyz/p/18704873 | 2026-10-01 |
| 30 | PAKDD 2027 纯线下、必须现场报告 | 会伴 myhuiban（引官方 CFP） | https://www.myhuiban.com/conference/157 | 2026-10-01 |
| 31 | ACM Multimedia 2026 非混合、必须现场报告 | ACM MM 2026 官网 | https://2026.acmmm.org/site/paper-presenters-guidelines.html | 2026-10-01 |
| 32 | ICIP 2026 现场报告要求与替代报告人规则 | ICIP 2026 官网 | https://2026.ieeeicip.org/presentation-instructions/ | 2026-10-01 |
| 33 | ICDAR 2026 注册要求（每篇至少一名作者 full 注册）与报告指引 | ICDAR 2026 官网 | https://icdar2026.org/index.php/registration/ ；https://icdar2026.org/index.php/instruction-for-presenters/ | 2026-10-01 |
| 34 | ECIR 2027 为线下（in-person）会议 | ECIR 2027 官网 | https://www.ecir2027.co.uk/ | 2026-10-01 |
| 35 | AAMAS 2026 混合形式与远程报告申请流程 | AAMAS 2026 官方 Hybrid FAQ | https://cyprusconferences.org/aamas2026/hybrid-faq/ | 2026-10-01 |
| 36 | ACL 家族远程报告指引（可按论文逐篇申请） | ACL Conference Handbook | https://acl-org.github.io/conference-handbook/remote/ | 2026-10-01 |
| 37 | **ICDAR 2027 完整日期链**：摘要 2027-01-31 / 全文 2027-02-20 23:59 AoE / 审稿意见 2027-04-20 / rebuttal 2027-04-27 / **通知 2027-05-15** / camera-ready 2027-06-05；**最多 17 页 Springer LNCS；双盲 + rebuttal** | AI Conference Deadlines（引 icdar2027.org） | https://mldeadlines.com/conference/icdar-2027/ | **2026-10-02** |
| 38 | ICDAR 2027「up to 17 pages in Springer LNCS format and reviewed double-blind with a rebuttal phase」 | AI WhatsOn | https://aiwhatson.com/event/icdar-2027-document-analysis-kuala-lumpur | **2026-10-02** |
| 39 | ICDAR 2027 main track 明文征稿 *foundation models for document understanding* / *multimodal LLMs for documents and agents for document AI* / *document reasoning models*；约 450 人参会；in-person | THE D\*AI\*LY BRIEF（引 icdar2027.org CFP） | https://www.beri.net/events/icdar-2027 | **2026-10-02** |
| 40 | **中马互免签证协定**（《中华人民共和国政府和马来西亚政府关于互免持公务普通护照和普通护照人员签证的协定》）**2025-07-17 生效**；单次停留 ≤30 日、180 日内累计 ≤90 日 | 中国驻马来西亚大使馆 / 中国领事服务网 | https://my.china-embassy.gov.cn/fwzc/lsyw/lszj/fhqz2024/cjwdvisa/202508/t20250801_11681383.htm ；https://cs.mfa.gov.cn/zggmcg/ljmdd/yz_645708/mlxy_647012/rjjl_647022/ | **2026-10-02** |

> **时效性提醒**：录用率逐年变动，到会政策**每届都可能调整**（疫情后尤其如此）。
> 上述数据用于**排序与决策参考**，**投稿与注册前必须回到会议官网核对当届条款**。
