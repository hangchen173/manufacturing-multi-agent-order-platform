from __future__ import annotations

from typing import Any, Dict


DECISION_ACTIONS = {"auto_approve", "auto_correct", "manual_review"}


def normalize_annotation(annotation: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize annotations to the single evaluation contract."""
    if not isinstance(annotation, dict):
        raise ValueError("annotation must be a JSON object")
    required = ("document_id", "order_level", "items")
    missing = [key for key in required if key not in annotation]
    if missing:
        raise ValueError(f"annotation missing required fields: {', '.join(missing)}")
    if not isinstance(annotation["order_level"], dict) or not isinstance(annotation["items"], list):
        raise ValueError("order_level must be an object and items must be a list")

    decision = annotation.get("business_decision")
    if not isinstance(decision, dict) or decision.get("action") not in DECISION_ACTIONS:
        raise ValueError("business_decision.action must be auto_approve, auto_correct, or manual_review")
    annotation["business_decision"] = decision
    for index, item in enumerate(annotation["items"], start=1):
        if not isinstance(item, dict):
            raise ValueError(f"items[{index - 1}] must be an object")
        item.setdefault("line_index", index)
    return annotation


def predicted_action(prediction: Dict[str, Any]) -> str:
    explicit = prediction.get("business_decision")
    if isinstance(explicit, dict) and explicit.get("action") in DECISION_ACTIONS:
        return explicit["action"]
    return "manual_review" if prediction.get("needs_confirmation") else "auto_approve"
