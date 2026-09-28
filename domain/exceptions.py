from typing import Optional, Any

class AgentBaseException(Exception):
    def __init__(self, message: str, agent_name: Optional[str] = None, details: Optional[Any] = None):
        self.message = message
        self.agent_name = agent_name
        self.details = details
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.agent_name:
            return f"[{self.agent_name}] {self.message}"
        return self.message

class ParserException(AgentBaseException):
    pass


class ExtractionSchemaException(AgentBaseException):
    """模型输出未通过结构校验。属有界可重试错误：带反证/错误详情重抽一次。"""


class ExtractionGroundednessException(AgentBaseException):
    """抽取结果与原文无法对上。属不可重试错误：需人工或重新提交文档。"""


class ModelTruncationException(AgentBaseException):
    """模型输出被 max_tokens 截断（或返回空内容），未产出任何可用正文。

    推理型模型把「思考」与「正文」计入同一个 max_tokens 预算：预算被思考耗尽时，
    API 仍返回 HTTP 200，但 finish_reason='length' 且 content 为空串。
    这属于**容量不足**而非**结构错误**——必须与 ExtractionSchemaException 区分：
    结构错误要带字段级反馈重抽，截断重抽若带结构反馈会误导模型，还会掩盖真实失败原因。
    归类为可重试（见 RETRYABLE_ERRORS），重试时**不带**结构反馈。
    """


class MatchingException(AgentBaseException):
    pass


class RiskControlException(AgentBaseException):
    pass


class OrchestratorException(AgentBaseException):
    pass


class SupervisorException(AgentBaseException):
    pass

class DocumentLoadException(AgentBaseException):
    pass

class VectorStoreException(AgentBaseException):
    pass

class ConfigurationException(Exception):
    pass

class ValidationException(Exception):
    def __init__(self, field: str, message: str, value: Optional[Any] = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"Validation error for field '{field}': {message}")

class OrderNotFoundException(Exception):
    def __init__(self, message: str, details: Optional[Any] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

class OrderManagerException(Exception):
    def __init__(self, message: str, details: Optional[Any] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

class InvalidOrderStatusException(Exception):
    def __init__(self, order_id: str, current_status: str, expected_status: str):
        self.order_id = order_id
        self.current_status = current_status
        self.expected_status = expected_status
        super().__init__(
            f"Invalid order status for {order_id}: expected '{expected_status}', got '{current_status}'"
        )
