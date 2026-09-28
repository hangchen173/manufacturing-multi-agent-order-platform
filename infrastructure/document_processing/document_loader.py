"""文档加载与结构中间表示（Document IR）。

设计文档 §2.2 / S5：StructureScout 需要"sheet/页/区域探测"所需的原始结构，因此
加载层必须产出**结构化 IR**，而不是把所有内容压成一段文本：

- Excel：逐 Sheet 输出 `name / index / hidden / rows / merged_regions`，隐藏表与
  封面表由 StructureScout 判定是否排除，加载层不预做业务判断。
- PDF：逐页输出 `text / tables`；**缺少可提取文本的页不再整份拒绝**，而是渲染成
  图片并把 `image_path` 放进 IR，交由 StructureScout 路由到图像解析。
- 文本：直接给出 `text`。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        """返回 `(order_text, document_type)`。

        `order_text` 对 pdf/excel 是 Document IR 的 JSON 字符串，对 text 是原文，
        对 image 是文件路径——与历史调用方保持兼容。
        """
        self._validate_file_path(file_path)
        file_ext = Path(file_path).suffix.lower()

        try:
            if file_ext == ".pdf":
                return self._load_pdf(file_path), "pdf"
            if file_ext in (".xlsx", ".xls"):
                return self._load_excel(file_path), "excel"
            if file_ext in SUPPORTED_TEXT_EXTENSIONS:
                return self._load_text(file_path), "text"
            if file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                return file_path, "image"
            raise DocumentLoadException(
                f"不支持的文件格式: {file_ext}",
                details={"file_path": file_path, "extension": file_ext},
            )
        except DocumentLoadException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise DocumentLoadException(
                f"文档加载失败: {exc}",
                details={"file_path": file_path, "error": str(exc)},
            ) from exc

    def load_ir(self, file_path: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """直接返回 Document IR（dict）。供编排层使用，避免二次 JSON 解析。"""
        order_text, document_type = self.load_document(file_path)
        if document_type in {"pdf", "excel"}:
            return json.loads(order_text), document_type
        if document_type == "text":
            return {"document_type": "text", "text": order_text}, document_type
        return {"document_type": "image"}, document_type

    def _validate_file_path(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            raise DocumentLoadException(f"文件不存在: {file_path}", details={"file_path": file_path})
        if not os.path.isfile(file_path):
            raise DocumentLoadException(f"路径不是文件: {file_path}", details={"file_path": file_path})

    # ------------------------------------------------------------------ PDF
    def _load_pdf(self, file_path: str) -> str:
        import fitz

        self.logger.info(f"加载PDF文件: {file_path}")
        try:
            pages: List[Dict[str, Any]] = []
            with fitz.open(file_path) as doc:
                for page in doc:
                    tables = page.find_tables().tables
                    bounds = [fitz.Rect(table.bbox) for table in tables]
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
                    text = "\n".join(lines)
                    entry: Dict[str, Any] = {
                        "page_number": page.number + 1,
                        "text": text,
                        "tables": [table.extract() for table in tables],
                    }
                    if not text.strip() and not entry["tables"]:
                        # 扫描页：渲染成图片，交由图像解析，而不是拒绝整份文档。
                        entry["image_path"] = self._render_pdf_page(page, file_path)
                    pages.append(entry)
            self.logger.info(f"PDF加载完成，共 {len(pages)} 页")
            return json.dumps({"document_type": "pdf", "pages": pages}, ensure_ascii=False)
        except DocumentLoadException:
            raise
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"PDF加载失败: {exc}")
            raise DocumentLoadException(
                f"PDF文件读取失败: {exc}",
                details={"file_path": file_path, "error": str(exc)},
            ) from exc

    @staticmethod
    def _render_pdf_page(page: Any, file_path: str) -> str:
        import fitz

        image_path = f"{file_path}.page-{page.number + 1}.png"
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        pixmap.save(image_path)
        return image_path

    # ------------------------------------------------------------------ Excel
    def _load_excel(self, file_path: str) -> str:
        import openpyxl
        import pandas as pd

        self.logger.info(f"加载Excel文件: {file_path}")
        try:
            structure = self._excel_structure(file_path, openpyxl)
            sheets: List[Dict[str, Any]] = []
            with pd.ExcelFile(file_path) as workbook:
                for index, name in enumerate(workbook.sheet_names):
                    df = pd.read_excel(
                        workbook, sheet_name=name, header=None, dtype=object, keep_default_na=False,
                    )
                    # 保留源单元格与前置零；不把标题当表头，也不按显示对齐推断列边界。
                    rows = json.loads(df.to_json(
                        orient="values", date_format="iso", force_ascii=False, double_precision=15,
                    ))
                    meta = structure.get(name, {})
                    sheets.append({
                        "name": name,
                        "index": index,
                        "hidden": bool(meta.get("hidden")),
                        "rows": rows,
                        "merged_regions": meta.get("merged_regions") or [],
                    })
            self.logger.info(f"Excel加载完成，共 {len(sheets)} 个工作表")
            return json.dumps({"document_type": "excel", "sheets": sheets}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"Excel加载失败: {exc}")
            raise DocumentLoadException(
                f"Excel文件读取失败: {exc}",
                details={"file_path": file_path, "error": str(exc)},
            ) from exc

    @staticmethod
    def _excel_structure(file_path: str, openpyxl_module: Any) -> Dict[str, Dict[str, Any]]:
        """用 openpyxl 读取隐藏状态与合并区域（pandas 不暴露这些结构信息）。"""
        structure: Dict[str, Dict[str, Any]] = {}
        workbook = openpyxl_module.load_workbook(file_path, read_only=False, data_only=True)
        try:
            for name in workbook.sheetnames:
                sheet = workbook[name]
                structure[name] = {
                    "hidden": sheet.sheet_state != "visible",
                    "merged_regions": [str(rng) for rng in sheet.merged_cells.ranges],
                }
        finally:
            workbook.close()
        return structure

    # ------------------------------------------------------------------ text
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
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return False
        return Path(file_path).suffix.lower() in self.supported_formats

    def get_supported_formats(self) -> List[str]:
        return list(self.supported_formats)
