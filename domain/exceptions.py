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

class MatchingException(AgentBaseException):
    pass

class RiskControlException(AgentBaseException):
    pass

class OrchestratorException(AgentBaseException):
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
