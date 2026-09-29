"""向量库端口：标准物料库的语义检索能力。

用 `Protocol` 而非 ABC：FAISSManager 与测试替身（FakeFAISSManager /
OfflineFAISSManager）都无需继承它，结构化匹配即可，避免适配器为了满足类型
而引入无谓的继承关系。
"""
from __future__ import annotations

from typing import Any, Dict, List, Protocol, Tuple


class VectorStore(Protocol):
    #: 标准物料库的元数据行（含 sku_code / reference_price 等）
    metadata: List[Dict[str, Any]]

    def search(self, query: str, k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """返回 `(物料元数据, 距离)` 列表，距离越小越相似。"""
        ...
