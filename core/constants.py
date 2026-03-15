from enum import Enum

class ModelType(str, Enum):
    QWEN_MAX = "qwen-max"
    QWEN_PLUS = "qwen-plus"
    QWEN_VL_PLUS = "qwen-vl-plus"

class DocumentType(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"
    IMAGE = "image"
    TEXT = "text"
    UNKNOWN = "unknown"

class SeverityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class IssueType(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    LOW_MATCH_SCORE = "low_match_score"
    INVALID_PRICE = "invalid_price"
    PRICE_ABNORMAL = "price_abnormal"
    PAST_DELIVERY = "past_delivery"
    INVALID_DATE_FORMAT = "invalid_date_format"
    INVALID_QUANTITY = "invalid_quantity"

DEFAULT_CONFIDENCE_THRESHOLD = 0.8
DEFAULT_MATCH_THRESHOLD = 0.8
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT = 60
DEFAULT_EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
FAISS_INDEX_DIMENSION = 384

PRICE_ABNORMALITY_RATIO_HIGH = 2.0
PRICE_ABNORMALITY_RATIO_LOW = 0.5

SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
SUPPORTED_PDF_EXTENSIONS = {'.pdf'}
SUPPORTED_EXCEL_EXTENSIONS = {'.xlsx', '.xls'}
SUPPORTED_TEXT_EXTENSIONS = {'.txt', '.csv'}
SUPPORTED_DOCUMENT_EXTENSIONS = SUPPORTED_PDF_EXTENSIONS | SUPPORTED_EXCEL_EXTENSIONS | SUPPORTED_TEXT_EXTENSIONS

MODEL_PRICING = {
    ModelType.QWEN_MAX: {"input": 0.02, "output": 0.06},
    ModelType.QWEN_PLUS: {"input": 0.004, "output": 0.012},
    ModelType.QWEN_VL_PLUS: {"input": 0.008, "output": 0.02}
}
