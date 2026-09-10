import os
from typing import Optional
from dataclasses import dataclass

from dotenv import load_dotenv
from domain.exceptions import ConfigurationException

load_dotenv()

@dataclass
class ModelConfig:
    api_key: Optional[str]
    base_url: str
    model: str

@dataclass
class ServerConfig:
    debug: bool
    port: int

@dataclass
class DataConfig:
    data_dir: str
    faiss_index_path: str
    standard_materials_path: str
    order_auto_archive_days: int

@dataclass
class DatabaseConfig:
    url: str

@dataclass
class RiskConfig:
    confidence_threshold: float
    match_threshold: float
    evaluation_as_of: Optional[str]

class Config:
    def __init__(self):
        self.model = ModelConfig(
            api_key=self._get_env("QWEN_API_KEY"),
            base_url=self._get_env("QWEN_BASE_URL", default="https://dashscope.aliyuncs.com/compatible-mode/v1"),
            model=self._get_env("QWEN_MODEL", default="qwen3.7-plus")
        )
        
        self.server = ServerConfig(
            debug=self._get_bool_env("FLASK_DEBUG", default=True),
            port=int(self._get_env("FLASK_PORT", default="5001"))
        )
        
        self.data = DataConfig(
            data_dir=self._get_env("DATA_DIR", default="data"),
            faiss_index_path=self._get_env("FAISS_INDEX_PATH", default="data/faiss_index"),
            standard_materials_path=self._get_env("STANDARD_MATERIALS_PATH", default="data/standard_materials.csv"),
            order_auto_archive_days=int(self._get_env("ORDER_AUTO_ARCHIVE_DAYS", default="30")),
        )
        self.database = DatabaseConfig(
            url=self._get_env("DATABASE_URL", default="postgresql://orders:orders@localhost:5432/orders")
        )
        
        self.risk = RiskConfig(
            confidence_threshold=float(self._get_env("RISK_CONFIDENCE_THRESHOLD", default="0.8")),
            match_threshold=float(self._get_env("RISK_MATCH_THRESHOLD", default="0.8")),
            evaluation_as_of=self._get_env("RISK_EVALUATION_AS_OF"),
        )
    
    @staticmethod
    def _get_env(key: str, default: Optional[str] = None) -> Optional[str]:
        return os.getenv(key, default)

    @staticmethod
    def _get_bool_env(key: str, default: bool = False) -> bool:
        value = os.getenv(key)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def require_model_api_key(self) -> str:
        if not self.model.api_key:
            raise ConfigurationException("QWEN_API_KEY 未配置，无法初始化模型客户端")
        return self.model.api_key
