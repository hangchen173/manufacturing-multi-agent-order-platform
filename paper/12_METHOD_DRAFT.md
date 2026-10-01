# §4 Method — 英文草稿

> 编制日期：2026-10-02 ｜ 目标篇幅：LNCS 单栏约 3.0 页
> 写法：英文正文（可直接进论文）+ 中文批注（写作意图，定稿时删除）
> 素材：`MULTI_AGENT_DESIGN.md` §2.3–2.5 + 三处已核实代码
> （`application/protocol/adversarial.py`、`application/blackboard/slices.py`、`application/protocol/budget.py`）

---

## 4. Method

### 4.1 System overview

*[中文批注：先把架构讲清楚，但**不要在总览里讲 11 个 agent 的细节**——
审稿人关心的是机制，不是角色清单。角色表放附录或压缩成一段。]*

VEAP is a multi-agent verification protocol for structured document extraction. It
instantiates a single design principle: **agents do not exchange opinions, they exchange
checkable evidence.** The system comprises eleven agents — ten domain agents and one
orchestrating supervisor — communicating exclusively through a shared blackboard via
structured messages.

Two properties of the design are worth stating up front, because they distinguish VEAP
from prior multi-agent debate approaches:

1. **Only two of the eleven agents invoke an LLM.** The extractor produces the initial
   claim set, and a review assistant generates a natural-language summary for the human
   operator. The remaining nine agents — including the verifier that carries the
   adversarial load — are fully deterministic and consume **zero tokens**. Verification is
   therefore not merely cheaper than a natural-language debate; it is a different
   computational category.
2. **Agents never call each other.** Each agent is an approximate pure function
   $\textit{handle}: \text{slice} \to \text{messages}$. Coordination is mediated entirely
   by the blackboard and a task dependency graph, which is what makes the protocol
   replayable and independently testable.

The blackboard maintains three layers: **control state** (routing, budgets, risk flags),
**claims and evidence** (append-only), and **order facts** (the committed values). Agents
communicate through a fixed repertoire of seven speech acts —
$\textsc{Request}, \textsc{Inform}, \textsc{Propose}, \textsc{Challenge}, \textsc{Verdict},
\textsc{Refuse}, \textsc{Escalate}$ — and each role is authorised to emit only a subset of
them. In particular, the verifier may not emit $\textsc{Propose}$: **the agent that finds a
problem can never be the agent that fixes it.**

### 4.2 Evidence-anchored adversarial verification

*[中文批注：这是 C1，全文的方法核心。Algorithm 1 必须与代码逐行对应——
审稿人若去读开源代码，算法与实现不一致是致命的。]*

The protocol proceeds as $\textsc{Propose} \to \textsc{Challenge} \to \textsc{Verdict}$
(Algorithm 1). The extractor emits, for each item row $i$ and field $f$, a claim together
with a locator $\ell_{i,f}$ obtained from the document layout (§3.1). The
grounding verifier then **re-resolves every locator against the source document** and
compares the resolved value with the claimed value.

The comparison is fully deterministic and uses no model: numeric fields are normalised
through exact decimal arithmetic, dates through ISO parsing, and text through whitespace
and case normalisation. **A challenge is therefore not an opinion — it is the output of a
comparison operator, and it carries the counter-evidence that produced it.**

When the resolved value disagrees with the claim, the verifier emits a
$\textsc{Challenge}$ carrying a reproducible evidence item

$$
e = (\kappa, \ell, v^\star), \qquad v^\star = \rho(\ell, D),
$$

where $v^\star$ is the value actually present at the locator. The challenge **must**
carry such evidence: a challenge without a resolvable locator is not admissible.

The supervisor then constructs the feedback returned to the extractor. Here lies the
design decision that distinguishes VEAP from natural-language debate: **the feedback
contains only the locator and the resolved value, and discards the verifier's
phrasing.** Formally, for a set of challenges $P$, the feedback is

$$
\mathrm{Anchor}(P) \;=\; \bigl\{\, \text{``position } \ell \text{ holds } v^\star\text{''} \;\bigm|\; (\kappa,\ell,v^\star) \in P \,\bigr\},
$$

with no natural-language rationale included. The rationale for discarding it is
behavioural, not stylistic: a fluent argument can persuade the producer to *accept a
correction without re-reading the source*, which replaces one hallucination with another.
A locator cannot persuade; it can only be checked. The producer is thereby forced to
re-resolve the same address and confront the same value.

*[中文批注：上面这段是 C1 的机制论证，也是 C2 实验要检验的假设。
**注意措辞**：这里说的是「为什么我们认为该这样设计」，不是「已经证明」——
证明在 §6 的对照实验里。不要写成既成事实。]*

