import os
from pathlib import Path
from typing import Optional, Tuple
import fitz
import pandas as pd
from PIL import Image

class DocumentLoader:
    def __init__(self):
        self.supported_formats = ['.pdf', '.xlsx', '.xls', '.png', '.jpg', '.jpeg']
    
    def load_document(self, file_path: str) -> Tuple[str, Optional[str]]:
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in self.supported_formats:
            raise ValueError(f"不支持的文件格式: {file_ext}")
        
        if file_ext == '.pdf':
            return self._load_pdf(file_path), 'pdf'
        elif file_ext in ['.xlsx', '.xls']:
            return self._load_excel(file_path), 'excel'
        elif file_ext in ['.png', '.jpg', '.jpeg']:
            return file_path, 'image'
        
        return "", None
    
    def _load_pdf(self, file_path: str) -> str:
        text = ""
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        return text
    
    def _load_excel(self, file_path: str) -> str:
        df = pd.read_excel(file_path)
        return df.to_string(index=False)
    
    def validate_file(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_formats
