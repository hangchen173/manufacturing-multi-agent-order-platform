import unittest

from application.agents import MatchingAgent
from config import Config
from domain.models import OrderItem


class FakeFAISSManager:
    """为确定性匹配提供目录元数据，并可定制嵌入兜底结果。"""

    def __init__(self, metadata, search_results=None):
        self.metadata = metadata
        self._search_results = search_results or []

    def search(self, _query, k=3):
        return self._search_results[:k]


# 同名（屏蔽控制电缆）异规格：归一化后规格主字段一致，仅屏蔽类型限定词不同，
# 一旦错配参考价相差数倍（4.16 vs 23.36）。
CATALOG = [
    {
        "sku_code": "CBL-003",
        "material_name": "屏蔽控制电缆",
        "specification": "RVVP 4×0.5mm² 普通屏蔽",
        "reference_price": 4.16,
    },
    {
        "sku_code": "CBL-043",
        "material_name": "屏蔽控制电缆",
        "specification": "RVVP 4×0.5mm² 耐油屏蔽",
        "reference_price": 23.36,
    },
]


class SameNameDifferentSpecTests(unittest.TestCase):
    def _agent(self, search_results=None):
        return MatchingAgent(
            faiss_manager=FakeFAISSManager(CATALOG, search_results=search_results),
            config=Config(),
        )

    def _item(self, specification):
        return OrderItem(
            material_name="屏蔽控制电缆",
            specification=specification,
            quantity=100,
            unit="米",
            confidence_score=0.9,
        )

    def test_exact_spec_resolves_to_its_own_sku(self):
        matched_003 = self._agent()._match_by_catalog_key(
            self._item("RVVP 4×0.5mm² 普通屏蔽")
        )
        matched_043 = self._agent()._match_by_catalog_key(
            self._item("RVVP 4×0.5mm² 耐油屏蔽")
        )

        self.assertEqual(matched_003["sku_code"], "CBL-003")
        self.assertEqual(matched_043["sku_code"], "CBL-043")

    def test_normalized_spec_variants_resolve_to_its_own_sku(self):
        # 全角/半角乘号、上标²与字符2、空格大小写差异均应归一化到同一 SKU
        matched_003 = self._agent()._match_by_catalog_key(
            self._item("RVVP 4*0.5mm2 普通屏蔽")
        )
        matched_043 = self._agent()._match_by_catalog_key(
            self._item("rvvp4ｘ0.5mm²耐油屏蔽")
        )

        self.assertEqual(matched_003["sku_code"], "CBL-003")
        self.assertEqual(matched_043["sku_code"], "CBL-043")

    def test_missing_spec_qualifier_is_not_forced_to_a_sibling_sku(self):
        # 只给出规格主字段、缺少屏蔽类型限定词时，不得在同规格 SKU 间任选一个
        self.assertIsNone(
            self._agent()._match_by_catalog_key(self._item("RVVP 4×0.5mm²"))
        )

    def test_underspecified_spec_falls_back_without_fabricating_sku(self):
        # 确定性层拒识后走嵌入兜底；兜底无结果时不得凭空给出 SKU
        matched = self._agent(search_results=[])._match_item(
            self._item("RVVP 4×0.5mm²")
        )

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.match_score, 0.0)


if __name__ == "__main__":
    unittest.main()
