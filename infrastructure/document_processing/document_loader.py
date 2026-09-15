import os
import logging
import json
from pathlib import Path
from typing import Optional, Tuple, List

from domain.constants import (
    SUPPORTED_DOCUMENT_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_TEXT_EXTENSIONS,
)
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
            elif file_ext in SUPPORTED_TEXT_EXTENSIONS:
                return self._load_text(file_path), 'text'
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
            pages = []
            with fitz.open(file_path) as doc:
                for page in doc:
                    if not page.get_text().strip():
                        raise ValueError("PDF 包含无可提取文字的页面，请将扫描页作为图片提交")
                    tables = page.find_tables().tables
                    bounds = [fitz.Rect(table.bbox) for table in tables]
                    # Keep each cell intact; exclude its spans from the surrounding text.
                    lines = []
                    for block in page.get_text("dict", sort=True)["blocks"]:
                        for line in block.get("lines", []):
                            spans = []
                            for span in line["spans"]:
                                rect = fitz.Rect(span["bbox"])
                                center = (rect.tl + rect.br) / 2
                                if not any(center in bound for bound in bounds):
                                    spans.append(span["text"])
                            if spans:
                                lines.append(" ".join(spans))
                    pages.append({
                        "page_number": page.number + 1,
                        "text": "\n".join(lines),
                        "tables": [table.extract() for table in tables],
                    })
            self.logger.info(f"PDF加载完成，共 {len(pages)} 页")
            return json.dumps({"document_type": "pdf", "pages": pages}, ensure_ascii=False)
            
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
            with pd.ExcelFile(file_path) as workbook:
                sheet_name = workbook.sheet_names[0]
                df = pd.read_excel(workbook, sheet_name=sheet_name, header=None,
                                   dtype=object, keep_default_na=False)
            # Preserve source cells and leading zeros; do not turn the title into
            # a header or infer column boundaries from display-alignment spaces.
            rows = json.loads(df.to_json(orient="values", date_format="iso", force_ascii=False,
                                        double_precision=15))
            self.logger.info(f"Excel加载完成，工作表 {sheet_name}，共 {len(rows)} 行")
            return json.dumps({"document_type": "excel", "sheet_name": sheet_name,
                               "rows": rows}, ensure_ascii=False)
            
        except Exception as e:
            self.logger.error(f"Excel加载失败: {str(e)}")
            raise DocumentLoadException(
                f"Excel文件读取失败: {str(e)}",
                details={"file_path": file_path, "error": str(e)}
            )

    def _load_text(self, file_path: str) -> str:
        self.logger.info("加载文本文件: %s", file_path)
        try:
            with open(file_path, "r", encoding="utf-8-sig") as file:
                return file.read()
        except UnicodeDecodeError as exc:
            raise DocumentLoadException(
                "文本文件必须使用 UTF-8 编码",
                details={"file_path": file_path, "error": str(exc)},
            ) from exc
        except OSError as exc:
            raise DocumentLoadException(
                f"文本文件读取失败: {exc}",
                details={"file_path": file_path, "error": str(exc)},
            ) from exc
    
    def validate_file(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False
        if not os.path.isfile(file_path):
            return False
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_formats
    
    def get_supported_formats(self) -> List[str]:
        return list(self.supported_formats)
