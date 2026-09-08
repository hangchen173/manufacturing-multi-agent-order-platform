from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from evaluation.contracts import predicted_action


ORDER_LEVEL_FIELDS = [
    "order_number",
    "customer_name",
    "total_amount",
]

ITEM_LEVEL_FIELDS = [
    "material_name_raw",
    "specification_raw",
    "quantity",
    "unit",
    "unit_price",
    "delivery_date",
]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def normalize_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def values_match(expected: Any, predicted: Any, tolerance: float = 1e-3) -> bool:
    expected_num = normalize_float(expected)
    predicted_num = normalize_float(predicted)

    if expected_num is not None and predicted_num is not None:
        return abs(expected_num - predicted_num) <= tolerance

    return normalize_text(expected) == normalize_text(predicted)


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


@dataclass
class FieldCounter:
    matched: int = 0
    total: int = 0

    def add(self, is_match: bool) -> None:
        self.total += 1
        if is_match:
            self.matched += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matched": self.matched,
            "total": self.total,
            "accuracy": safe_divide(self.matched, self.total),
        }


@dataclass
class EvaluationAccumulator:
    total_samples: int = 0
    success_count: int = 0
    failure_count: int = 0
    annotated_samples: int = 0
    needs_confirmation_count: int = 0
    total_latency_ms: float = 0.0
    total_parsed_items: int = 0
    total_matched_items: int = 0
    total_risk_issues: int = 0
    order_field_counters: Dict[str, FieldCounter] = field(
        default_factory=lambda: {field: FieldCounter() for field in ORDER_LEVEL_FIELDS}
    )
    item_field_counters: Dict[str, FieldCounter] = field(
        default_factory=lambda: {field: FieldCounter() for field in ITEM_LEVEL_FIELDS}
    )
    sku_top1_counter: FieldCounter = field(default_factory=FieldCounter)
    confirmation_counter: FieldCounter = field(default_factory=FieldCounter)
    item_count_exact_counter: FieldCounter = field(default_factory=FieldCounter)
    decision_counter: FieldCounter = field(default_factory=FieldCounter)
    auto_release_counter: FieldCounter = field(default_factory=FieldCounter)

    def record_sample(
        self,
        *,
        success: bool,
        latency_ms: float,
        needs_confirmation: bool,
        parsed_item_count: int,
        matched_item_count: int,
        risk_issue_count: int,
        annotation: Optional[Dict[str, Any]] = None,
        prediction: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.total_samples += 1
        self.total_latency_ms += latency_ms
        self.total_parsed_items += parsed_item_count
        self.total_matched_items += matched_item_count
        self.total_risk_issues += risk_issue_count

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        if needs_confirmation:
            self.needs_confirmation_count += 1

        if annotation and prediction:
            self.annotated_samples += 1
            self._record_annotated_metrics(annotation, prediction)

    def _record_annotated_metrics(self, annotation: Dict[str, Any], prediction: Dict[str, Any]) -> None:
        predicted_final = prediction.get("final_result") or {}
        predicted_parsed = predicted_final.get("parsed_order") or {}
        predicted_matched = predicted_final.get("matched_order") or {}
        predicted_items = predicted_matched.get("items") or predicted_parsed.get("items") or []

        expected_order_level = annotation.get("order_level", {})
        for field_name in ORDER_LEVEL_FIELDS:
            if field_name in expected_order_level:
                expected_value = expected_order_level[field_name]
                predicted_value = predicted_parsed.get(field_name)
                self.order_field_counters[field_name].add(values_match(expected_value, predicted_value))

        expected_items = annotation.get("items", [])
        self.item_count_exact_counter.add(len(expected_items) == len(predicted_items))

        for index in range(max(len(expected_items), len(predicted_items))):
            expected_item = expected_items[index] if index < len(expected_items) else {}
            predicted_item = predicted_items[index] if index < len(predicted_items) else {}

            expected_field_map = {
                "material_name_raw": expected_item.get("material_name_raw"),
                "specification_raw": expected_item.get("specification_raw"),
                "quantity": expected_item.get("quantity"),
                "unit": expected_item.get("unit"),
                "unit_price": expected_item.get("unit_price"),
                "delivery_date": expected_item.get("delivery_date"),
            }
            predicted_field_map = {
                "material_name_raw": predicted_item.get("material_name"),
                "specification_raw": predicted_item.get("specification"),
                "quantity": predicted_item.get("quantity"),
                "unit": predicted_item.get("unit"),
                "unit_price": predicted_item.get("unit_price"),
                "delivery_date": predicted_item.get("delivery_date"),
            }

            for field_name in ITEM_LEVEL_FIELDS:
                if field_name in expected_item:
                    self.item_field_counters[field_name].add(
                        values_match(expected_field_map[field_name], predicted_field_map[field_name])
                    )

            golden_sku = expected_item.get("golden_sku_code")
            self.sku_top1_counter.add(
                values_match(golden_sku, predicted_item.get("sku_code"))
                if golden_sku not in (None, "")
                else predicted_item.get("sku_code") in (None, "")
            )

        expected_decision = annotation.get("business_decision") or {}
        if expected_decision.get("action"):
            actual_action = predicted_action(prediction)
            self.decision_counter.add(expected_decision["action"] == actual_action)
            self.confirmation_counter.add(
                (expected_decision["action"] == "manual_review")
                == (actual_action == "manual_review")
            )
            self.auto_release_counter.add(
                expected_decision["action"] != "manual_review"
                or actual_action == "manual_review"
            )

    def to_dict(self) -> Dict[str, Any]:
        summary = {
            "total_samples": self.total_samples,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": safe_divide(self.success_count, self.total_samples),
            "annotated_samples": self.annotated_samples,
            "needs_confirmation_count": self.needs_confirmation_count,
            "needs_confirmation_rate": safe_divide(
                self.needs_confirmation_count, self.total_samples
            ),
            "avg_latency_ms": safe_divide(self.total_latency_ms, self.total_samples),
            "avg_parsed_items": safe_divide(self.total_parsed_items, self.total_samples),
            "avg_matched_items": safe_divide(self.total_matched_items, self.total_samples),
            "avg_risk_issues": safe_divide(self.total_risk_issues, self.total_samples),
            "order_level_accuracy": {
                key: counter.to_dict() for key, counter in self.order_field_counters.items()
            },
            "item_level_accuracy": {
                key: counter.to_dict() for key, counter in self.item_field_counters.items()
            },
            "item_count_exact_match": self.item_count_exact_counter.to_dict(),
            "sku_top1_accuracy": self.sku_top1_counter.to_dict(),
            "confirmation_accuracy": self.confirmation_counter.to_dict(),
            "business_decision_accuracy": self.decision_counter.to_dict(),
            "error_auto_release_rate": safe_divide(
                self.auto_release_counter.total - self.auto_release_counter.matched,
                self.auto_release_counter.total,
            ),
        }
        return summary


def build_summary_markdown(
    *,
    dataset_name: str,
    input_dir: str,
    annotation_dir: Optional[str],
    summary: Dict[str, Any],
    failures: List[Dict[str, Any]],
) -> str:
    lines = [
        f"# Evaluation Summary: {dataset_name}",
        "",
        "## Run Info",
        "",
        f"- Input dir: `{input_dir}`",
        f"- Annotation dir: `{annotation_dir}`" if annotation_dir else "- Annotation dir: `None`",
        f"- Total samples: {summary['total_samples']}",
        f"- Success count: {summary['success_count']}",
        f"- Failure count: {summary['failure_count']}",
        f"- Success rate: {summary['success_rate']:.2%}",
        f"- Annotated samples: {summary['annotated_samples']}",
        f"- Avg latency: {summary['avg_latency_ms']:.2f} ms",
        f"- Needs confirmation rate: {summary['needs_confirmation_rate']:.2%}",
        "",
        "## Order-Level Accuracy",
        "",
    ]

    for field_name, result in summary["order_level_accuracy"].items():
        lines.append(
            f"- `{field_name}`: {result['matched']}/{result['total']} ({result['accuracy']:.2%})"
        )

    lines.extend(
        [
            "",
            "## Item-Level Accuracy",
            "",
        ]
    )
    for field_name, result in summary["item_level_accuracy"].items():
        lines.append(
            f"- `{field_name}`: {result['matched']}/{result['total']} ({result['accuracy']:.2%})"
        )

    lines.extend(
        [
            "",
            "## Extra Metrics",
            "",
            (
                f"- Item count exact match: "
                f"{summary['item_count_exact_match']['matched']}/"
                f"{summary['item_count_exact_match']['total']} "
                f"({summary['item_count_exact_match']['accuracy']:.2%})"
            ),
            (
                f"- SKU Top-1 accuracy: "
                f"{summary['sku_top1_accuracy']['matched']}/"
                f"{summary['sku_top1_accuracy']['total']} "
                f"({summary['sku_top1_accuracy']['accuracy']:.2%})"
            ),
            (
                f"- Confirmation accuracy: "
                f"{summary['confirmation_accuracy']['matched']}/"
                f"{summary['confirmation_accuracy']['total']} "
                f"({summary['confirmation_accuracy']['accuracy']:.2%})"
            ),
            (
                f"- Business decision accuracy: {summary['business_decision_accuracy']['matched']}/"
                f"{summary['business_decision_accuracy']['total']} "
                f"({summary['business_decision_accuracy']['accuracy']:.2%})"
            ),
            f"- Error auto-release rate: {summary['error_auto_release_rate']:.2%}",
            "",
            "## Failures",
            "",
        ]
    )

    if not failures:
        lines.append("- None")
    else:
        for failure in failures[:20]:
            lines.append(
                f"- `{failure['document_id']}`: {failure.get('message', 'unknown error')}"
            )

    return "\n".join(lines) + "\n"
