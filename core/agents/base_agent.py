from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from langchain_core.language_models import BaseLanguageModel
from config import Config

class BaseAgent(ABC):
    def __init__(self, llm: Optional[BaseLanguageModel] = None):
        self.config = Config()
        self.llm = llm
        self.name = self.__class__.__name__
    
    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    def get_name(self) -> str:
        return self.name
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        return True
    
    def log_info(self, message: str):
        print(f"[{self.name}] {message}")
    
    def log_error(self, message: str):
        print(f"[{self.name}][ERROR] {message}")
