from typing import Any, Dict, Optional
from enum import Enum
import base64
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from core.agents.base_agent import BaseAgent
from core.models import ParsedOrder
from core.constants import ModelType
from core.exceptions import ParserException
from config import Config

class ParserScenario(str, Enum):
    LOGIC_DECISION = "logic_decision"
    GENERAL_PARSING = "general_parsing"
    IMAGE_OCR = "image_ocr"

class ParserAgent(BaseAgent):
    def __init__(self, llm=None, scenario: ParserScenario = ParserScenario.GENERAL_PARSING, config: Optional[Config] = None):
        super().__init__(llm, config)
        self.scenario = scenario
        self.parser = PydanticOutputParser(pydantic_object=ParsedOrder)
        
        if not llm:
            self.llm = self._get_llm_for_scenario(scenario)
    
    def _get_llm_for_scenario(self, scenario: ParserScenario) -> ChatOpenAI:
        model_map = {
            ParserScenario.LOGIC_DECISION: self.config.model.max_model,
            ParserScenario.GENERAL_PARSING: self.config.model.plus_model,
            ParserScenario.IMAGE_OCR: self.config.model.vl_model,
        }
        
        model = model_map.get(scenario, self.config.model.plus_model)
        
        return ChatOpenAI(
            model=model,
            api_key=self.config.model.api_key,
            base_url=self.config.model.base_url,
            temperature=0,
            max_tokens=4096
        )
    
    def set_scenario(self, scenario: ParserScenario):
        self.scenario = scenario
        self.llm = self._get_llm_for_scenario(scenario)
    
    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _create_text_prompt(self):
        return ChatPromptTemplate.from_messages([
            ("system", """你是一位专业的制造业订单解析专家。请从给定的订单文本中提取结构化信息。
{format_instructions}

注意事项：
1. 仔细识别物料名称、规格型号、数量、单位、单价、交期等关键字段
2. 如果某些字段缺失，保持为 null，但尽可能完整提取
3. 解析置信度：如果订单信息清晰完整，置信度设为 0.9-1.0；如果有部分模糊信息，设为 0.7-0.89；如果信息严重不全，设为 0.5-0.69
4. 所有金额和数量使用数字类型"""),
            ("user", "订单文本如下：\n{order_text}")
        ])
    
    def _create_image_message(self, image_path: str, image_type: str = "jpeg", format_instructions: str = ""):
        base64_image = self._encode_image(image_path)
        return [
            {
                "type": "text",
                "text": f"""你是一位专业的制造业订单解析专家。请从这张订单图片中提取结构化信息。
{format_instructions}

注意事项：
1. 仔细识别物料名称、规格型号、数量、单位、单价、交期等关键字段
2. 如果某些字段缺失，保持为 null，但尽可能完整提取
3. 解析置信度：如果订单信息清晰完整，置信度设为 0.9-1.0；如果有部分模糊信息，设为 0.7-0.89；如果信息严重不全，设为 0.5-0.69
4. 所有金额和数量使用数字类型"""
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
                "message": f"解析失败: {str(e)}"
            }
    
    def _process_text(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        order_text = input_data.get("order_text", "")
        if not order_text:
            raise ParserException("订单文本不能为空", agent_name=self.name)
        
        prompt = self._create_text_prompt()
        chain = prompt | self.llm | self.parser
        
        result = chain.invoke({
            "order_text": order_text,
            "format_instructions": self.parser.get_format_instructions()
        })
        
        self.log_info(f"文本订单解析完成，共解析出 {len(result.items)} 项物料")
        
        return {
            "success": True,
            "parsed_order": result,
            "message": "解析成功"
        }
    
    def _process_image(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        image_path = input_data.get("image_path", "")
        if not image_path:
            raise ParserException("图片路径不能为空", agent_name=self.name)
        
        if not Path(image_path).exists():
            raise ParserException(f"图片文件不存在: {image_path}", agent_name=self.name)
        
        image_type = input_data.get("image_type", "jpeg")
        format_instructions = self.parser.get_format_instructions()
        
        messages = [
            HumanMessage(content=self._create_image_message(image_path, image_type, format_instructions))
        ]
        
        prompt = ChatPromptTemplate.from_messages([
            ("placeholder", "{messages}")
        ])
        
        chain = prompt | self.llm | self.parser
        
        result = chain.invoke({
            "messages": messages
        })
        
        self.log_info(f"图片订单解析完成，共解析出 {len(result.items)} 项物料")
        
        return {
            "success": True,
            "parsed_order": result,
            "message": "解析成功"
        }
