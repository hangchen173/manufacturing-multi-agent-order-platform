from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from time import perf_counter

from domain.models import OrderStatus


@dataclass
class StageExecutionResult:
    success: bool
    message: str
    payload: Any = None
    usage: Dict[str, int] = field(default_factory=dict)


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
            expected_status={
                OrderStatus.PARSING: OrderStatus.PENDING,
                OrderStatus.MATCHING: OrderStatus.PARSING,
                OrderStatus.RISK_CHECKING: OrderStatus.MATCHING,
            }[self.target_status],
        )
        if not status_updated:
            return StageExecutionResult(
                success=False,
                message=f"{self.name} 阶段启动失败",
            )

        start = perf_counter()
        try:
            result = self.runner(input_data)
        except Exception as exc:
            result = {"success": False, "message": f"{self.name} 阶段执行异常: {exc}"}
        elapsed_ms = (perf_counter() - start) * 1000
        usage = result.get("usage") or {}
        recorded = order_manager.record_stage(order_id, self.name, {
            "runner_latency_ms": round(elapsed_ms, 2),
            "success": bool(result.get("success")),
            "usage": usage,
            **(result.get("diagnostics") or {}),
        })
        if not recorded:
            message = f"{self.name} 阶段诊断记录持久化失败"
            order_manager.set_error(order_id, message)
            return StageExecutionResult(success=False, message=message, usage=usage)
        if not result.get("success"):
            message = result.get("message", f"{self.name} 阶段执行失败")
            order_manager.set_error(order_id, message)
            return StageExecutionResult(
                success=False,
                message=message,
                usage=usage,
            )

        payload = result.get(self.payload_key)
        if self.persist_callback is not None:
            persisted = self.persist_callback(order_id, payload)
            if not persisted:
                message = f"{self.name} 阶段结果持久化失败"
                order_manager.set_error(order_id, message)
                return StageExecutionResult(success=False, message=message, usage=usage)

        return StageExecutionResult(
            success=True,
            message=result.get("message", f"{self.name} 阶段执行成功"),
            payload=payload,
            usage=usage,
        )
