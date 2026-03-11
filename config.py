import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    QWEN_API_KEY = os.getenv("QWEN_API_KEY")
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    
    QWEN_MODEL_MAX = os.getenv("QWEN_MODEL_MAX", "qwen-max")
    QWEN_MODEL_PLUS = os.getenv("QWEN_MODEL_PLUS", "qwen-plus")
    QWEN_MODEL_VL = os.getenv("QWEN_MODEL_VL", "qwen-vl-plus")
    
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
    
    FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "data/faiss_index")
    STANDARD_MATERIALS_PATH = os.getenv("STANDARD_MATERIALS_PATH", "data/standard_materials")
    
    RISK_CONFIDENCE_THRESHOLD = float(os.getenv("RISK_CONFIDENCE_THRESHOLD", 0.8))
    
    MAX_RETRIES = 3
    TIMEOUT = 60
