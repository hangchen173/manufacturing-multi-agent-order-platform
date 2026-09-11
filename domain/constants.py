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
    AMBIGUOUS_MATCH = "ambiguous_match"
    AMBIGUOUS_MISSING_SPECIFICATION = "ambiguous_missing_specification"
    UNRESOLVED_PARSING_PROBLEM = "unresolved_parsing_problem"
    MISSING_QUANTITY = "missing_quantity"
    MISSING_UNIT_PRICE = "missing_unit_price"
    INSUFFICIENT_AMOUNT_INFO = "insufficient_amount_info"

DEFAULT_CONFIDENCE_THRESHOLD = 0.8
DEFAULT_MATCH_THRESHOLD = 0.8
DEFAULT_EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
FAISS_INDEX_DIMENSION = 384

PRICE_ABNORMALITY_RATIO_HIGH = 2.0
PRICE_ABNORMALITY_RATIO_LOW = 0.5
PRICE_POLICY_RATIO_MAX = 1.5
LINE_TOTAL_TOLERANCE = 1.0

# 缺失字段政策：抽取 schema 与下游风控共用同一口径，缺失一律保留未知，禁止猜测或补默认值。
# - reject：不得缺失，缺失即拒识（结构校验失败）。
# - escalate：不得猜测，缺失时标记为阻断项送审。
# - allow：允许缺失，缺失即跳过对应校验，不补造默认值。
FIELD_MISSING_POLICY = {
    "material_name": "reject",
    "specification": "escalate",
    "quantity": "escalate",
    "unit": "allow",
    "unit_price": "escalate",
    "delivery_date": "allow",
    "total_amount": "allow",
}

# 包装数量约束仅适用于模拟业务范围内的计件单位，不默认代表所有制造业物料。
PACK_QUANTITY_MULTIPLE = 10
PACK_QUANTITY_UNITS = frozenset({"个", "只", "件"})

SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
SUPPORTED_PDF_EXTENSIONS = {'.pdf'}
SUPPORTED_EXCEL_EXTENSIONS = {'.xlsx', '.xls'}
SUPPORTED_TEXT_EXTENSIONS = {'.txt', '.csv'}
SUPPORTED_DOCUMENT_EXTENSIONS = SUPPORTED_PDF_EXTENSIONS | SUPPORTED_EXCEL_EXTENSIONS | SUPPORTED_TEXT_EXTENSIONS
