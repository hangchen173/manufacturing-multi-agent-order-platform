from enum import Enum

class SeverityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class IssueType(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    INVALID_PRICE = "invalid_price"
    PRICE_ABNORMAL = "price_abnormal"
    PRICE_OUT_OF_POLICY = "price_out_of_policy"
    PAST_DELIVERY = "past_delivery"
    INVALID_DATE_FORMAT = "invalid_date_format"
    INVALID_QUANTITY = "invalid_quantity"
    NON_PACK_QUANTITY = "non_pack_quantity"
    LINE_TOTAL_MISMATCH = "line_total_mismatch"
    UNKNOWN_MATERIAL = "unknown_material"
    AMBIGUOUS_MISSING_SPECIFICATION = "ambiguous_missing_specification"

DEFAULT_CONFIDENCE_THRESHOLD = 0.8
DEFAULT_MATCH_THRESHOLD = 0.8
DEFAULT_EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
FAISS_INDEX_DIMENSION = 384

PRICE_ABNORMALITY_RATIO_HIGH = 2.0
PRICE_ABNORMALITY_RATIO_LOW = 0.5
PRICE_POLICY_RATIO_MAX = 1.5
LINE_TOTAL_TOLERANCE = 1.0
PACK_QUANTITY_MULTIPLE = 10

SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
SUPPORTED_PDF_EXTENSIONS = {'.pdf'}
SUPPORTED_EXCEL_EXTENSIONS = {'.xlsx', '.xls'}
SUPPORTED_TEXT_EXTENSIONS = {'.txt', '.csv'}
SUPPORTED_DOCUMENT_EXTENSIONS = SUPPORTED_PDF_EXTENSIONS | SUPPORTED_EXCEL_EXTENSIONS | SUPPORTED_TEXT_EXTENSIONS
