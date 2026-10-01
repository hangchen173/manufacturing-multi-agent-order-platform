# §3 Problem Formulation — 草稿

> 编制日期：2026-10-02 ｜ 目标篇幅：LNCS 单栏约 1.0 页
> 用途：把工程实现转为学术表述。**审稿人从这一章判断工作的严谨性。**
> 写法：英文正文（可直接进论文）+ 中文批注（写作意图，定稿时删除）。

---

## 3. Problem Formulation

### 3.1 Structured documents and locators

*[中文批注：先建立「文档—定位符—取值」这套最小语义，后面所有定义都建在它上面。
不引入任何与本文主张无关的概念。]*

We consider the task of extracting a schema-specified set of fields from a structured
document. Let a **structured document** be a pair $D = (\tau, Z)$, where $\tau \in
\{\textsc{Excel}, \textsc{Pdf}, \textsc{Image}\}$ is the document type and $Z$ is its
content representation: for $\textsc{Excel}$, $Z$ is a set of worksheets, each a grid of
cells; for $\textsc{Pdf}$, $Z$ is a set of pages with text and tables; for
$\textsc{Image}$, $Z$ is a rendered raster.

The central object of this paper is the **locator**, which turns a position in $D$ into a
machine-resolvable address. Let

$$
\ell \;\in\; \mathcal{L} \;=\; \underbrace{\mathcal{S}\times\mathbb{N}\times\mathbb{N}}_{\texttt{cell}}
\;\cup\; \underbrace{\mathbb{N}}_{\texttt{page}}
\;\cup\; \underbrace{\Sigma^{*}}_{\texttt{span}},
$$

where $\mathcal{S}$ is the set of worksheet names and $\Sigma^{*}$ is the set of finite
strings. We write $\texttt{cell}(s,r,c)$, $\texttt{page}(p)$ and $\texttt{span}(x)$ for the
three locator kinds.

A **resolution function** $\rho : \mathcal{L} \times \mathcal{D} \to \mathcal{V} \cup
\{\bot\}$ maps a locator and a document to the value stored at that address, or $\bot$ if
the address does not exist. Crucially, $\rho$ is **deterministic and publicly
computable**: any party holding $D$ and $\ell$ obtains the same $\rho(\ell, D)$. This is
the property that the rest of the paper exploits.

### 3.2 Evidence, claims, and grounding

*[中文批注：证据三元组是 C1 的形式化载体；「可复现」必须有严格定义，
否则整个主张会变成「我们说它可复现」。]*

**Definition 1 (Evidence).** An *evidence item* is a triple $e = (\kappa, \ell, v)$ where
$\kappa \in \mathcal{K}$ is an evidence kind, $\ell \in \mathcal{L}$ is a locator, and $v$
is the value asserted at that locator. We say $e$ is **reproducible** with respect to $D$
iff $\rho(\ell, D) = v$; that is, re-resolving the locator on the document yields exactly
the asserted value.

*[中文批注：`reproducible` 是代码里 `Evidence.reproducible` 字段的直译，
且 `challenge_evidence()` 恒置 `True` —— 注意这里有个语义落差，
见文末「与代码的对齐检查」。]*

**Definition 2 (Claim).** A *claim* is a tuple $c = (\sigma, v, \beta, \gamma)$ where
$\sigma$ is a subject (e.g. `item[3].quantity`), $v$ is the asserted value, $\beta$ is the
basis on which the claim was produced, and $\gamma \in [0,1]$ is an optional
self-reported confidence. A claim is **grounded** in $D$ iff it is accompanied by at least
one reproducible evidence item $e$ with $\rho(e.\ell, D) = v$.

**Definition 3 (Hallucination).** A claim $c = (\sigma, v)$ is **hallucinated** with
respect to $D$ iff no locator that is a valid address for $\sigma$ resolves to $v$:

$$
\mathrm{Hall}(c, D) \;\equiv\; \neg\,\exists \ell \in \mathcal{L}_{\sigma} \;:\; \rho(\ell, D) = v,
$$

where $\mathcal{L}_{\sigma} \subseteq \mathcal{L}$ is the set of locators that can
legitimately support subject $\sigma$.

*[中文批注：定义 3 刻意用「不存在任何能支持该值的地址」，而不是「模型说错了」。
这样「幻觉」就是**相对于文档可判定**的，不依赖人工判断，也不需要 ground truth 标注——
这是本文指标能被程序化计算的前提。]*

### 3.3 The verifiability gap

*[中文批注：这一节是全文的理论支点。它把「自然语言辩论 vs 证据锚定」从一个工程偏好
升级为一个**可判定的形式差异**。没有这一节，C1 会被审稿人当成实现细节。]*

Consider two multi-agent verification protocols that differ only in their **debate
medium**:

- $\Pi_{\mathrm{NL}}$: agents exchange challenges expressed in natural language;
- $\Pi_{\mathrm{EV}}$: agents exchange challenges expressed as evidence triples
  $e = (\kappa, \ell, v)$ with $\ell \in \mathcal{L}$.

**Proposition 1 (Verifiability gap).** Under $\Pi_{\mathrm{EV}}$, the acceptance decision
for a challenge against claim $c$ is decidable by a deterministic procedure:

$$
\mathrm{accept}(e, c, D) \;\iff\; \rho(e.\ell, D) = e.v \;\wedge\; \mathrm{Hall}(c, D).
$$

