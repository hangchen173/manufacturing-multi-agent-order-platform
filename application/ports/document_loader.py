"""文档加载端口：把上传文件解析成订单文本或 Document IR。"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, Tuple


class DocumentLoaderPort(Protocol):
    def load_document(self, file_path: str) -> Tuple[str, Optional[str]]:
        """返回 `(order_text, document_type)`。"""
        ...

    def load_ir(self, file_path: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """直接返回 Document IR 与其类型，避免二次 JSON 解析。"""
        ...
