import os
import logging
from pathlib import Path
from typing import Optional, Tuple, List

from domain.constants import SUPPORTED_DOCUMENT_EXTENSIONS, SUPPORTED_IMAGE_EXTENSIONS
from domain.exceptions import DocumentLoadException

class DocumentLoader:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.supported_formats = list(SUPPORTED_DOCUMENT_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS)
    
    def load_document(self, file_path: str) -> Tuple[str, Optional[str]]:
        self._validate_file_path(file_path)
        
        file_ext = Path(file_path).suffix.lower()
        
        try:
            if file_ext == '.pdf':
                return self._load_pdf(file_path), 'pdf'
            elif file_ext in ['.xlsx', '.xls']:
                return self._load_excel(file_path), 'excel'
            elif file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                return file_path, 'image'
            else:
                raise DocumentLoadException(
                    f"不支持的文件格式: {file_ext}",
                    details={"file_path": file_path, "extension": file_ext}
                )
        except DocumentLoadException:
            raise
        except Exception as e:
            raise DocumentLoadException(
                f"文档加载失败: {str(e)}",
                details={"file_path": file_path, "error": str(e)}
            )
    
    def _validate_file_path(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            raise DocumentLoadException(
                f"文件不存在: {file_path}",
                details={"file_path": file_path}
            )
        
        if not os.path.isfile(file_path):
            raise DocumentLoadException(
                f"路径不是文件: {file_path}",
                details={"file_path": file_path}
            )
    
    def _load_pdf(self, file_path: str) -> str:
        import fitz

        self.logger.info(f"加载PDF文件: {file_path}")
        
        try:
            doc = fitz.open(file_path)
            text_parts = []
            
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(page_text)
            
            doc.close()
            full_text = "\n".join(text_parts)
            
            self.logger.info(f"PDF加载完成，共 {len(text_parts)} 页")
            return full_text
            
        except Exception as e:
            self.logger.error(f"PDF加载失败: {str(e)}")
            raise DocumentLoadException(
                f"PDF文件读取失败: {str(e)}",
                details={"file_path": file_path, "error": str(e)}
            )
    
    def _load_excel(self, file_path: str) -> str:
        import pandas as pd

        self.logger.info(f"加载Excel文件: {file_path}")
        
        try:
            df = pd.read_excel(file_path)
            text = df.to_string(index=False)
            
            self.logger.info(f"Excel加载完成，共 {len(df)} 行")
            return text
            
        except Exception as e:
            self.logger.error(f"Excel加载失败: {str(e)}")
            raise DocumentLoadException(
                f"Excel文件读取失败: {str(e)}",
                details={"file_path": file_path, "error": str(e)}
            )
    
    def validate_file(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False
        if not os.path.isfile(file_path):
            return False
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_formats
    
    def get_supported_formats(self) -> List[str]:
        return list(self.supported_formats)
