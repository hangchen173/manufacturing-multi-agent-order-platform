"""字段级评分（VEAP 与所有基线共用同一口径）。

**为什么不直接用 `metrics.MetricsCollector`**：它绑定在 `run_evaluation.py` 的
落盘流程上（需要 `prediction` / `business_decision` 等完整响应结构）。
本实验要比较的是**抽取字段本身**，需要一个能从「任意一个 `ParsedOrder`」
直接算分的轻量口径。判等仍复用 `metrics.values_match`，保证与主评测同口径——
否则「基线 92% / VEAP 95%」这种数字就失去意义。

**对齐方式**：明细行按**位置**对齐。所有方法读的是同一份订单原文，
明细行的顺序由原文决定，因此位置是最自然、也最不可操纵的对齐键。
（按物料名对齐会引入「名字错就整行对不上」的二次惩罚，把字段错误放大成行错误。）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

#: (ParsedOrder 字段, 标注字段)。标注里物料名/规格带 `_raw` 后缀，
#: 因为它要求「忠实保留原值、不做标准化」——见 `extractor._TEXT_SYSTEM_PROMPT` 第 5 条。
ITEM_FIELD_MAP: Tuple[Tuple[str, str], ...] = (
    ("material_name", "material_name_raw"),
    ("specification", "specification_raw"),
    ("quantity", "quantity"),
    ("unit", "unit"),
    ("unit_price", "unit_price"),
    ("delivery_date", "delivery_date"),
)

ORDER_FIELD_MAP: Tuple[Tuple[str, str], ...] = (
    ("order_number", "order_number"),
    ("customer_name", "customer_name"),
    ("total_amount", "total_amount"),
)


def _is_annotated(value: Any) -> bool:
    """标注中「有值」才算入分母。标注为空的字段无从判断对错。"""
    return value is not None and value != ""


def score_order(parsed: Optional[Any], annotation: Dict[str, Any]) -> Dict[str, Any]:
    """算一份订单的字段级命中情况。

    返回：
    - ``order_fields`` / ``item_fields``：字段 → ``{"matched": int, "total": int}``
    - ``items_expected`` / ``items_predicted``：行数（用于诊断「漏抽/多抽」）
    """
    from evaluation.metrics import values_match

    order_level = annotation.get("order_level") or {}
    gold_items: List[Dict[str, Any]] = list(annotation.get("items") or [])
    predicted_items: List[Any] = list(getattr(parsed, "items", None) or []) if parsed else []

    order_fields = {gold: {"matched": 0, "total": 0} for _, gold in ORDER_FIELD_MAP}
    item_fields = {pred: {"matched": 0, "total": 0} for pred, _ in ITEM_FIELD_MAP}

    # 订单级字段**无条件计入分母**：预测为 None（运行失败）是「没答对」，
    # 不是「不用答」。若把失败样本的字段剔出分母，失败越多分母越小、
    # 准确率反而越好看——这正是最不该出现在对照实验里的偏差。
    # （明细级字段天然遵循同一规则，见下方循环。）
    for pred_field, gold_field in ORDER_FIELD_MAP:
        expected = order_level.get(gold_field)
        if not _is_annotated(expected):
            continue
        order_fields[gold_field]["total"] += 1
        if parsed is not None and values_match(expected, getattr(parsed, pred_field, None)):
            order_fields[gold_field]["matched"] += 1

    for index, gold_item in enumerate(gold_items):
        predicted = predicted_items[index] if index < len(predicted_items) else None
        for pred_field, gold_field in ITEM_FIELD_MAP:
            expected = gold_item.get(gold_field)
            if not _is_annotated(expected):
                continue
            item_fields[pred_field]["total"] += 1
            if predicted is not None and values_match(
                expected, getattr(predicted, pred_field, None)
            ):
                item_fields[pred_field]["matched"] += 1

    return {
        "order_fields": order_fields,
        "item_fields": item_fields,
        "items_expected": len(gold_items),
        "items_predicted": len(predicted_items),
    }


def merge_counts(target: Dict[str, Dict[str, int]], source: Dict[str, Dict[str, int]]) -> None:
    """把一份订单的计数累加进总计。"""
    for field_name, counts in source.items():
        slot = target.setdefault(field_name, {"matched": 0, "total": 0})
        slot["matched"] += counts["matched"]
        slot["total"] += counts["total"]


def accuracy(counts: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    """把「字段 → matched/total」汇总成总体准确率。"""
    matched = sum(counts[field]["matched"] for field in counts)
    total = sum(counts[field]["total"] for field in counts)
    return {
        "matched": matched,
        "total": total,
        "accuracy": (matched / total) if total else 0.0,
        "per_field": {
            field: {
                **counts[field],
                "accuracy": (counts[field]["matched"] / counts[field]["total"])
                if counts[field]["total"] else 0.0,
            }
            for field in counts
        },
    }
