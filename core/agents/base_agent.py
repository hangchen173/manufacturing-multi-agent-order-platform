import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from langchain_core.language_models import BaseLanguageModel
from config import Config

class BaseAgent(ABC):
    def __init__(self, llm: Optional[BaseLanguageModel] = None, config: Optional[Config] = None):
        self.config = config or Config()
        self.llm = llm
        self.name = self.__class__.__name__
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        self.logger = logging.getLogger(self.name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f'[%(name)s] %(levelname)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    def get_name(self) -> str:
        return self.name
    
    def validate_input(self, input_data: Dict[str, Any], required_keys: Optional[list] = None) -> bool:
        if required_keys:
            missing_keys = [key for key in required_keys if key not in input_data]
            if missing_keys:
                raise ValueError(f"Missing required keys: {missing_keys}")
        return True
    
    def log_info(self, message: str) -> None:
        self.logger.info(message)
    
    def log_error(self, message: str) -> None:
        self.logger.error(message)
    
    def log_warning(self, message: str) -> None:
        self.logger.warning(message)
    
    def log_debug(self, message: str) -> None:
        self.logger.debug(message)
