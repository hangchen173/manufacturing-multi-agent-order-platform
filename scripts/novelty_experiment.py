"""新颖性判决实验（门禁 G0）。

**判决问题**：把对抗协议的反证媒介从「自然语言论证」换成「机器可核查的定位符」，
是否真的提升了幻觉修正率？

**设计**：两臂单变量对照。同一个注入错误、同一条 CHALLENGE、同一个提示词骨架、
同一个模型与温度，唯一差异是回灌给 Extractor 的 feedback 形态：

```
Arm A  natural_language   「第 3 项的 quantity 与原文不一致，请重新核对原订单。」
Arm B  locator            「…原单元格为 100，抽取为 98765。
                              · 反证位置 工作表 采购订单 第 17 行第 5 列：原文为 100」
```

规格与判定规则见 `paper/06_NOVELTY_EXPERIMENT.md`。

用法：

```
# 只造样本、不调模型（零成本，可离线）
python scripts/novelty_experiment.py --dry-run

# 小规模试跑，先确认 feedback 真的进了 prompt
python scripts/novelty_experiment.py --limit 5 --repeats 1

# 难度阶梯预实验：两档各跑一遍（两档的样本身份完全一致，只差注入值）
python scripts/novelty_experiment.py --limit 10 --repeats 1 --difficulty gross
python scripts/novelty_experiment.py --limit 10 --repeats 1 --difficulty subtle

# 正式跑 50 × 2 臂 × 3 重复 = 300 次调用（两档各一遍）
python scripts/novelty_experiment.py --samples 50 --repeats 3 --difficulty subtle
```

**⚠️ 2026-10-02 实测**：``--difficulty gross`` 下两臂同时饱和到 100%（天花板效应），
判决实验无法区分两臂。正式跑请用 ``subtle``，并以 ``gross`` 作为难度对照。

**红线**：实验必须直连模型服务商官方端点。中转站（API relay）会静默替换模型，
使「实际用了哪个模型」不可证明，整篇论文的可复现性主张随之失效。
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application.agents.extractor import Extractor  # noqa: E402
from application.agents.grounding_verifier import NUMERIC_FIELDS, GroundingVerifier  # noqa: E402
from application.agents.source_map import find_item_locators, normalize_text  # noqa: E402
from application.protocol import build_counter_evidence_feedback, challenge_evidence  # noqa: E402
from config import Config  # noqa: E402
from domain.messages import AgentMessage, Performative  # noqa: E402
from infrastructure.document_processing import DocumentLoader  # noqa: E402

ORDERS_DIR = PROJECT_ROOT / "datasets/generated_complex/orders/test"
ANNOTATIONS_DIR = PROJECT_ROOT / "datasets/generated_complex/annotations/test"
RESULTS_ROOT = PROJECT_ROOT / "evaluation/results"

#: 两臂：(臂名, 反馈模式)。臂名进产物，模式进 build_counter_evidence_feedback。
ARMS: Tuple[Tuple[str, str], ...] = (
    ("A_natural_language", "natural_language"),
    ("B_locator", "locator"),
)

#: 可注入的字段。自建订单集的明细表只有「物料名 / 规格型号 / 数量 / 单位 / 单价」
#: 五列，没有交期列，因此交期不进轮转——否则会整类落空、样本分布失衡。
FIELD_ROTATION = ("quantity", "unit_price", "material_name", "specification")

#: 注入难度两档（D19）。
#:
#: - ``gross``  —— 错误值在原表中**不存在**（数值 ×10 量级错位），一眼可辨，
#:   不需要定位符就能知道「哪个值错了」。
#: - ``subtle`` —— 错误值在原表中**真实存在**（同列另一行的取值，且优先挑与 gold
#:   最相似的候选）。值本身完全合法，只有回到正确的那一格才能发现——精确对应制造业
#:   订单抽取最典型的失效模式「行错位 / 张冠李戴」，也是 locator 相对自然语言措辞
#:   应当产生增量的条件。
#:
#: ⚠️ 2026-10-02 试跑发现：``gross`` 档下两臂同时饱和到 100%（天花板效应），
#: 判决实验无法区分两臂。正式跑前必须先确认 ``subtle`` 档能拉开差距。
DIFFICULTIES = ("gross", "subtle")

OUTCOME_CORRECTED = "corrected"
OUTCOME_ABSTAINED = "abstained"
OUTCOME_UNCHANGED = "unchanged"
OUTCOME_OTHER_WRONG = "other_wrong"
OUTCOME_ERROR = "error"


# --------------------------------------------------------------------- 数值/日期工具

def _to_decimal(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value).split("T")[0])
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------- 样本构造

def _pick_target(
    locators: List[Dict[str, Any]], field: str, rng: random.Random
) -> Optional[Tuple[int, Dict[str, Any], int, Any]]:
    """挑一个「该字段有源单元格、且值非空」的明细行。"""
    candidates = [
        (index, locator, locator["columns"][field], locator["values"].get(field))
        for index, locator in enumerate(locators)
        if locator["columns"].get(field) is not None
        and locator["values"].get(field) not in (None, "")
    ]
    if not candidates:
        return None
    return rng.choice(candidates)


def _alternatives_in_column(
    field: str, gold: Any, locators: List[Dict[str, Any]]
) -> List[Any]:
    """同列中其他行的真实取值（按规范化文本去重，排除与 gold 等价的那些）。"""
    gold_key = normalize_text(str(gold))
    unique: Dict[str, Any] = {}
    for locator in locators:
        value = locator["values"].get(field)
        if value in (None, ""):
            continue
        key = normalize_text(str(value))
        if key == gold_key or key in unique:
            continue
        unique[key] = value
    return list(unique.values())


def _common_prefix_length(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def _most_similar(gold: Any, alternatives: List[Any]) -> Any:
    """挑与 gold 最像的候选——越像越难辨，最大化混淆度。

    例：gold 为 ``100``、同列候选为 ``{50, 120, 1000}`` 时取 ``1000``
    （只差一位数），而不是随机撞上 ``50``（一眼可辨）。
    """
    gold_text = normalize_text(str(gold))
    return max(
        alternatives,
        key=lambda value: _common_prefix_length(gold_text, normalize_text(str(value))),
    )


def _injection_rng(order_stem: str, item_index: int, field: str) -> random.Random:
    """注入专用随机源，由样本身份派生。

    **为什么必须独立**：若注入与「选目标行」共用一条随机流，``gross`` 分支多消耗一次
    ``rng.choice`` 就会让后续订单的目标行整体漂移——两档就不是同一批样本，无法对照。
    派生式随机源使**目标行选择与难度完全无关**，两档唯一差异只剩 ``injected_value``。
    """
    return random.Random(f"{order_stem}|{item_index}|{field}")


def inject_wrong_value(
    field: str,
    gold: Any,
    locators: List[Dict[str, Any]],
    rng: random.Random,
    difficulty: str = "gross",
) -> Optional[Any]:
    """注入一个「像真的」错误值。

    - ``subtle``：**所有字段**统一注入「同列另一行的真实取值」，且优先挑与 gold 最
      相似的候选。错误值在原表中真实存在，只有回到正确的那一格才能发现。
    - ``gross``：数值字段用十进制位错位（``100 → 1000``）；交期后移一周；文本字段
      随机取同列另一个真实取值。错误值一眼可辨，重读原订单即可修正。
    """
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"未知的注入难度 {difficulty!r}，可选 {DIFFICULTIES}")

    alternatives = _alternatives_in_column(field, gold, locators)

    if difficulty == "subtle":
        return _most_similar(gold, alternatives) if alternatives else None

    if field in NUMERIC_FIELDS:
        number = _to_decimal(gold)
        if number is None or number == 0:
            return None
        wrong = number * 10
        return float(wrong) if wrong != number else None

    if field == "delivery_date":
        parsed = _to_date(gold)
        if parsed is None:
            return None
        return (parsed + timedelta(days=7)).isoformat()

    return rng.choice(alternatives) if alternatives else None


def build_sample(
    order_path: Path,
    annotation: Dict[str, Any],
    loader: DocumentLoader,
    ordinal: int,
    rng: random.Random,
    usage: Dict[str, int],
    difficulty: str = "gross",
) -> Optional[Dict[str, Any]]:
    """把一份订单 + 一条注入错误，构成一条可独立重跑的样本。"""
    document_ir, document_type = loader.load_ir(str(order_path))
    if document_type != "excel":
        return None

    locators = find_item_locators(document_ir, None)
    if not locators:
        return None

    region = {"kind": "sheet", "name": locators[0]["sheet"]}
    order_text = Extractor.region_source(document_ir, region)
    if not order_text.strip():
        return None

    available = [
        field for field in FIELD_ROTATION
        if any(locator["columns"].get(field) is not None
               and locator["values"].get(field) not in (None, "")
               for locator in locators)
    ]
    if not available:
        return None

    # 均衡分配：优先挑目前用得最少的字段，避免某一类字段垄断全部样本。
    field = min(available, key=lambda name: (usage.get(name, 0), FIELD_ROTATION.index(name)))
    target = _pick_target(locators, field, rng)
    if target is None:
        return None
    item_index, locator, column, gold = target

    # 统一种子条件：样本必须在**两档下都可注入**，否则某一档会跳过、usage 计数漂移，
    # 后续订单的字段分配随之分叉，两档就不再是同一批样本。
    if not _alternatives_in_column(field, gold, locators):
        return None
    if field in NUMERIC_FIELDS:
        number = _to_decimal(gold)
        if number is None or number == 0:
            return None

    injected = inject_wrong_value(
        field, gold, locators,
        _injection_rng(order_path.stem, item_index, field),
        difficulty=difficulty,
    )
    if injected is None:
        return None

    usage[field] = usage.get(field, 0) + 1
    return {
        "sample_id": f"{order_path.stem}#item{item_index}.{field}",
        "order_id": order_path.stem,
        "order_text": order_text,
        "region": region,
        "difficulty": difficulty,
        "item_index": item_index,
        "field": field,
        "gold_value": gold,
        "injected_value": injected,
        "material_name": locator["values"].get("material_name"),
        "locator": {
            "kind": "cell",
            "sheet": locator["sheet"],
            "row": locator["row"],
            "column": column,
        },
        "annotation_gold": _annotation_value(annotation, item_index, field),
    }
    return None


def _annotation_value(annotation: Dict[str, Any], item_index: int, field: str) -> Any:
    """取标注值，仅用于事后审计源单元格与标注是否一致；不参与判定。"""
    items = annotation.get("items") or []
    if item_index >= len(items):
        return None
    item = items[item_index]
    if field == "material_name":
        return item.get("material_name_raw")
    if field == "specification":
        return item.get("specification_raw")
    return item.get(field)


def collect_samples(
    limit: Optional[int], seed: int, difficulty: str = "gross"
) -> List[Dict[str, Any]]:
    loader = DocumentLoader()
    rng = random.Random(seed)
    usage: Dict[str, int] = {}
    samples: List[Dict[str, Any]] = []
    skipped = 0

    for ordinal, order_path in enumerate(sorted(ORDERS_DIR.glob("*.xlsx"))):
        if limit is not None and len(samples) >= limit:
            break
        annotation_path = ANNOTATIONS_DIR / f"{order_path.stem}.json"
        if not annotation_path.exists():
            skipped += 1
            continue
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        sample = build_sample(order_path, annotation, loader, ordinal, rng, usage,
                              difficulty=difficulty)
        if sample is None:
            skipped += 1
            continue
        samples.append(sample)

    if skipped:
        print(f"[样本] 跳过 {skipped} 份订单（无定位符 / 字段全空 / 无可用替换值）",
              file=sys.stderr)
    return samples


# --------------------------------------------------------------------- 挑战与判定

def build_challenge(sample: Dict[str, Any]) -> AgentMessage:
    """构造一条与 GroundingVerifier._verify_against_cells 形态一致的合法挑战。"""
    item_index = sample["item_index"]
    field = sample["field"]
    gold = sample["gold_value"]
    injected = sample["injected_value"]
    locator = sample["locator"]
    subject = f"item[{item_index}].{field}"

    reason = (
        f"第 {item_index + 1} 项 {field} 与工作表 {locator['sheet']} "
        f"第 {locator['row']} 行对应列不一致："
        f"原单元格为 {gold!r}，抽取为 {injected!r}。"
    )
    return AgentMessage(
        order_id=sample["order_id"],
        task_id=f"novelty-{sample['sample_id']}",
        sender="grounding_verifier",
        performative=Performative.CHALLENGE,
        subject={"claim_subject": subject, "item_index": item_index, "field": field},
        payload={"reason": reason, "item_index": item_index, "field": field},
        evidence=challenge_evidence(
            subject=subject, locator=locator, expected=injected, actual=gold
        ),
    )


def _locate_predicted_item(parsed: Any, sample: Dict[str, Any]) -> Tuple[Any, str]:
    """在重抽结果里找到被挑战的那一行：先按位置，再按物料名回退。"""
    gold_key = normalize_text(str(sample["material_name"] or ""))
    index = sample["item_index"]
    if index < len(parsed.items):
        candidate = parsed.items[index]
        if normalize_text(str(candidate.material_name or "")) == gold_key:
            return candidate, "positional"
    for position, candidate in enumerate(parsed.items):
        if normalize_text(str(candidate.material_name or "")) == gold_key:
            return candidate, f"matched_by_name@{position}"
    return None, "unmatched"


def run_once(extractor: Extractor, sample: Dict[str, Any], mode: str) -> Dict[str, Any]:
    challenge = build_challenge(sample)
    feedback = build_counter_evidence_feedback([challenge], mode=mode)
    before = dict(extractor.last_usage)
    started = perf_counter()
    parsed: Any = None
    error: Optional[str] = None
    try:
        parsed = extractor.extract_text(sample["order_text"], feedback=feedback)
    except Exception as exc:  # noqa: BLE001 - 失败样本必须记下来，不能中断整轮
        error = f"{type(exc).__name__}: {exc}"
    latency_ms = round((perf_counter() - started) * 1000, 2)
    usage = {
        key: extractor.last_usage.get(key, 0) - before.get(key, 0)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }

    field = sample["field"]
    if parsed is None:
        return {"predicted": None, "match": "error", "outcome": OUTCOME_ERROR,
                "error": error, "latency_ms": latency_ms, **usage}

    item, match = _locate_predicted_item(parsed, sample)
    predicted = None if item is None else getattr(item, field, None)
    # 判定口径直接复用验证者自己的相等判断，保证「修正率」等于验证者会接受的比例。
    if item is not None and GroundingVerifier._cell_matches(field, sample["gold_value"], predicted):
        outcome = OUTCOME_CORRECTED
    elif predicted is None:
        outcome = OUTCOME_ABSTAINED
    elif GroundingVerifier._cell_matches(field, sample["injected_value"], predicted):
        outcome = OUTCOME_UNCHANGED
    else:
        outcome = OUTCOME_OTHER_WRONG

    return {"predicted": _jsonable(predicted), "match": match, "outcome": outcome,
            "error": error, "latency_ms": latency_ms, **usage}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


# --------------------------------------------------------------------- 统计

def _rate(rows: List[Dict[str, Any]], outcome: str) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row["outcome"] == outcome) / len(rows)


def _majority(flags: List[bool]) -> bool:
    return sum(flags) * 2 > len(flags)


def mcnemar_exact(discordant_b: int, discordant_c: int) -> float:
    """配对二分结果的精确 McNemar 检验（双侧）。"""
    total = discordant_b + discordant_c
    if total == 0:
        return 1.0
    from scipy.stats import binomtest

    return float(binomtest(min(discordant_b, discordant_c), total, 0.5).pvalue)


def summarize(samples: List[Dict[str, Any]], runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_key: Dict[Tuple[str, str, int], Dict[str, Any]] = {
        (row["sample_id"], row["arm"], row["repeat"]): row for row in runs
    }
    per_arm: Dict[str, Dict[str, Any]] = {}
    sample_majority: Dict[str, Dict[str, bool]] = {}

    for arm, _mode in ARMS:
        arm_rows = [row for row in runs if row["arm"] == arm]
        per_arm[arm] = {
            "calls": len(arm_rows),
            "correction_rate": _rate(arm_rows, OUTCOME_CORRECTED),
            "abstention_rate": _rate(arm_rows, OUTCOME_ABSTAINED),
            "unchanged_rate": _rate(arm_rows, OUTCOME_UNCHANGED),
            "over_correction_rate": _rate(arm_rows, OUTCOME_OTHER_WRONG),
            "error_rate": _rate(arm_rows, OUTCOME_ERROR),
            "mean_total_tokens": _mean([row["total_tokens"] or 0 for row in arm_rows]),
            "mean_latency_ms": _mean([row["latency_ms"] for row in arm_rows]),
        }
        sample_majority[arm] = {}
        for sample in samples:
            flags = [
                by_key[(sample["sample_id"], arm, repeat)]["outcome"] == OUTCOME_CORRECTED
                for repeat in range(_repeats_of(runs, arm))
                if (sample["sample_id"], arm, repeat) in by_key
            ]
            if flags:
                sample_majority[arm][sample["sample_id"]] = _majority(flags)

    arm_a, arm_b = ARMS[0][0], ARMS[1][0]
    paired = [
        (sample_majority[arm_a][sample["sample_id"]], sample_majority[arm_b][sample["sample_id"]])
        for sample in samples
        if sample["sample_id"] in sample_majority[arm_a]
        and sample["sample_id"] in sample_majority[arm_b]
    ]
    b_count = sum(1 for a_correct, b_correct in paired if not a_correct and b_correct)
    c_count = sum(1 for a_correct, b_correct in paired if a_correct and not b_correct)
    p_value = mcnemar_exact(b_count, c_count)

    delta = per_arm[arm_b]["correction_rate"] - per_arm[arm_a]["correction_rate"]
    abstention_delta = per_arm[arm_b]["abstention_rate"] - per_arm[arm_a]["abstention_rate"]

    if p_value < 0.05 and delta > 0:
        verdict = "GO"
    elif abstention_delta < 0 and per_arm[arm_a]["abstention_rate"] > 0:
        verdict = "WEAK_GO"
    else:
        verdict = "NO_GO"

    return {
        "per_arm": per_arm,
        "paired_samples": len(paired),
        "discordant_a_wrong_b_right": b_count,
        "discordant_a_right_b_wrong": c_count,
        "delta_correction_rate": delta,
        "delta_abstention_rate": abstention_delta,
        "mcnemar_p_value": p_value,
        "verdict": verdict,
        "arm_a": arm_a,
        "arm_b": arm_b,
    }


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _repeats_of(runs: List[Dict[str, Any]], arm: str) -> int:
    return max((row["repeat"] for row in runs if row["arm"] == arm), default=-1) + 1


# --------------------------------------------------------------------- 产物

def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_summary_csv(path: Path, samples: List[Dict[str, Any]],
                      runs: List[Dict[str, Any]]) -> None:
    fields = ["sample_id", "order_id", "item_index", "field", "gold_value",
              "injected_value", "arm", "repeat", "predicted", "outcome",
              "match", "total_tokens", "latency_ms"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in runs:
            writer.writerow({key: row.get(key) for key in fields})


def build_summary_markdown(summary: Dict[str, Any], samples: List[Dict[str, Any]],
                           repeats: int, model: str) -> str:
    arm_a, arm_b = summary["arm_a"], summary["arm_b"]
    per_arm = summary["per_arm"]
    lines = [
        "# 新颖性判决实验（G0）结果",
        "",
        f"- 样本数：{len(samples)}",
        f"- 重复次数：每样本每臂 {repeats} 次",
        f"- 模型：`{model}`",
        f"- 总调用数：{per_arm[arm_a]['calls'] + per_arm[arm_b]['calls']}",
        "",
        "## 两臂指标",
        "",
        f"| 指标 | {arm_a}（自然语言） | {arm_b}（locator） | Δ(B−A) |",
        "|---|---|---|---|",
    ]
    rows = [
        ("幻觉修正率（主指标）", "correction_rate"),
        ("弃权率（改判为 null）", "abstention_rate"),
        ("未修正率（原样保留错值）", "unchanged_rate"),
        ("过度修正率（换成另一个错值）", "over_correction_rate"),
        ("调用失败率", "error_rate"),
    ]
    for label, key in rows:
        a_value, b_value = per_arm[arm_a][key], per_arm[arm_b][key]
        lines.append(f"| {label} | {a_value:.4f} | {b_value:.4f} | {b_value - a_value:+.4f} |")
    lines += [
        f"| 平均 token/次 | {per_arm[arm_a]['mean_total_tokens']:.1f} "
        f"| {per_arm[arm_b]['mean_total_tokens']:.1f} "
        f"| {per_arm[arm_b]['mean_total_tokens'] - per_arm[arm_a]['mean_total_tokens']:+.1f} |",
        f"| 平均延迟 ms | {per_arm[arm_a]['mean_latency_ms']:.0f} "
        f"| {per_arm[arm_b]['mean_latency_ms']:.0f} "
        f"| {per_arm[arm_b]['mean_latency_ms'] - per_arm[arm_a]['mean_latency_ms']:+.0f} |",
        "",
        "## 配对检验（McNemar 精确检验，双侧，α = 0.05）",
        "",
        f"- 可配对样本：{summary['paired_samples']}",
        f"- A 错 / B 对：{summary['discordant_a_wrong_b_right']}",
        f"- A 对 / B 错：{summary['discordant_a_right_b_wrong']}",
        f"- 修正率差 Δ：{summary['delta_correction_rate']:+.4f}",
        f"- p 值：{summary['mcnemar_p_value']:.4f}",
        "",
        "## 判定（对照 paper/06_NOVELTY_EXPERIMENT.md §6）",
        "",
        f"**{summary['verdict']}**",
        "",
    ]
    if summary["verdict"] == "GO":
        lines.append("Arm B 修正率显著高于 Arm A → C1/C2 成立，按准备计划阶段 B–E 推进。")
    elif summary["verdict"] == "WEAK_GO":
        lines.append("修正率差异不显著，但 Arm B 弃权率更低 → 主张需收窄为"
                     "「证据形态影响核对行为」而非「提升修正率」。")
    else:
        lines.append("两臂无差异 → 停止投稿，改走「系统论文 + 边界声明」或转期刊路线。"
                     "只损失 2 周。")
    lines += [
        "",
        "> 复现实验前请核对 `run_manifest.json`：代码版本、提示词指纹、模型配置、"
        "样本指纹任一变化都会使本次结果不可比。",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------- 主流程

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="新颖性判决实验（G0）")
    parser.add_argument("--samples", type=int, default=50, help="样本数，默认 50")
    parser.add_argument("--limit", type=int, default=None, help="只跑前 N 条（小规模试跑）")
    parser.add_argument("--repeats", type=int, default=3, help="每样本每臂重复次数，默认 3")
    parser.add_argument("--seed", type=int, default=20261001, help="样本抽样随机种子")
    parser.add_argument("--dry-run", action="store_true", help="只造样本，不调用模型")
    parser.add_argument("--model", default=None, help="覆盖模型名")
    parser.add_argument("--base-url", default=None, help="覆盖服务商端点")
    parser.add_argument("--api-key", default=None, help="覆盖 API key（默认读环境变量）")
    parser.add_argument("--output-dir", default=None, help="产物目录")
    parser.add_argument(
        "--difficulty", choices=DIFFICULTIES, default="gross",
        help="注入难度：gross=一眼可辨（数值 ×10）；subtle=同列另一行的真实值（行错位）。"
             "默认 gross，与 2026-10-02 试跑口径一致。",
    )
    parser.add_argument(
        "--max-output-tokens", type=int, default=None,
        help="把单次输出的 max_tokens 上限下调到该值。弱模型的接口上限可能只有 8192，"
             "而生产默认是 16384，不改会 400 并表现为「模型 100%% error」。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    limit = args.limit if args.limit is not None else args.samples

    print(f"[样本] 从 {ORDERS_DIR} 构造样本，上限 {limit} 条"
          f"（注入难度 {args.difficulty}）…", file=sys.stderr)
    samples = collect_samples(limit, args.seed, difficulty=args.difficulty)
    if not samples:
        print("[样本] 没有构造出任何样本，检查数据集路径。", file=sys.stderr)
        return 1

    config = Config()
    if args.model:
        config.model.model = args.model
    if args.base_url:
        config.model.base_url = args.base_url
    if args.api_key:
        config.model.api_key = args.api_key

    budgets = apply_output_token_budget(args.max_output_tokens)
    print(f"[模型] {config.model.model}；单次输出上限 {budgets}", file=sys.stderr)

    run_dir = Path(args.output_dir) if args.output_dir else (
        RESULTS_ROOT
        / f"novelty_experiment_{args.difficulty}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(run_dir / "samples.jsonl", samples)

    field_counts: Dict[str, int] = {}
    for sample in samples:
        field_counts[sample["field"]] = field_counts.get(sample["field"], 0) + 1
    print(f"[样本] 共 {len(samples)} 条；字段分布 {field_counts}", file=sys.stderr)

    if args.dry_run:
        print(f"[dry-run] 样本已写入 {run_dir / 'samples.jsonl'}，未调用模型。", file=sys.stderr)
        print(f"[dry-run] 字段分布：{field_counts}")
        return 0

    if not config.model.api_key:
        print("[错误] 未配置模型 API key（环境变量 QWEN_API_KEY 或 --api-key）。"
              "请直连服务商官方端点，不要使用中转站。", file=sys.stderr)
        return 1

    _write_run_manifest(run_dir, config, samples)

    extractor = Extractor(config=config)
    runs: List[Dict[str, Any]] = []
    total = len(samples) * len(ARMS) * args.repeats
    done = 0
    # 交错执行：同一重复内先跑两臂，避免「某一臂总是排在后面」带来的漂移。
    for repeat in range(args.repeats):
        for sample in samples:
            for arm, mode in ARMS:
                result = run_once(extractor, sample, mode)
                runs.append({
                    "sample_id": sample["sample_id"], "arm": arm, "repeat": repeat,
                    "order_id": sample["order_id"], "item_index": sample["item_index"],
                    "field": sample["field"], "gold_value": _jsonable(sample["gold_value"]),
                    "injected_value": _jsonable(sample["injected_value"]),
                    "mode": mode, **result,
                })
                done += 1
                print(f"[{done}/{total}] {sample['sample_id']} {arm} "
                      f"→ {result['outcome']}", file=sys.stderr)

    summary = summarize(samples, runs)
    write_jsonl(run_dir / "predictions.jsonl", runs)
    write_summary_csv(run_dir / "summary.csv", samples, runs)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "summary.md").write_text(
        build_summary_markdown(summary, samples, args.repeats, config.model.model),
        encoding="utf-8",
    )

    print(f"\n产物目录：{run_dir}")
    print(f"判定：{summary['verdict']}（Δ修正率={summary['delta_correction_rate']:+.4f}，"
          f"p={summary['mcnemar_p_value']:.4f}）")
    print(f"请把判定结果记入 paper/02_DECISIONS.md 的 G0 条目。")
    return 0


def apply_output_token_budget(max_output_tokens: Optional[int]) -> Dict[str, int]:
    """把单次输出的 ``max_tokens`` 上限下调到指定值。

    **为什么需要**：``extractor.EXTRACTION_MAX_TOKENS`` 硬编码为 16384，而部分模型
    （如 ``qwen3-8b``）的接口上限是 8192，直接调用会返回
    ``400 InvalidParameter: Range of max_tokens should be [1, 8192]``——
    这会表现为「该模型 100% error」，很容易被误判成「模型能力不够」。

    **为什么放在脚本里而不是生产代码**：生产代码属于冻结基线 ``paper-v1-baseline``，
    实验期不修改，否则整篇论文的可复现性主张失效。这是**实验专用旋钮**，
    取值会写入 run manifest 留痕。
    """
    from application.agents import extractor as extractor_module
    from application.agents import review_assistant as review_module

    targets = (
        (extractor_module, "EXTRACTION_MAX_TOKENS"),
        (review_module, "REVIEW_MAX_TOKENS"),
    )
    if max_output_tokens is not None and max_output_tokens < 1:
        raise ValueError("--max-output-tokens 必须为正整数")

    effective: Dict[str, int] = {}
    for module, name in targets:
        current = getattr(module, name)
        if max_output_tokens is not None:
            current = min(current, max_output_tokens)
            setattr(module, name, current)
        effective[name] = current
    return effective


def _write_run_manifest(run_dir: Path, config: Config, samples: List[Dict[str, Any]]) -> None:
    """复用评测运行身份机制，保证实验可复现（也是论文 C4 的实证素材）。"""
    from evaluation.run_evaluation import build_run_identity, identity_hash

    documents = [ORDERS_DIR / f"{sample['order_id']}.xlsx" for sample in samples]
    try:
        identity = build_run_identity(
            config, documents=documents, annotation_dir=ANNOTATIONS_DIR,
            manifest_map={}, manifest_base_dir=None, manifest_csv=None,
        )
    except Exception as exc:  # noqa: BLE001 - 身份记录失败不应阻断实验，但必须留痕
        identity = {"identity_error": f"{type(exc).__name__}: {exc}"}

    identity["experiment"] = "novelty_verdict_g0"
    identity["arms"] = [{"name": arm, "feedback_mode": mode} for arm, mode in ARMS]
    identity["difficulty"] = samples[0].get("difficulty") if samples else None
    identity["output_token_budget"] = apply_output_token_budget(None)
    identity["sample_count"] = len(samples)
    identity["sample_fingerprint"] = _fingerprint_samples(samples)
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_identity": identity, "identity_hash": identity_hash(identity)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _fingerprint_samples(samples: List[Dict[str, Any]]) -> str:
    import hashlib

    payload = json.dumps(
        [{key: sample[key] for key in ("sample_id", "difficulty", "field", "gold_value",
                                       "injected_value", "locator")}
         for sample in samples],
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
