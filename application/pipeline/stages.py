from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from domain.models import OrderStatus


@dataclass
class StageExecutionResult:
    success: bool
    message: str
    payload: Any = None


class AgentPipelineStage:
    def __init__(
        self,
        name: str,
        target_status: OrderStatus,
        status_reason: str,
        runner: Callable[[Dict[str, Any]], Dict[str, Any]],
        payload_key: str,
        persist_callback: Optional[Callable[[str, Any], bool]] = None,
    ):
        self.name = name
        self.target_status = target_status
        self.status_reason = status_reason
        self.runner = runner
        self.payload_key = payload_key
        self.persist_callback = persist_callback

    def execute(self, order_manager: Any, order_id: str, input_data: Dict[str, Any]) -> StageExecutionResult:
        status_updated = order_manager.update_order_status(
            order_id,
            self.target_status,
            reason=self.status_reason,
        )
        if not status_updated:
            return StageExecutionResult(
                success=False,
                message=f"{self.name} 阶段启动失败",
            )

        result = self.runner(input_data)
        if not result.get("success"):
            message = result.get("message", f"{self.name} 阶段执行失败")
            order_manager.set_error(order_id, message)
            return StageExecutionResult(
                success=False,
                message=message,
            )

        payload = result.get(self.payload_key)
        if self.persist_callback is not None:
            self.persist_callback(order_id, payload)

        return StageExecutionResult(
            success=True,
            message=result.get("message", f"{self.name} 阶段执行成功"),
            payload=payload,
        )