After at most $A = 2$ extraction attempts, any claim that remains challenged is marked
$\textit{disputed}$ and is excluded from auto-approval (§4.4). Claims that survive with a
matching locator are grounded in the sense of Definition 2.

**Algorithm 1** Evidence-Anchored Adversarial Verification (VEAP)

```
Input : document D, schema S, budget B, max attempts A
Output: claim set C, auto-approval set A_out

 1  feedback ← ⊥
 2  for attempt = 1 to A do
 3      C ← ∅
 4      for each region r ∈ Route(D) do                  ▷ deterministic routing
 5          c ← Extract(D|_r, S, feedback)               ▷ LLM, 1 call
 6          C ← C ∪ {(c, ℓ(c))}                          ▷ attach locators from layout
 7      P ← ∅
 8      for each claim c ∈ C do
 9          v* ← ρ(c.ℓ, D)                               ▷ deterministic, 0 tokens
10          if v* ≠ c.v then
11              P ← P ∪ { (kind, c.ℓ, v*) }              ▷ counter-evidence, no rationale
12      if P = ∅ then break
13      feedback ← Anchor(P)                             ▷ locators + values only
14  disputed ← { c ∈ C : c challenged in final attempt }
15  return C, { c ∈ C \ disputed : Grounded(c) }
```

*[中文批注：Algorithm 1 与 `Supervisor._extract_and_verify()` 逐行对应：
第 2 行的 `A` = `MAX_EXTRACTION_ATTEMPTS`，第 9 行的 $\rho$ = `_cell_matches`，
第 13 行的 `Anchor` = `build_counter_evidence_feedback(mode="locator")`。
**定稿前必须再核一遍**，因为代码可能已改。]*

### 4.3 Structural context isolation

*[中文批注：C2。关键是把「结构性」讲成**可验证的工程属性**，而不是「我们在提示词里
要求它别偷看」。这是与 ACL 2026 匿名化工作的差异点。]*

For the adversarial protocol to be more than self-confirmation, the verifier must not have
access to the producer's internal state. VEAP enforces this **structurally** rather than
by prompt instruction.

Every agent reads the blackboard through a role-scoped **context slice**, constructed by a
single entry point that applies both a whitelist of readable keys and a blacklist of
forbidden keys. The blacklist is decisive: a forbidden key **never enters the slice at
all** — it is not passed and then ignored, it is never constructed. Concretely, the
verifier's slice is built from the document, the disputed claim's subject and value, and
the claim list — and the producer's rationale and self-reported confidence are explicitly
stripped:

```
FORBIDDEN_KEYS[GROUNDING_VERIFIER] = { extractor.rationale, extractor.confidence }
```

This matters because self-reported confidence is known to be poorly calibrated: a model is
frequently as confident about its hallucinations as about its correct extractions. Had the
verifier been able to read $\gamma$ (Definition 2), it could defer to the producer's
confidence instead of consulting the document, and the protocol would collapse back into
self-confirmation. Isolation is therefore not a fairness measure — it is what makes the
verification signal *external*.

We verify this property by an automated assertion that inspects the constructed slice for
forbidden keys, rather than by trusting the prompt.

**A stronger property holds for the grounding verifier.** Its decision is a pure function
of the document, the claimed value and the locator:

$$
\mathrm{verify} \;:\; (D,\; \ell,\; v) \;\longrightarrow\; \{\textsc{Inform}, \textsc{Challenge}\},
$$

with **no code path that could read the producer's state**. Isolation is therefore not a
mitigation that reduces the verifier's susceptibility to persuasion; it removes the
susceptibility by construction. We state this as a structural guarantee rather than
reporting an ablation, because removing the isolation layer from this component is an
identity transformation — a fact we verify by an executable assertion rather than by
experiment.

*[中文批注：这一段是 2026-10-02 的重要改写。原稿写的是「§6.4 的消融去掉隔离来测量其贡献」，
但实测证明：验证者模块内 `confidence` / `rationale` **出现 0 次**，置信度从 0.0 拉到 1.0
判定逐字节不变——**该消融是恒等变换**。见 `tests/test_ablation_invariance.py`。

改成「纯函数性」是**更强的声明**：消融只能证明「有影响」，纯函数性证明「不可能有影响」。
且这样写与代码严格一致，审稿人若去读开源代码不会发现落差。

同时要**如实说明**：隔离对**基于 LLM 的验证者**才会产生行为差异；
本实现的验证者是确定性的，所以隔离在这里是「设计不变量」而非「性能机制」。
这种诚实反而是加分项。]*

### 4.4 Budget-constrained escalation

