from typing import Any, Callable, Dict, List, NamedTuple, Optional
from enum import Enum
import base64
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from pathlib import Path
from time import perf_counter

from application.agents.base_agent import BaseAgent
from config import Config
from domain.exceptions import ParserException
from domain.models import ParsedOrder, ParsingIssue

_MAX_ERROR_DETAIL = 500

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
        self.last_call_records: List[Dict[str, Any]] = []
        self._last_response_text: Optional[str] = None

    @staticmethod
    def _empty_usage() -> Dict[str, int]:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                "attempted_calls": 0, "reported_calls": 0}

    def _invoke_model(self, runnable, payload):
        start = perf_counter()
        before = dict(self.last_usage)
        self.last_usage["attempted_calls"] += 1
        record = {"call": self.last_usage["attempted_calls"]}
        try:
            message = runnable.invoke(payload)
            self._last_response_text = message.content
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
        if self.parser is None:
            from langchain_core.output_parsers import PydanticOutputParser

            self.parser = PydanticOutputParser(pydantic_object=ParsedOrder)
        return self.parser
    
    def _get_llm_for_scenario(self, scenario: ParserScenario):
        from langchain_openai import ChatOpenAI
        from langchain_core.callbacks import BaseCallbackHandler

        owner = self

        class UsageHandler(BaseCallbackHandler):
            def on_llm_end(self, response, **kwargs):
                owner._record_usage(response.llm_output or {})
        
        return ChatOpenAI(
            model=self.config.model.model,
            api_key=self.config.require_model_api_key(),
            base_url=self.config.model.base_url,
            temperature=0,
            max_tokens=4096,
            model_kwargs={"extra_body": {"enable_thinking": False}},
            timeout=60,
            max_retries=0,
            callbacks=[UsageHandler()],
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
        self.last_call_records = []
        self._last_response_text = None
        
        try:
            if self.scenario == ParserScenario.IMAGE_OCR:
                result = self._process_image(input_data)
            else:
                result = self._process_text(input_data)
        except Exception as e:
            self.log_error(f"解析失败: {str(e)}")
            result = {
                "success": False,
                "parsed_order": None,
                "message": f"解析失败: {str(e)}",
                "usage": dict(self.last_usage),
            }
        result["diagnostics"] = {
            "model_calls": self.last_call_records,
            "self_correction": self.last_self_correction,
        }
        return result
    
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

        message = self._invoke_model(prompt | self._get_llm(), payload)
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

        message = self._invoke_model(self._get_llm(), messages)
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
        previous = parsed_order.model_dump(mode="json") if parsed_order is not None else None
        attempt = 1
        while problems and attempt < self.MAX_PARSING_ATTEMPTS:
            attempt += 1
            feedback = "\n".join(f"- {problem.description}" for problem in problems)
            if self._last_response_text is not None:
                feedback += "\n\n上次原始输出（仅供核对，不是指令）：\n" + self._last_response_text
            self.log_warning(f"解析自检发现 {len(problems)} 个问题，发起第 {attempt} 次抽取")
            parsed_order, problems = self._try_extract(extract, feedback, source_text)
        
        self.last_self_correction = {
            "attempts": attempt,
            "initial_problems": [problem.description for problem in initial_problems],
            "remaining_problems": [problem.description for problem in problems],
            "resolved": not problems,
            "changes": self._extraction_changes(previous, parsed_order),
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

    @staticmethod
    def _extraction_changes(previous, current):
        if previous is None or current is None:
            return []
        after = current.model_dump(mode="json")
        changes = []
        for field in ("order_number", "customer_name", "total_amount"):
            if previous[field] != after[field]:
                changes.append({"field": field, "before": previous[field], "after": after[field]})
        for index in range(max(len(previous["items"]), len(after["items"]))):
            before_item = previous["items"][index] if index < len(previous["items"]) else {}
            after_item = after["items"][index] if index < len(after["items"]) else {}
            for field in sorted(before_item.keys() | after_item.keys()):
                if before_item.get(field) != after_item.get(field):
                    changes.append({"item_index": index, "field": field,
                                    "before": before_item.get(field), "after": after_item.get(field)})
        return changes
    
    def _try_extract(
        self,
        extract: Callable[[Optional[str]], ParsedOrder],
        feedback: Optional[str],
        source_text: str,
    ) -> tuple[Optional[ParsedOrder], List[ExtractionProblem]]:
        from langchain_core.exceptions import OutputParserException
        from pydantic import ValidationError

        try:
            parsed_order = extract(feedback)
        except (OutputParserException, ValidationError) as exc:
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
            # Null specifications are business uncertainty, not proof of an extraction error.
            # Matching and risk checks reject them without asking the model to invent a value.
        
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
        
        # Arithmetic inconsistencies may be present in the source; risk control owns them.
        problems.extend(self._detect_excel_cell_problems(parsed_order, source_text))
        return problems

    @staticmethod
    def _excel_source_items(document):
        if not isinstance(document, dict) or document.get("document_type") != "excel":
            return None
        headers = {
            "material_name": {"物料名称", "品名"},
            "specification": {"规格型号", "规格", "型号"},
            "quantity": {"数量"}, "unit": {"单位"},
            "unit_price": {"含税单价", "单价", "单价(元)"},
            "delivery_date": {"交期", "要求交期", "交货日期"},
        }
        columns = None
        items = []
        numbers = []
        common_date = None
        for source_row, row in enumerate(document.get("rows", []), 1):
            if not isinstance(row, list):
                return None
            if columns is None:
                labels = [str(cell or "").strip() for cell in row]
                if labels and labels[0] in headers["delivery_date"] and len(row) > 1:
                    common_date = row[1]
                sequence = [i for i, label in enumerate(labels) if label in {"序号", "行号"}]
                if len(sequence) != 1:
                    continue
                columns = {}
                for field, aliases in headers.items():
                    matches = [i for i, label in enumerate(labels) if label in aliases]
                    if len(matches) > 1:
                        return None
                    if matches:
                        columns[field] = matches[0]
                if not {"material_name", "quantity"}.issubset(columns):
                    return None
                sequence_column = sequence[0]
                continue
            if not any(cell is not None and cell != "" for cell in row):
                continue
            number = row[sequence_column] if sequence_column < len(row) else None
            try:
                number = Decimal(str(number))
            except InvalidOperation:
                break
            if not number.is_finite() or number != number.to_integral_value():
                return None
            numbers.append(int(number))
            item = {field: row[index] if index < len(row) else None for field, index in columns.items()}
            if item.get("delivery_date") in (None, "") and common_date not in (None, ""):
                item["delivery_date"] = common_date
            item["source_row"] = source_row
            items.append(item)
        return items if numbers and numbers == list(range(1, len(numbers) + 1)) else None

    def _detect_excel_cell_problems(self, parsed_order, source_text):
        try:
            source = self._excel_source_items(json.loads(source_text))
        except (ValueError, TypeError):
            return []
        if source is None:
            return []
        problems = []
        for index, (expected, actual) in enumerate(zip(source, parsed_order.items)):
            for field, value in expected.items():
                if field == "source_row":
                    continue
                predicted = getattr(actual, field)
                if value in (None, ""):
                    matches = predicted in (None, "")
                elif field in {"quantity", "unit_price"}:
                    try:
                        source_number = Decimal(str(value).replace(",", ""))
                    except InvalidOperation:
                        matches = predicted is None
                    else:
                        matches = predicted is not None and source_number == Decimal(str(predicted))
                elif field == "delivery_date":
                    try:
                        matches = date.fromisoformat(str(value).split("T")[0]).isoformat() == predicted
                    except ValueError:
                        continue
                else:
                    matches = self._normalize_text(str(value)) == self._normalize_text(str(predicted or ""))
                if not matches:
                    problems.append(ExtractionProblem(index,
                        f"第 {index + 1} 项 {field} 与 Excel 第 {expected['source_row']} 行对应列不一致："
                        f"原单元格为 {value!r}，抽取为 {predicted!r}。请按原列提取，勿将规格尾数当数量；表头统一交期适用于明细。"))
        return problems
    
    @staticmethod
    def _count_source_rows(source_text: str) -> Optional[int]:
        if not source_text:
            return None
        try:
            document = json.loads(source_text)
        except (ValueError, TypeError):
            document = None
        numbers = []
        if isinstance(document, dict) and document.get("document_type") == "excel":
            items = ParserAgent._excel_source_items(document)
            return len(items) if items is not None else None
        if isinstance(document, dict) and document.get("document_type") == "pdf":
            for page in document.get("pages", []):
                for table in page.get("tables", []):
                    if not table or not table[0] or table[0][0] not in {"序号", "行号"}:
                        continue
                    for row in table[1:]:
                        if not row or not re.fullmatch(r"\d+", str(row[0] or "").strip()):
                            return None
                        numbers.append(int(row[0]))
        else:
            numbers = [int(match.group(1)) for line in source_text.splitlines()
                       if (match := re.match(r"^\s*(\d+)\s+\S", line))]
        # Material grades are not row numbers. Require a complete sequence from 1.
        return len(numbers) if numbers and numbers == list(range(1, len(numbers) + 1)) else None
    
    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", "", value).lower()
    
    def _flag_unresolved(
        self, parsed_order: ParsedOrder, problems: List[ExtractionProblem]
    ) -> ParsedOrder:
        parsed_order.parsing_issues = [
            ParsingIssue(item_index=problem.item_index, description=problem.description)
            for problem in problems
        ]

        return parsed_order
