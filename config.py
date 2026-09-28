import os
from typing import Any, Dict, Optional
from dataclasses import dataclass

from dotenv import load_dotenv
from domain.exceptions import ConfigurationException

load_dotenv()

#: 不同服务商控制「思考/推理强度」的参数名不同，发错会被静默忽略。这里按 base_url
#: 主机名分流。两项均已在 2026-09 对真实接口实测：
#:   - DeepSeek：`/models` 声明 `effort` 支持 low/high/max、默认 high，接口接受该参数；
#:     但实测其**对 token 消耗无可稳定复现的影响**（同档位内波动大于档位间差异），
#:     故这里只作为「意图声明」（解析任务不需要高推理档），不得据此宣称节省 token。
#:   - DashScope：`enable_thinking=False` 实测生效，qwen3.8-flash 关闭思考后
#:     completion_tokens 188 → 31，且不再返回 reasoning_tokens。
#: 真正的成本杠杆是 max_tokens —— 推理与正文共享该预算（见 extractor.EXTRACTION_MAX_TOKENS）。
_THINKING_PARAM_BY_HOST = (
    ("deepseek", {"effort": "low"}),
    ("dashscope", {"enable_thinking": False}),
    ("aliyuncs", {"enable_thinking": False}),
)


@dataclass
class ModelConfig:
    api_key: Optional[str]
    base_url: str
    model: str
    #: 显式覆盖推理控制参数；为 None 时按 base_url 自动分流（见 request_body）。
    extra_body: Optional[Dict[str, Any]] = None

    def request_body(self) -> Dict[str, Any]:
        """该模型要求的推理控制参数。显式配置优先，否则按服务商分流。"""
        if self.extra_body is not None:
            return dict(self.extra_body)
        host = (self.base_url or "").lower()
        for marker, body in _THINKING_PARAM_BY_HOST:
            if marker in host:
                return dict(body)
        return {}


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

    def model_for(self, role: str) -> ModelConfig:
        """解析某个角色应使用的模型配置（角色级多模型路由的唯一入口）。

        约定：环境变量 `<ROLE>_MODEL` / `<ROLE>_API_KEY` / `<ROLE>_BASE_URL`
        覆盖默认模型，缺项回落到 `self.model`。

        - 未配置任何角色级变量 → 返回默认模型，即「单模型模式」，与改造前行为一致；
        - 例如 `EXTRACTOR_MODEL=deepseek-flash` + `REVIEW_ASSISTANT_MODEL=qwen3.8-flash`
          → 生产者与审核助手各用一家模型。
        """
        prefix = role.upper()
        name = self._get_env(f"{prefix}_MODEL")
        api_key = self._get_env(f"{prefix}_API_KEY")
        base_url = self._get_env(f"{prefix}_BASE_URL")
        if not (name or api_key or base_url):
            return self.model
        return ModelConfig(
            api_key=api_key or self.model.api_key,
            base_url=base_url or self.model.base_url,
            model=name or self.model.model,
        )
