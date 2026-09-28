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

# 风险问题的规范排序：PolicyRisk 与 ScheduleRisk 分属两个 Agent，合并时必须
# 用同一口径排序，保证同一订单的风险列表顺序可复现、可对比。
RISK_CHECK_ORDER = (
    "low_confidence",
    "unknown_material",
    "ambiguous_match",
    "ambiguous_missing_specification",
    "missing_quantity",
    "missing_unit_price",
    "non_pack_quantity",
    "invalid_price",
    "price_abnormal",
    "price_out_of_policy",
    "invalid_date_format",
    "past_delivery",
    "invalid_quantity",
    "unresolved_parsing_problem",
    "line_total_mismatch",
    "insufficient_amount_info",
)

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

# 文档结构词汇表：StructureScout 用它探测区域，GroundingVerifier 用它逐格比对。
# 两处共用同一口径，避免“结构侦察认出的表”和“溯源校验认的表”不一致。
EXCEL_SEQUENCE_HEADERS = ("序号", "行号")
EXCEL_HEADER_ALIASES = {
    "material_name": ("物料名称", "品名", "名称", "货物名称"),
    "specification": ("规格型号", "规格", "型号", "规格及型号"),
    "quantity": ("数量", "订购数量", "采购数量"),
    "unit": ("单位", "计量单位"),
    "unit_price": ("含税单价", "单价", "单价(元)", "单价（元）"),
    "delivery_date": ("交期", "要求交期", "交货日期", "交货期"),
}
# 表头必须至少包含这些字段，才认定该区域是订单明细区。
EXCEL_REQUIRED_DETAIL_FIELDS = ("material_name", "quantity")
# 结构上像封面/说明而不是明细的工作表名特征。
EXCEL_NON_DETAIL_SHEET_HINTS = ("说明", "封面", "须知", "备注", "填写", "模板")

SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
SUPPORTED_PDF_EXTENSIONS = {'.pdf'}
SUPPORTED_EXCEL_EXTENSIONS = {'.xlsx', '.xls'}
SUPPORTED_TEXT_EXTENSIONS = {'.txt', '.csv'}
SUPPORTED_DOCUMENT_EXTENSIONS = SUPPORTED_PDF_EXTENSIONS | SUPPORTED_EXCEL_EXTENSIONS | SUPPORTED_TEXT_EXTENSIONS
