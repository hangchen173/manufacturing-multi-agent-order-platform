from typing import Dict, Optional, Set

from domain.exceptions import InvalidOrderStatusException
from domain.models import OrderStatus


ALLOWED_ORDER_TRANSITIONS: Dict[OrderStatus, Set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.PARSING, OrderStatus.FAILED},
    OrderStatus.PARSING: {OrderStatus.MATCHING, OrderStatus.FAILED},
    OrderStatus.MATCHING: {OrderStatus.RISK_CHECKING, OrderStatus.FAILED},
    OrderStatus.RISK_CHECKING: {
        OrderStatus.NEEDS_CONFIRMATION,
        OrderStatus.COMPLETED,
        OrderStatus.FAILED,
    },
    OrderStatus.NEEDS_CONFIRMATION: {OrderStatus.COMPLETED, OrderStatus.FAILED},
    OrderStatus.COMPLETED: set(),
    OrderStatus.FAILED: set(),
}


def can_transition(current_status: Optional[OrderStatus], target_status: OrderStatus) -> bool:
    if current_status is None:
        return target_status == OrderStatus.PENDING

    if current_status == target_status:
        return True

    return target_status in ALLOWED_ORDER_TRANSITIONS.get(current_status, set())


def validate_transition(
    current_status: Optional[OrderStatus],
    target_status: OrderStatus,
    force: bool = False,
) -> None:
    if force or can_transition(current_status, target_status):
        return

    expected_statuses = sorted(
        status.value for status in ALLOWED_ORDER_TRANSITIONS.get(current_status, set())
    )
    expected_label = ", ".join(expected_statuses) if expected_statuses else "terminal"

    raise InvalidOrderStatusException(
        order_id="unknown",
        current_status=current_status.value if current_status else "none",
        expected_status=expected_label,
    )
