"""模型输出的通用守卫：把「输出被截断」与「输出结构不对」区分开。

放在 protocol 层而非某个 Agent 内：它是跨角色的通用契约，多个 Agent 都要用。
若把它写进某个 Agent 模块，其他 Agent 引用它会形成同层 Agent 之间的直接依赖，
破坏「Agent 之间零直接调用」的拓扑约束（见 V1 拓扑测试）。

背景（2026-09 对真实接口实测）：推理型模型把「思考」与「正文」计入同一个
max_tokens 预算。预算被思考耗尽时，API 仍返回 HTTP 200，但
`finish_reason == 'length'` 且 `content == ''`。

此时若把空正文直接送进结构校验，会被归类成结构错误，于是系统带着一份
与真实故障无关的「字段级反馈」去重抽——既误导模型，又掩盖了「预算不足」的根因。
"""
from __future__ import annotations

from typing import Any, Optional

from domain.exceptions import ModelTruncationException


def assert_not_truncated(message: Any, agent_name: str,
                         max_tokens: Optional[int] = None) -> None:
    """校验模型返回了可用正文，否则抛出 ModelTruncationException。

    - `finish_reason == 'length'`：即使正文非空，也必然是被切断的半截内容
      （例如不完整的 JSON），同样不能当结构错误处理；
    - 正文为空 / 仅空白：没有产出任何可用内容，属容量问题。

    该异常归入可重试错误，且重试时**不带**结构反馈。
    """
    metadata = getattr(message, "response_metadata", None) or {}
    finish_reason = metadata.get("finish_reason")
    content = (getattr(message, "content", None) or "").strip()
    if finish_reason == "length" or not content:
        budget = (f"当前 max_tokens={max_tokens}" if max_tokens is not None
                  else "当前 max_tokens 上限")
        raise ModelTruncationException(
            f"模型未产出可用正文（finish_reason={finish_reason!r}）：推理与正文共享 "
            f"max_tokens 预算，疑似推理阶段耗尽预算导致正文被截断。"
            f"请提高输出上限（{budget}）后重试。",
            agent_name=agent_name,
            details={"finish_reason": finish_reason},
        )
