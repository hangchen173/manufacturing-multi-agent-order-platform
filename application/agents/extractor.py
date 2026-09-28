"""抽取者 Agent（生产者）。

把非结构化订单文档转成结构化主张（PROPOSE）。它是**唯一**对文档正文调用模型的
业务角色（ReviewAssistant 是唯一的另一个模型调用点）。

它只负责“抽”，不负责“验”：`_parse_with_self_correction` 的自我循环已删除，
改由 GroundingVerifier + Supervisor 的对抗协议接管。
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, List, Optional

from application.agents.base_agent import CollaborativeAgent
from application.agents.source_map import find_item_locators
from application.protocol.model_output import assert_not_truncated
from domain.agent_roles import AgentRole
from domain.exceptions import ExtractionSchemaException, ParserException
from domain.messages import AgentMessage, Evidence, Performative
from domain.models import ParsedOrder
from domain.tasks import Task

MAX_ERROR_DETAIL = 500

#: 推理与正文共享同一个 max_tokens 预算，必须给「思考 + 完整 JSON」留足空间，
#: 否则复杂多行订单会在推理阶段耗尽预算、正文返回空串。
EXTRACTION_MAX_TOKENS = 16384

_CORRECTION_INSTRUCTION = """上一次抽取结果在自检中未通过，存在以下问题：
{feedback}

请对照原订单与上次输出核对上述问题，重新输出完整结果。没有证据的字段保持 null，禁止为了通过校验编造规格、数量、价格或金额。若原订单本身存在矛盾，忠实保留原值交人工审核。其他正确字段保持不变。"""

_TEXT_SYSTEM_PROMPT = """你是一位专业的制造业订单解析专家。请从给定的订单文本中提取结构化信息。
{format_instructions}

注意事项：
1. 仔细识别物料名称、规格型号、数量、单位、单价、交期等关键字段
2. 如果某些字段缺失，保持为 null，但尽可能完整提取
3. 解析置信度：如果订单信息清晰完整，置信度设为 0.9-1.0；如果有部分模糊信息，设为 0.7-0.89；如果信息严重不全，设为 0.5-0.69
4. 所有金额和数量使用数字类型
5. 有明确品名/物料名称与规格/型号列或标签时，逐字段忠实保留原值；名称里即使含尺寸、型号或俗称，也不得拆出挪到规格字段，不要改写为标准物料名。只提取明确给出的总金额，不自行计算补填。"""

_IMAGE_SYSTEM_PROMPT = """你是一位专业的制造业订单解析专家。请从这张订单图片中提取结构化信息。
{format_instructions}

