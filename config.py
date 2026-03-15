import os
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass
class ModelConfig:
    api_key: str
    base_url: str
    max_model: str
    plus_model: str
    vl_model: str

@dataclass
class ServerConfig:
    env: str
    debug: bool
    port: int

@dataclass
class DataConfig:
    data_dir: str
    faiss_index_path: str
    standard_materials_path: str

@dataclass
class RiskConfig:
    confidence_threshold: float
    match_threshold: float
    max_retries: int
    timeout: int

class Config:
    _instance: Optional['Config'] = None
    
    def __new__(cls) -> 'Config':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.model = ModelConfig(
            api_key=self._get_env("QWEN_API_KEY", required=True),
            base_url=self._get_env("QWEN_BASE_URL", default="https://dashscope.aliyuncs.com/compatible-mode/v1"),
            max_model=self._get_env("QWEN_MODEL_MAX", default="qwen-max"),
            plus_model=self._get_env("QWEN_MODEL_PLUS", default="qwen-plus"),
            vl_model=self._get_env("QWEN_MODEL_VL", default="qwen-vl-plus")
        )
        
        self.server = ServerConfig(
            env=self._get_env("FLASK_ENV", default="development"),
            debug=self._get_env("FLASK_DEBUG", default="1") == "1",
            port=int(self._get_env("FLASK_PORT", default="5001"))
        )
        
        self.data = DataConfig(
            data_dir=self._get_env("DATA_DIR", default="data"),
            faiss_index_path=self._get_env("FAISS_INDEX_PATH", default="data/faiss_index"),
            standard_materials_path=self._get_env("STANDARD_MATERIALS_PATH", default="data/standard_materials")
        )
        
        self.risk = RiskConfig(
            confidence_threshold=float(self._get_env("RISK_CONFIDENCE_THRESHOLD", default="0.8")),
            match_threshold=float(self._get_env("RISK_MATCH_THRESHOLD", default="0.8")),
            max_retries=int(self._get_env("MAX_RETRIES", default="3")),
            timeout=int(self._get_env("TIMEOUT", default="60"))
        )
        
        self.hf_endpoint = self._get_env("HF_ENDPOINT", default="https://huggingface.co")
    
    @staticmethod
    def _get_env(key: str, default: Optional[str] = None, required: bool = False) -> str:
        value = os.getenv(key, default)
        if required and not value:
            raise ValueError(f"Required environment variable '{key}' is not set")
        return value
    
    @property
    def QWEN_API_KEY(self) -> str:
        return self.model.api_key
    
    @property
    def QWEN_BASE_URL(self) -> str:
        return self.model.base_url
    
    @property
    def QWEN_MODEL_MAX(self) -> str:
        return self.model.max_model
    
    @property
    def QWEN_MODEL_PLUS(self) -> str:
        return self.model.plus_model
    
    @property
    def QWEN_MODEL_VL(self) -> str:
        return self.model.vl_model
    
    @property
    def FLASK_ENV(self) -> str:
        return self.server.env
    
    @property
    def FLASK_DEBUG(self) -> bool:
        return self.server.debug
    
    @property
    def FLASK_PORT(self) -> int:
        return self.server.port
    
    @property
    def DATA_DIR(self) -> str:
        return self.data.data_dir
    
    @property
    def FAISS_INDEX_PATH(self) -> str:
        return self.data.faiss_index_path
    
    @property
    def STANDARD_MATERIALS_PATH(self) -> str:
        return self.data.standard_materials_path
    
    @property
    def RISK_CONFIDENCE_THRESHOLD(self) -> float:
        return self.risk.confidence_threshold
    
    @property
    def MAX_RETRIES(self) -> int:
        return self.risk.max_retries
    
    @property
    def TIMEOUT(self) -> int:
        return self.risk.timeout
