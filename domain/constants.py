from enum import Enum

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
DEFAULT_EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
FAISS_INDEX_DIMENSION = 384

PRICE_ABNORMALITY_RATIO_HIGH = 2.0
PRICE_ABNORMALITY_RATIO_LOW = 0.5

SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
SUPPORTED_PDF_EXTENSIONS = {'.pdf'}
SUPPORTED_EXCEL_EXTENSIONS = {'.xlsx', '.xls'}
SUPPORTED_TEXT_EXTENSIONS = {'.txt', '.csv'}
SUPPORTED_DOCUMENT_EXTENSIONS = SUPPORTED_PDF_EXTENSIONS | SUPPORTED_EXCEL_EXTENSIONS | SUPPORTED_TEXT_EXTENSIONS
