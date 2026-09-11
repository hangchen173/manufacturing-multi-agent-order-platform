from typing import Any, Callable, Dict, List, NamedTuple, Optional
from enum import Enum
import base64
import hashlib
import re
from pathlib import Path

from application.agents.base_agent import BaseAgent
from config import Config
from domain.exceptions import ParserException
from domain.models import ParsedOrder, ParsingIssue

_AMOUNT_TOLERANCE = 0.01
_MAX_ERROR_DETAIL = 500

_CORRECTION_INSTRUCTION = """上一次抽取结果在自检中未通过，存在以下问题：
{feedback}

请只针对上述问题重新核对原订单，逐项修正后重新输出完整的结构化结果；未被指出问题的字段必须与上一次保持一致，不要改动其他内容。"""

_TEXT_SYSTEM_PROMPT = """你是一位专业的制造业订单解析专家。请从给定的订单文本中提取结构化信息。
{format_instructions}

注意事项：
1. 仔细识别物料名称、规格型号、数量、单位、单价、交期等关键字段
2. 如果某些字段缺失，保持为 null，但尽可能完整提取
3. 解析置信度：如果订单信息清晰完整，置信度设为 0.9-1.0；如果有部分模糊信息，设为 0.7-0.89；如果信息严重不全，设为 0.5-0.69
4. 所有金额和数量使用数字类型"""

_IMAGE_SYSTEM_PROMPT = """你是一位专业的制造业订单解析专家。请从这张订单图片中提取结构化信息。
{format_instructions}

注意事项：
1. 仔细识别物料名称、规格型号、数量、单位、单价、交期等关键字段
2. 如果某些字段缺失，保持为 null，但尽可能完整提取
3. 解析置信度：如果订单信息清晰完整，置信度设为 0.9-1.0；如果有部分模糊信息，设为 0.7-0.89；如果信息严重不全，设为 0.5-0.69
4. 所有金额和数量使用数字类型"""