*[中文批注：C3。核心是「升级而非降级」这条设计原则，以及它**可被证伪**——
E4 的第三项消融就是去掉它，看指标怎么变。]*

An unbounded verification loop is a cost hazard and, in a business setting, a correctness
hazard. VEAP therefore imposes a per-order budget

$$
B = (T_{\max}, N_{\max}, W_{\max}),
$$

tracked by the supervisor across all tasks and checked before every model invocation. In
our implementation $T_{\max} = 200{,}000$ tokens, $N_{\max} = 12$ calls and $W_{\max} =
300{,}000$ ms.

The design principle is stated as a refusal to trade correctness for availability:

> **When the budget is exhausted, the system escalates to a human. It does not lower its
> standard, and it does not silently approve.**

Formally, budget exhaustion raises an escalation event that routes the affected fields to
human review, marking them $\textit{disputed}$. They never enter the auto-approval set.
This is what makes the accuracy–cost frontier of §6.5 meaningful: a protocol that
responds to budget pressure by approving more aggressively would appear cheaper while
silently degrading — precisely the failure mode our evaluation is designed to expose.

We characterise this mechanism by a **stress test** rather than an ablation. On our
datasets the default budget is never reached — processing an order consumes three model
calls against a limit of twelve — so removing the breaker would be an identity
transformation and an ablation would carry no information. Instead we tighten
$N_{\max}$ to 1 and 2 and verify that the escalation path is actually taken, reporting
the resulting behaviour. This tests whether the safety net *works*, not whether it changes
performance.

*[中文批注：这一段同样来自 2026-10-02 的实测：240 + 100 个历史样本 **0 次**预算升级；
实测每单 3 次调用 vs 上限 12。**不要写成消融**——审稿人会发现两臂完全相同，
反而怀疑你连自己系统的行为都没测清楚。写成压力测试既诚实又有信息量。]*

### 4.5 Complexity

*[中文批注：这一节是**相对优势的量化表达**，不要省略。它把「我们的验证不花 token」
从一句好话变成一条复杂度陈述。]*

Let $R$ be the number of document regions, $n$ the number of item rows, $m$ the number of
fields per row, and $A$ the maximum number of extraction attempts.

| Resource | VEAP | Natural-language debate with $k$ agents, $t$ rounds |
|---|---|---|
| LLM calls | $O(A \cdot R)$ | $O(k \cdot t)$ |
| Tokens | $O(A \cdot R \cdot \lvert D \rvert)$ | $O(k \cdot t \cdot \lvert D \rvert)$ |
| Deterministic comparisons | $O(A \cdot n \cdot m)$ | — |
| Wall clock | dominated by LLM latency | dominated by $k \cdot t$ LLM calls |

The essential asymmetry is in the second column's dependence on the **claim count**: in
VEAP, verification cost grows with $n \cdot m$ in *deterministic comparisons*, which are
free of tokens and latency, while the number of LLM calls is independent of how many
fields are disputed. A natural-language debate, by contrast, must spend model calls to
argue about each disputed field. **Increasing the number of verified fields therefore
costs VEAP nothing in tokens, but costs a debate linearly.** This is the structural reason
we expect VEAP to dominate on the accuracy–cost frontier, and it is what §6.5 measures.

---

## 写作检查清单（定稿前逐项打勾）

- [ ] Algorithm 1 与 `Supervisor._extract_and_verify()` 逐行核对（代码可能已改）
- [ ] §4.1 的「十一个 agent / 仅两个调用 LLM」与 `domain/agent_roles.AgentRole` 一致
- [ ] §4.2 的确定性比对描述与 `GroundingVerifier._cell_matches()` 一致
- [ ] §4.3 的 `FORBIDDEN_KEYS` 代码块与 `domain/agent_roles.py` 一致
- [ ] §4.4 的三个预算默认值与 `application/protocol/budget.py` 一致
- [ ] §4.5 的复杂度表与 §6.5 的实测数字对得上
- [ ] 全章**不出现**「黑板」「言后行为」等中文工程词（见 `04_TERMINOLOGY.md`）

---

## ⚠️ 需要补强的一处论证

§4.2 末尾关于「locator 不会说服、只会被核查」的论证目前是**机制性断言**，缺少直接证据。

**补强方式**：§6 的 E4 第一项消融正是它的对照检验。写作时应**前后呼应**：

> §4.2 提出假设 → §6.4 给出「换成自然语言反证后，弃权率显著上升 / 修正率显著下降」的数据 → §7 解释机制

**若 E4 结果显示两臂无差异**，则 §4.2 这段论证必须**删除或改写为边界声明**，
不能保留一个没有证据支撑的因果解释。这是审稿人最容易抓住的地方。
