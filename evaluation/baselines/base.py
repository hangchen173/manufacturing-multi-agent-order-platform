"""基线公共底座：模型调用、用量记账、输出解析。

**三条设计约束**（`paper/10_EXPERIMENTS.md` §3）：

1. 基线**不得复用 VEAP 的验证逻辑**（`GroundingVerifier` / 对抗协议 / locator 回灌），
   否则对照无效——那就成了「VEAP 对比 VEAP 的变体」。
2. 基线**必须复用同一套输出模式与评测口径**（`ParsedOrder` + `values_match`），
   否则算出来的准确率不可比。
3. 基线的**抽取提示词与模型必须与 VEAP 抽取器完全一致**——这是**单变量控制**：
   本实验要比较的是「验证媒介」，若基线另写一套提示词，比的就成了提示词质量。

因此这里刻意 import 了 `extractor` 的私有常量 `_TEXT_SYSTEM_PROMPT`。
这是有意为之：**同一个字符串**才是「同一套提示词」的唯一保证；
复制一份到本文件，日后上游一改就悄悄失配，而实验不会报错。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import Config


@dataclass
class BaselineResult:
    """一次基线运行的完整结果。字段与 VEAP 侧对齐，便于同口径比较。"""

    parsed: Optional[Any] = None
    usage: Dict[str, int] = field(
        default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
    calls: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None
    #: 机器可核查证据链。**基线恒为空**——这正是「不可审计」的度量口径，
    #: 由比较脚本统一**测量**，而不是靠论文里断言。
    evidence_chain: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return int(self.usage.get("total_tokens") or 0)

    @property
    def succeeded(self) -> bool:
        return self.parsed is not None


def base_system_prompt() -> str:
    """VEAP 抽取器的系统提示词（原样）。基线沿用，保证单变量控制。"""
    from application.agents.extractor import _TEXT_SYSTEM_PROMPT

    return _TEXT_SYSTEM_PROMPT


def format_instructions() -> str:
    """与 VEAP 完全相同的输出格式说明。"""
    from langchain_core.output_parsers import PydanticOutputParser

    from domain.models import ParsedOrder

    return PydanticOutputParser(pydantic_object=ParsedOrder).get_format_instructions()


def order_user_message(order_text: str) -> str:
    """与 VEAP 抽取路径逐字一致的 user 消息。"""
    return "订单文本如下：\n" + order_text


def parse_order(content: str) -> Any:
    """按 `ParsedOrder` 解析模型输出；失败抛 `ValueError`（调用方须记录为 error）。"""
    from langchain_core.exceptions import OutputParserException
    from langchain_core.output_parsers import PydanticOutputParser
    from pydantic import ValidationError

    from domain.models import ParsedOrder

    parser = PydanticOutputParser(pydantic_object=ParsedOrder)
    try:
        return parser.parse(content)
    except (OutputParserException, ValidationError) as exc:
        detail = " ".join(str(exc).split())
        if len(detail) > 300:
            detail = detail[:300] + "…"
        raise ValueError(f"输出无法通过结构校验: {detail}") from exc


class BaselineLLM:
    """带用量记账的模型客户端。

    角色固定为 ``extractor``：使基线与 VEAP 抽取器命中**同一套模型路由**
    （`Config.model_for`），避免「基线用了别的模型」这种不可比的情况。
    """

    def __init__(
        self,
        config: Config,
        *,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        role: str = "extractor",
    ):
        from langchain_core.callbacks import BaseCallbackHandler
        from langchain_openai import ChatOpenAI

        from application.agents.extractor import EXTRACTION_MAX_TOKENS

        self.usage: Dict[str, int] = {
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0
        }
        self.calls = 0
        owner = self

        class _UsageHandler(BaseCallbackHandler):
            def on_llm_end(self, response, **kwargs):  # noqa: ANN001, D102
                usage = (response.llm_output or {}).get("token_usage") or {}
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    owner.usage[key] += int(usage.get(key) or 0)

        model_config = config.model_for(role)
        self._llm = ChatOpenAI(
            model=model_config.model,
            api_key=model_config.api_key or config.require_model_api_key(),
            base_url=model_config.base_url,
            temperature=temperature,
            max_tokens=max_tokens or EXTRACTION_MAX_TOKENS,
            model_kwargs={"extra_body": model_config.request_body()},
            timeout=60,
            max_retries=0,
            callbacks=[_UsageHandler()],
        )
        self.model_name: str = model_config.model
        self.temperature = temperature

    def snapshot(self) -> Dict[str, int]:
        return dict(self.usage)

    def delta(self, before: Dict[str, int]) -> Dict[str, int]:
        return {key: self.usage[key] - before.get(key, 0) for key in self.usage}

    def complete(self, system: str, user: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        self.calls += 1
        message = self._llm.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        return message.content or ""