def prompt_fingerprint() -> str:
    """返回解析提示词的指纹，用于评测运行身份校验。"""
    payload = "\n\n".join(
        (_TEXT_SYSTEM_PROMPT, _IMAGE_SYSTEM_PROMPT, _CORRECTION_INSTRUCTION)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()



class ParserScenario(str, Enum):
    GENERAL_PARSING = "general_parsing"
    IMAGE_OCR = "image_ocr"


class ExtractionProblem(NamedTuple):
    item_index: Optional[int]
    description: str


class ParserAgent(BaseAgent):
    MAX_PARSING_ATTEMPTS = 2

    def __init__(self, llm=None, scenario: ParserScenario = ParserScenario.GENERAL_PARSING, config: Optional[Config] = None):
        super().__init__(llm, config)
        self.scenario = scenario
        self.parser = None
        self.last_self_correction: Optional[Dict[str, Any]] = None
        self.last_usage: Dict[str, int] = self._empty_usage()

    @staticmethod
    def _empty_usage() -> Dict[str, int]:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _record_usage(self, message: Any) -> None:
        usage = getattr(message, "usage_metadata", None) or {}
        self.last_usage["prompt_tokens"] += int(usage.get("input_tokens") or 0)
        self.last_usage["completion_tokens"] += int(usage.get("output_tokens") or 0)
        self.last_usage["total_tokens"] += int(usage.get("total_tokens") or 0)
    
    def _get_output_parser(self):
        if self.parser is None:
            from langchain_core.output_parsers import PydanticOutputParser

            self.parser = PydanticOutputParser(pydantic_object=ParsedOrder)
        return self.parser
    
    def _get_llm_for_scenario(self, scenario: ParserScenario):
        from langchain_openai import ChatOpenAI
        
        return ChatOpenAI(
            model=self.config.model.model,
            api_key=self.config.require_model_api_key(),
            base_url=self.config.model.base_url,
            temperature=0,
            max_tokens=4096
        )

    def _get_llm(self):
        if self.llm is None:
            self.llm = self._get_llm_for_scenario(self.scenario)
        return self.llm
    
    def set_scenario(self, scenario: ParserScenario):
        self.scenario = scenario
        self.llm = None
    
    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _create_text_prompt(self, feedback: Optional[str] = None):
        from langchain_core.prompts import ChatPromptTemplate

        messages = [
            ("system", _TEXT_SYSTEM_PROMPT),
            ("user", "订单文本如下：\n{order_text}")
        ]
        if feedback:
            messages.append(("user", _CORRECTION_INSTRUCTION))
        return ChatPromptTemplate.from_messages(messages)
    
    def _create_image_message(self, image_path: str, image_type: str = "jpeg", format_instructions: str = ""):
        base64_image = self._encode_image(image_path)
        return [
            {
                "type": "text",
                "text": _IMAGE_SYSTEM_PROMPT.format(format_instructions=format_instructions)
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/{image_type};base64,{base64_image}"
                }
            }
        ]
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.log_info(f"开始解析订单，场景: {self.scenario}")
        self.last_self_correction = None
        self.last_usage = self._empty_usage()
        
        try:
            if self.scenario == ParserScenario.IMAGE_OCR:
                return self._process_image(input_data)
            else:
                return self._process_text(input_data)
        except Exception as e:
            self.log_error(f"解析失败: {str(e)}")
            return {
                "success": False,
                "parsed_order": None,
                "message": f"解析失败: {str(e)}",
                "usage": dict(self.last_usage),
            }
    
    def _process_text(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        order_text = input_data.get("order_text", "")
        if not order_text:
            raise ParserException("订单文本不能为空", agent_name=self.name)
        
        parsed_order = self._parse_with_self_correction(
            source_text=order_text,
            extract=lambda feedback: self._extract_text(order_text, feedback),
        )
        
        self.log_info(f"文本订单解析完成，共解析出 {len(parsed_order.items)} 项物料")
        
        return {
            "success": True,
            "parsed_order": parsed_order,
            "message": "解析成功",
            "usage": dict(self.last_usage),
        }
    
    def _extract_text(self, order_text: str, feedback: Optional[str]) -> ParsedOrder:
        parser = self._get_output_parser()
        prompt = self._create_text_prompt(feedback)

        payload: Dict[str, Any] = {
            "order_text": order_text,
            "format_instructions": parser.get_format_instructions(),
        }
        if feedback:
            payload["feedback"] = feedback

        message = (prompt | self._get_llm()).invoke(payload)
        self._record_usage(message)
        return parser.parse(message.content)
    
    def _process_image(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        image_path = input_data.get("image_path", "")
        if not image_path:
            raise ParserException("图片路径不能为空", agent_name=self.name)
        
        if not Path(image_path).exists():
            raise ParserException(f"图片文件不存在: {image_path}", agent_name=self.name)
        
        image_type = input_data.get("image_type", "jpeg")
        
        parsed_order = self._parse_with_self_correction(
            source_text="",
            extract=lambda feedback: self._extract_image(image_path, image_type, feedback),
        )
        
        self.log_info(f"图片订单解析完成，共解析出 {len(parsed_order.items)} 项物料")
        
        return {
            "success": True,
            "parsed_order": parsed_order,
            "message": "解析成功",
            "usage": dict(self.last_usage),
        }
    
    def _extract_image(self, image_path: str, image_type: str, feedback: Optional[str]) -> ParsedOrder:
        from langchain_core.messages import HumanMessage

        parser = self._get_output_parser()
        messages = [
            HumanMessage(
                content=self._create_image_message(
                    image_path, image_type, parser.get_format_instructions()
                )
            )
        ]
        if feedback:
            messages.append(HumanMessage(content=_CORRECTION_INSTRUCTION.format(feedback=feedback)))

        message = self._get_llm().invoke(messages)
        self._record_usage(message)
        return parser.parse(message.content)
    
    def _parse_with_self_correction(
        self,
        source_text: str,
        extract: Callable[[Optional[str]], ParsedOrder],
    ) -> ParsedOrder:
        parsed_order, problems = self._try_extract(extract, None, source_text)
        if parsed_order is not None and not problems:
            return parsed_order
        
        initial_problems = list(problems)
        attempt = 1
        while problems and attempt < self.MAX_PARSING_ATTEMPTS:
            attempt += 1
            feedback = "\n".join(f"- {problem.description}" for problem in problems)
            self.log_warning(f"解析自检发现 {len(problems)} 个问题，发起第 {attempt} 次抽取")
            parsed_order, problems = self._try_extract(extract, feedback, source_text)
        
        self.last_self_correction = {
            "attempts": attempt,
            "initial_problems": [problem.description for problem in initial_problems],
            "remaining_problems": [problem.description for problem in problems],
            "resolved": not problems,
        }
        
        if parsed_order is None:
            raise ParserException(
                "；".join(problem.description for problem in problems),
                agent_name=self.name,
            )
        
        if problems:
            self.log_warning(f"二次抽取后仍有 {len(problems)} 个问题未解决，交人工确认")
            parsed_order = self._flag_unresolved(parsed_order, problems)
        
        return parsed_order
    
    def _try_extract(
        self,
        extract: Callable[[Optional[str]], ParsedOrder],
        feedback: Optional[str],
        source_text: str,
    ) -> tuple[Optional[ParsedOrder], List[ExtractionProblem]]:
        try:
            parsed_order = extract(feedback)
        except Exception as exc:
            self.log_warning(f"抽取结果未通过结构校验：{exc}")
            return None, [ExtractionProblem(None, self._describe_extraction_error(exc))]
        
        return parsed_order, self._detect_extraction_problems(parsed_order, source_text)
    
    @staticmethod
    def _describe_extraction_error(exc: Exception) -> str:
        detail = " ".join(str(exc).split())
        if len(detail) > _MAX_ERROR_DETAIL:
            detail = detail[:_MAX_ERROR_DETAIL] + "…"
        return f"上一次输出无法通过结构校验，必须修正这些字段后重新输出：{detail}"
    
    def _detect_extraction_problems(
        self, parsed_order: ParsedOrder, source_text: str
    ) -> List[ExtractionProblem]:
        if not parsed_order.items:
            return [ExtractionProblem(None, "未从订单中解析出任何物料明细")]
        
        problems: List[ExtractionProblem] = []
        
        for index, item in enumerate(parsed_order.items):
            if not (item.material_name or "").strip():
                problems.append(ExtractionProblem(index, f"第 {index + 1} 行物料名称缺失"))
            if not (item.specification or "").strip():
                problems.append(ExtractionProblem(index, f"第 {index + 1} 行规格型号缺失"))
        
        expected_rows = self._count_source_rows(source_text)
        if expected_rows is not None and expected_rows != len(parsed_order.items):
            problems.append(ExtractionProblem(
                None,
                f"明细数量不一致：原文共 {expected_rows} 行明细，解析出 {len(parsed_order.items)} 行",
            ))
        
        if source_text:
            normalized_source = self._normalize_text(source_text)
            for index, item in enumerate(parsed_order.items):
                normalized_name = self._normalize_text(item.material_name or "")
                if normalized_name and normalized_name not in normalized_source:
                    problems.append(ExtractionProblem(
                        index,
                        f"第 {index + 1} 行物料名称「{item.material_name}」无法在原文中定位",
                    ))
        
        amount_problem = self._check_amount_consistency(parsed_order)
        if amount_problem is not None:
            problems.append(amount_problem)
        
        return problems
    
    @staticmethod
    def _count_source_rows(source_text: str) -> Optional[int]:
        if not source_text:
            return None
        rows = sum(
            1 for line in source_text.splitlines() if re.match(r"^\s*\d+\s+\S", line)
        )
        return rows or None
    
    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", "", value).lower()
    
    def _check_amount_consistency(self, parsed_order: ParsedOrder) -> Optional[ExtractionProblem]:
        total_amount = parsed_order.total_amount
        if total_amount is None:
            return None
        
        items = parsed_order.items
        if any(item.quantity is None or item.unit_price is None for item in items):
            # 条件不足时不做金额核验；缺失字段由下游风控标记，不按零参与换算
            return None

        computed = sum(item.quantity * item.unit_price for item in items)
        tolerance = max(1.0, abs(total_amount) * _AMOUNT_TOLERANCE)
        if abs(computed - total_amount) > tolerance:
            return ExtractionProblem(
                None,
                f"数量、单价、金额关系不成立：明细合计 {computed:.2f} 与订单总额 {total_amount:.2f} 不一致",
            )
        return None
    
    def _flag_unresolved(
        self, parsed_order: ParsedOrder, problems: List[ExtractionProblem]
    ) -> ParsedOrder:
        parsed_order.parsing_issues = [
            ParsingIssue(item_index=problem.item_index, description=problem.description)
            for problem in problems
        ]

        unresolved_confidence = max(0.0, self.config.risk.confidence_threshold - 0.1)
        indexes = {problem.item_index for problem in problems}
        targets = range(len(parsed_order.items)) if None in indexes else indexes
        
        for index in targets:
            if 0 <= index < len(parsed_order.items):
                parsed_order.items[index].confidence_score = unresolved_confidence
        
        parsed_order.parsing_confidence = min(parsed_order.parsing_confidence, unresolved_confidence)
        return parsed_order