Under $\Pi_{\mathrm{NL}}$ there exists no such procedure, because a natural-language
challenge carries no address into $D$ and therefore admits no resolution function.

*Proof sketch.* For $\Pi_{\mathrm{EV}}$ the procedure is immediate from Definitions 1–3 and
requires only $D$ and $\ell$. For $\Pi_{\mathrm{NL}}$, suppose a decision procedure
$\mathcal{P}$ existed. Since $\mathcal{P}$ has access only to $(D, \text{challenge})$, two
challenges that are textually distinct but semantically equivalent with respect to $D$
would have to receive the same decision; yet natural language admits no canonical
semantics for this equivalence, so $\mathcal{P}$ cannot be well-defined. $\square$

*[中文批注：这个证明是「sketch」级别的，够会议论文用，但**必须在 Related Work 里
把「为什么不能用 NLI 模型来判定自然语言挑战」说清楚**——否则审稿人会反驳
「用蕴含模型不就能判定了」。预设答案：NLI 判定本身是概率性的、不可复现的，
且引入第二个可能幻觉的模型，等于把问题往后推了一层。这一条要写进 Discussion。]*

### 3.4 Budget-constrained extraction

*[中文批注：三重预算对应 `budget.py` 的三个字段，数值直接引用代码默认值。
把它形式化，是为了让 E5 的 Pareto 前沿有严格定义。]*

Processing an order consumes three resources. We define the **budget** as

$$
B = (T_{\max}, N_{\max}, W_{\max}),
$$

the maximum tokens, model calls, and wall-clock milliseconds per order (in our
implementation: $T_{\max} = 2\times10^{5}$, $N_{\max} = 12$, $W_{\max} = 3\times10^{5}$ ms).
A protocol **exhausts** its budget when any component is exceeded.

### 3.5 Problem statement

*[中文批注：双目标表述是关键——它让 E5 的 Pareto 图成为「问题的自然解」，
而不是「我们额外加的一个分析」。]*

Given a structured document $D$, a field schema $S = \{f_1,\dots,f_m\}$, and a budget
$B$, a verification protocol produces a grounded claim set $C$ and an **auto-approval
decision** $A \subseteq C$. We evaluate the protocol on two competing objectives:

$$
\min \; \mathrm{HER}(A) = \frac{|\{c \in A : \mathrm{Hall}(c, D)\}|}{|A|}
\qquad\text{and}\qquad
\max \; \mathrm{Auto}(A) = \frac{|A|}{|C|},
$$

subject to the budget $B$. **Hallucination escape rate** $\mathrm{HER}$ measures the
fraction of auto-approved values that have no supporting evidence in the source;
**automation rate** $\mathrm{Auto}$ measures how much human review is avoided. A protocol
that approves nothing achieves $\mathrm{HER}=0$ trivially; a protocol that approves
everything achieves $\mathrm{Auto}=1$ trivially. The task is therefore to trace a
favourable **accuracy–cost frontier** rather than to optimise either quantity alone.

**Scope of the claim.** We do not claim to eliminate hallucination. We claim that
changing the *medium* of multi-agent verification — from natural-language argument to
machine-checkable evidence — moves this frontier, and we quantify the move in §5–6.

---

## 写作检查清单（定稿前逐项打勾）

- [ ] 所有符号在符号表（Table 1）中出现且仅出现一次
- [ ] Definition 1 的 `reproducible` 与代码 `Evidence.reproducible` 语义一致（见下方对齐检查）
- [ ] Proposition 1 的证明补足到 LNCS 的严谨度，或明确标注为 proof sketch
- [ ] 预算默认值与 `application/protocol/budget.py` 完全一致
- [ ] HER 与 Auto 的定义与 §6 实验结果中实际计算的量完全一致
- [ ] 「不声称消除幻觉」这句边界声明保留（审稿人反感过度声称）

---

## ⚠️ 与代码的对齐检查（必须在定稿前解决）

形式化定义与当前实现之间存在**三处语义落差**。不是 bug，但**论文不能写得比代码更强**。

| # | 形式化定义 | 代码现状 | 处理 |
|---|---|---|---|
| 1 | Def 1：$e$ 可复现 $\iff \rho(\ell,D) = v$ | `Evidence.reproducible` 是**生产者自报的布尔字段**，`challenge_evidence()` 恒置 `True`，并**未真的去 resolve 校验** | 论文中应写成「$e$ 的可复现性由 $\rho$ 判定」，并在 §4 说明实现中以 `reproducible` 标记 + 验证者复核两步完成。**或者**补一个 `resolve` 校验（改动约 5 行），让代码与定义严格一致 |
| 2 | Def 2：claim 是四元组 $(\sigma,v,\beta,\gamma)$ | 代码 `Claim` 另有 `disputed` 字段 | 论文中加入第五个字段或说明 `disputed` 是运行期状态而非主张的一部分 |
| 3 | §3.3：$\Pi_{\mathrm{EV}}$ 的判定是确定性的 | `GroundingVerifier._cell_matches()` 对数值做 `Decimal` 归一、对文本做 `normalize_text`、对日期做 ISO 解析——**是确定性的** ✓ | **无需改动**，且这是一个加分点：应在 §4 明确指出「反证比对完全确定性，0 token」 |

> **建议**：优先解决第 1 项。它直接影响「machine-checkable」这个核心形容词的严谨性，
> 而且改动很小。**这是一项新增行动项。**