注意事项：
1. 仔细识别物料名称、规格型号、数量、单位、单价、交期等关键字段
2. 如果某些字段缺失，保持为 null，但尽可能完整提取
3. 解析置信度：如果订单信息清晰完整，置信度设为 0.9-1.0；如果有部分模糊信息，设为 0.7-0.89；如果信息严重不全，设为 0.5-0.69
4. 所有金额和数量使用数字类型
5. 有明确品名/物料名称与规格/型号列或标签时，逐字段忠实保留原值；名称里即使含尺寸、型号或俗称，也不得拆出挪到规格字段，不要改写为标准物料名。只提取明确给出的总金额，不自行计算补填。"""


def prompt_fingerprint() -> str:
    """返回解析提示词的指纹，用于评测运行身份校验。"""
    payload = "\n\n".join(
        (_TEXT_SYSTEM_PROMPT, _IMAGE_SYSTEM_PROMPT, _CORRECTION_INSTRUCTION)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Extractor(CollaborativeAgent):
    """一次 handle() 只做一次抽取。重试与反馈由 Supervisor 编排。"""

    role = AgentRole.EXTRACTOR
    MAX_EXTRACTION_ATTEMPTS = 2

    def __init__(self, llm: Optional[Any] = None, blackboard: Any = None, budget: Any = None,
                 config: Any = None):
        super().__init__(blackboard, budget, config)
        self.llm = llm
        self.last_usage: Dict[str, int] = self._empty_usage()
        self.last_call_records: List[Dict[str, Any]] = []
        self._last_response_text: Optional[str] = None
        #: 全局调用序号，仅用于让诊断记录里的 call 编号保持单调可读。
        self._call_seq = 0

    @staticmethod
    def _empty_usage() -> Dict[str, int]:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                "attempted_calls": 0, "reported_calls": 0}

    # ------------------------------------------------------------- model plumbing
    def _invoke_model(self, runnable, payload):
        start = perf_counter()
        before = dict(self.last_usage)
        self.last_usage["attempted_calls"] += 1
        self._call_seq += 1
        record = {"call": self._call_seq}
        try:
            message = runnable.invoke(payload)
            self._last_response_text = message.content
            assert_not_truncated(message, agent_name="Extractor",
                                 max_tokens=EXTRACTION_MAX_TOKENS)
            return message
        except Exception as exc:
            record["error_type"] = type(exc).__name__
            raise
        finally:
            record["latency_ms"] = round((perf_counter() - start) * 1000, 2)
            record["usage_reported"] = self.last_usage["reported_calls"] > before["reported_calls"]
            record["total_tokens"] = (
                self.last_usage["total_tokens"] - before["total_tokens"]
                if record["usage_reported"] else None
            )
            self.last_call_records.append(record)

    def _record_usage(self, output: Dict[str, Any]) -> None:
        usage = output.get("token_usage") or {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            self.last_usage[key] += int(usage.get(key) or 0)
        self.last_usage["reported_calls"] = self.last_usage.get("reported_calls", 0) + int(bool(usage))

    def _get_output_parser(self):
        from langchain_core.output_parsers import PydanticOutputParser

        return PydanticOutputParser(pydantic_object=ParsedOrder)

    def _get_llm(self):
        if self.llm is None:
            from langchain_openai import ChatOpenAI
            from langchain_core.callbacks import BaseCallbackHandler

            owner = self

            class UsageHandler(BaseCallbackHandler):
                def on_llm_end(self, response, **kwargs):
                    owner._record_usage(response.llm_output or {})

            # 角色级模型路由：Extractor 可与其他角色用不同模型（见 Config.model_for）。
            model_config = self.config.model_for(self.role.value)
            self.llm = ChatOpenAI(
                model=model_config.model,
                api_key=model_config.api_key or self.config.require_model_api_key(),
                base_url=model_config.base_url,
                temperature=0,
                max_tokens=EXTRACTION_MAX_TOKENS,
                model_kwargs={"extra_body": model_config.request_body()},
                timeout=60,
                max_retries=0,
                callbacks=[UsageHandler()],
            )
        return self.llm

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def _create_text_prompt(self, feedback: Optional[str] = None):
        from langchain_core.prompts import ChatPromptTemplate

        messages = [
            ("system", _TEXT_SYSTEM_PROMPT),
            ("user", "订单文本如下：\n{order_text}"),
        ]
        if feedback:
            messages.append(("user", _CORRECTION_INSTRUCTION))
        return ChatPromptTemplate.from_messages(messages)

    def _create_image_message(self, image_path: str, image_type: str = "jpeg",
                              format_instructions: str = "") -> List[Dict[str, Any]]:
        base64_image = self._encode_image(image_path)
        return [
            {"type": "text",
             "text": _IMAGE_SYSTEM_PROMPT.format(format_instructions=format_instructions)},
            {"type": "image_url",
             "image_url": {"url": f"data:image/{image_type};base64,{base64_image}"}},
        ]

    # ------------------------------------------------------------------ extraction
    def extract_text(self, order_text: str, feedback: Optional[str] = None) -> ParsedOrder:
        parser = self._get_output_parser()
        prompt = self._create_text_prompt(feedback)
        payload: Dict[str, Any] = {
            "order_text": order_text,
            "format_instructions": parser.get_format_instructions(),
        }
        if feedback:
            payload["feedback"] = feedback
        message = self._invoke_model(prompt | self._get_llm(), payload)
        return self._parse_output(parser, message.content)

    def extract_image(self, image_path: str, image_type: str, feedback: Optional[str] = None) -> ParsedOrder:
        from langchain_core.messages import HumanMessage

        parser = self._get_output_parser()
        messages = [HumanMessage(content=self._create_image_message(
            image_path, image_type, parser.get_format_instructions()
        ))]
        if feedback:
            messages.append(HumanMessage(content=_CORRECTION_INSTRUCTION.format(feedback=feedback)))
        message = self._invoke_model(self._get_llm(), messages)
        return self._parse_output(parser, message.content)

    @staticmethod
    def _parse_output(parser, content: str) -> ParsedOrder:
        from langchain_core.exceptions import OutputParserException
        from pydantic import ValidationError

        try:
            return parser.parse(content)
        except (OutputParserException, ValidationError) as exc:
            detail = " ".join(str(exc).split())
            if len(detail) > MAX_ERROR_DETAIL:
                detail = detail[:MAX_ERROR_DETAIL] + "…"
            raise ExtractionSchemaException(
                f"上一次输出无法通过结构校验，必须修正这些字段后重新输出：{detail}",
                agent_name="Extractor",
            ) from exc

    # ------------------------------------------------------------------ task entry
    def handle(self, task: Task) -> List[AgentMessage]:
        # 每次 handle 只统计本次调用的用量：INFORM 携带的是「本次」快照，
        # 由 Supervisor 汇总各条 INFORM 得到订单级总量，避免累计快照被重复累加。
        self.last_usage = self._empty_usage()
        self.last_call_records = []

        view = self.read_slice(task)
        region = view.get("region")
        feedback = view.get("feedback")
        document_ir = view.get("document_ir") or {}
        image_path = task.slice_key.get("image_path")

        # 扫描页：StructureScout 已把该页路由为图像解析，这里取加载层渲染好的图片。
        if not image_path and isinstance(region, dict) and region.get("mode") == "image":
            image_path = self._page_image_path(document_ir, region)

        if image_path:
            if not Path(image_path).exists():
                raise ParserException(f"图片文件不存在: {image_path}", agent_name=self.name)
            parsed = self.extract_image(image_path, task.slice_key.get("image_type", "jpeg"), feedback)
        else:
            source = self.region_source(document_ir, region)
            if not source.strip():
                raise ParserException("订单文本不能为空", agent_name=self.name)
            parsed = self.extract_text(source, feedback)

        self.log_info(f"抽取完成，共 {len(parsed.items)} 项物料（region={region}）")
        return self._to_messages(task, parsed, document_ir, region)

    @staticmethod
    def region_source(document_ir: Dict[str, Any], region: Optional[Dict[str, Any]]) -> str:
        if not document_ir:
            return ""
        document_type = document_ir.get("document_type")
        if document_type == "text":
            return document_ir.get("text") or ""
        if not region:
            return json.dumps(document_ir, ensure_ascii=False)
        kind = region.get("kind")
        if kind == "sheet":
            sheets = [sheet for sheet in document_ir.get("sheets", [])
                      if sheet.get("name") == region.get("name")]
            return json.dumps({"document_type": "excel", "sheets": sheets}, ensure_ascii=False)
        if kind == "page":
            pages = [page for page in document_ir.get("pages", [])
                     if page.get("page_number") == region.get("page_number")]
            return json.dumps({"document_type": "pdf", "pages": pages}, ensure_ascii=False)
        if kind == "pages":
            wanted = set(region.get("page_numbers") or [])
            pages = [page for page in document_ir.get("pages", [])
                     if page.get("page_number") in wanted]
            return json.dumps({"document_type": "pdf", "pages": pages}, ensure_ascii=False)
        return json.dumps(document_ir, ensure_ascii=False)

    @staticmethod
    def _page_image_path(document_ir: Dict[str, Any], region: Dict[str, Any]) -> Optional[str]:
        """从（已收窄的）文档 IR 中取出该页渲染后的图片路径。"""
        number = region.get("page_number")
        for page in document_ir.get("pages", []):
            if page.get("page_number") == number:
                return page.get("image_path")
        return None

    def _to_messages(self, task: Task, parsed: ParsedOrder,
                     document_ir: Dict[str, Any], region: Optional[Dict[str, Any]]) -> List[AgentMessage]:
        locators = find_item_locators(document_ir, region)
        payload = parsed.model_dump(mode="json")

        messages: List[AgentMessage] = [
            self.emit(
                task,
                Performative.PROPOSE,
                subject={"claim_subject": "order"},
                payload={
                    "claim": {
                        "subject": "order",
                        "value": {
                            "order_number": parsed.order_number,
                            "customer_name": parsed.customer_name,
                            "total_amount": parsed.total_amount,
                        },
                        "basis": "llm_structured_extraction",
                        "confidence": parsed.parsing_confidence,
                    },
                    "parsed_order": payload,
                    "region": region,
                },
            )
        ]

        for index, item in enumerate(parsed.items):
            evidence: List[Evidence] = []
            if index < len(locators):
                locator = locators[index]
                evidence.append(Evidence(
                    kind="cell_ref",
                    locator={"kind": "cell", "sheet": locator["sheet"], "row": locator["row"],
                             "columns": locator["columns"]},
                    value=locator["values"],
                    reproducible=True,
                    note=f"item[{index}] 定位到工作表 {locator['sheet']} 第 {locator['row']} 行",
                ))
            messages.append(self.claim_message(
                task,
                subject=f"item[{index}]",
                value=item.model_dump(mode="json"),
                basis="llm_structured_extraction",
                evidence=evidence,
                confidence=item.confidence_score,
            ))

        messages.append(self.emit(
            task,
            Performative.INFORM,
            payload={
                "usage": dict(self.last_usage),
                "model_calls": list(self.last_call_records),
                "region": region,
                "item_count": len(parsed.items),
            },
        ))
        return messages
