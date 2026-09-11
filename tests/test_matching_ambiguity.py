import unittest

from application.agents import MatchingAgent
from application.agents.risk_control_agent import RiskControlAgent
from config import Config
from domain.models import (
    MatchedOrder,
    MatchedOrderItem,
    OrderItem,
    ParsedOrder,
    ParsingIssue,
)


class FakeFAISSManager:
    """为确定性匹配提供目录元数据，并可定制嵌入兜底结果。"""

    def __init__(self, metadata, search_results=None):
        self.metadata = metadata
        self._search_results = search_results or []

    def search(self, _query, k=3):
        return self._search_results[:k]


# 同名（屏蔽控制电缆）异规格：归一化后规格主字段一致，仅屏蔽类型限定词不同，
# 一旦错配参考价相差数倍（4.16 vs 23.36）。
CBL_003 = {
    "sku_code": "CBL-003",
    "material_name": "屏蔽控制电缆",
    "specification": "RVVP 4×0.5mm² 普通屏蔽",
    "reference_price": 4.16,
    "aliases": ["屏蔽电缆"],
}
CBL_043 = {
    "sku_code": "CBL-043",
    "material_name": "屏蔽控制电缆",
    "specification": "RVVP 4×0.5mm² 耐油屏蔽",
    "reference_price": 23.36,
}

# 同名（交流接触器）仅末尾后缀不同：10/01 代表不同 SKU，参考价 62.00 vs 215.60。
ELC_001 = {
    "sku_code": "ELC-001",
    "material_name": "交流接触器",
    "specification": "CJX2-0910 AC220V 10",
    "reference_price": 62.00,
    "aliases": ["CJX2 9A 220V"],
}
ELC_025 = {
    "sku_code": "ELC-025",
    "material_name": "交流接触器",
    "specification": "CJX2-0910 AC220V 01",
    "reference_price": 215.60,
    "aliases": ["CJX2 9A 220V"],
}

CATALOG = [CBL_003, CBL_043, ELC_001, ELC_025]


class SameNameDifferentSpecTests(unittest.TestCase):
    def _agent(self, search_results=None):
        return MatchingAgent(
            faiss_manager=FakeFAISSManager(CATALOG, search_results=search_results),
            config=Config(),
        )

    def _item(self, specification, material_name="屏蔽控制电缆"):
        return OrderItem(
            material_name=material_name,
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

    def test_matching_carries_parsing_issues_downstream(self):
        # 解析自检未解决的问题必须随匹配结果继续向下游传递
        parsed_order = ParsedOrder(
            items=[self._item("RVVP 4×0.5mm² 普通屏蔽")],
            total_amount=None,
            parsing_confidence=0.7,
            parsing_issues=[ParsingIssue(item_index=0, description="示例未解决问题")],
        )

        result = self._agent().run({"parsed_order": parsed_order})

        self.assertEqual(
            result["matched_order"].parsing_issues[0].description, "示例未解决问题"
        )


class RegisteredAliasTests(unittest.TestCase):
    def _agent(self, search_results=None):
        return MatchingAgent(
            faiss_manager=FakeFAISSManager(CATALOG, search_results=search_results),
            config=Config(),
        )

    def test_registered_alias_name_resolves_to_catalog_sku(self):
        # 标准完整规格 + 已登记别名：正例仍应通过确定性匹配
        item = OrderItem(
            material_name="屏蔽电缆",
            specification="RVVP 4×0.5mm² 普通屏蔽",
            quantity=100,
            unit="米",
            confidence_score=0.9,
        )

        row = self._agent()._match_by_catalog_key(item)
        matched = self._agent()._match_item(item)

        self.assertEqual(row["sku_code"], "CBL-003")
        self.assertEqual(matched.sku_code, "CBL-003")
        self.assertEqual(matched.match_basis, "catalog_alias_spec_exact")

    def test_matched_item_carries_standard_specification(self):
        # 原始规格为等价书写时，匹配结果需保留标准规格供下游归一化记录使用
        item = OrderItem(
            material_name="屏蔽电缆",
            specification="RVVP 4*0.5mm2 普通屏蔽",
            quantity=100,
            unit="米",
            confidence_score=0.9,
        )

        matched = self._agent()._match_item(item)

        self.assertEqual(matched.sku_code, "CBL-003")
        self.assertEqual(matched.specification, "RVVP 4*0.5mm2 普通屏蔽")
        self.assertEqual(matched.matched_specification, "RVVP 4×0.5mm² 普通屏蔽")

    def test_duplicate_name_spec_key_is_rejected_as_ambiguous(self):
        # 完整名称与规格的目录键对应多个 SKU 时属于歧义，不能默认取第一条
        duplicate_catalog = [
            {
                "sku_code": "DUP-1",
                "material_name": "屏蔽控制电缆",
                "specification": "RVVP 4×0.5mm² 普通屏蔽",
            },
            {
                "sku_code": "DUP-2",
                "material_name": "屏蔽控制电缆",
                "specification": "RVVP 4×0.5mm² 普通屏蔽",
            },
        ]
        agent = MatchingAgent(
            faiss_manager=FakeFAISSManager(duplicate_catalog), config=Config()
        )
        item = OrderItem(
            material_name="屏蔽控制电缆",
            specification="RVVP 4×0.5mm² 普通屏蔽",
            quantity=100,
            unit="米",
            confidence_score=0.9,
        )

        self.assertIsNone(agent._match_by_catalog_key(item))


class NameConflictTests(unittest.TestCase):
    def _agent(self, search_results=None):
        return MatchingAgent(
            faiss_manager=FakeFAISSManager(CATALOG, search_results=search_results),
            config=Config(),
        )

    def test_name_conflict_is_not_accepted_on_unique_spec(self):
        # 规格在目录中唯一，但名称与标准名/已登记别名均不兼容 → 不自动接受
        item = OrderItem(
            material_name="工业电气",
            specification="RVVP 4×0.5mm² 普通屏蔽",
            quantity=100,
            unit="米",
            confidence_score=0.9,
        )

        self.assertIsNone(self._agent()._match_by_catalog_key(item))

    def test_high_similarity_does_not_override_name_conflict(self):
        # 分数接近满分也不能覆盖名称硬冲突，候选须保留并送审
        item = OrderItem(
            material_name="工业电气",
            specification="RVVP 4×0.5mm² 普通屏蔽",
            quantity=100,
            unit="米",
            confidence_score=0.9,
        )
        agent = self._agent(search_results=[(CBL_003, 0.02)])

        matched = agent._match_item(item)

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.candidate_skus, ["CBL-003"])
        self.assertGreater(matched.match_score, 0.98)
        self.assertIn("不兼容", matched.rejection_reason)


class HighScoreCandidateTests(unittest.TestCase):
    def _agent(self, search_results=None):
        return MatchingAgent(
            faiss_manager=FakeFAISSManager(CATALOG, search_results=search_results),
            config=Config(),
        )

    def test_same_name_missing_spec_qualifier_keeps_candidate(self):
        # 同名异规格、缺区分限定词：高相似度候选只保留、不自动接受
        item = OrderItem(
            material_name="屏蔽控制电缆",
            specification="RVVP 4×0.5mm²",
            quantity=100,
            unit="米",
            confidence_score=0.9,
        )
        agent = self._agent(search_results=[(CBL_003, 0.02)])

        matched = agent._match_item(item)

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.candidate_skus, ["CBL-003"])
        self.assertIn("缺少区分候选", matched.rejection_reason)

    def test_multiple_acceptable_candidates_are_ambiguous(self):
        # 多个候选同时满足规格一致与名称兼容 → 歧义，不得任选其一
        duplicate_catalog = [
            {
                "sku_code": "DUP-1",
                "material_name": "屏蔽控制电缆",
                "specification": "RVVP 4×0.5mm² 耐油屏蔽",
            },
            {
                "sku_code": "DUP-2",
                "material_name": "屏蔽控制电缆",
                "specification": "RVVP 4×0.5mm² 耐油屏蔽",
            },
        ]
        item = OrderItem(
            material_name="屏蔽控制电缆",
            specification="RVVP 4×0.5mm² 耐油屏蔽",
            quantity=100,
            unit="米",
            confidence_score=0.9,
        )
        agent = MatchingAgent(
            faiss_manager=FakeFAISSManager(
                duplicate_catalog,
                search_results=[(duplicate_catalog[0], 0.02), (duplicate_catalog[1], 0.02)],
            ),
            config=Config(),
        )

        matched = agent._match_item(item)

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.candidate_skus, ["DUP-1", "DUP-2"])
        self.assertIn("多个规格与名称一致的候选", matched.rejection_reason)

    def test_missing_trailing_suffix_is_not_forced_to_candidate(self):
        # 接触器 10/01：解析漏掉末尾后缀时，不得按最高相似度接受 ELC-025
        item = OrderItem(
            material_name="交流接触器",
            specification="CJX2-0910 AC220V",
            quantity=10,
            unit="个",
            confidence_score=0.9,
        )
        agent = self._agent(search_results=[(ELC_025, 0.03206)])

        matched = agent._match_item(item)

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.candidate_skus, ["ELC-025"])
        self.assertIn("缺少区分候选", matched.rejection_reason)
        self.assertIn("ELC-025", matched.rejection_reason)


class ContactorSuffixRegressionTests(unittest.TestCase):
    """接触器 10/01：末尾后缀不同即不同 SKU，确定性匹配与向量召回两条分支都不得误配。"""

    def _agent(self, search_results=None):
        return MatchingAgent(
            faiss_manager=FakeFAISSManager(CATALOG, search_results=search_results),
            config=Config(),
        )

    def _item(self, specification, material_name="交流接触器"):
        return OrderItem(
            material_name=material_name,
            specification=specification,
            quantity=10,
            unit="个",
            confidence_score=0.9,
        )

    def test_deterministic_path_distinguishes_suffix(self):
        agent = self._agent()
        matched_10 = agent._match_item(self._item("CJX2-0910 AC220V 10"))
        matched_01 = agent._match_item(self._item("CJX2-0910 AC220V 01"))

        self.assertEqual(matched_10.sku_code, "ELC-001")
        self.assertEqual(matched_10.match_basis, "catalog_name_spec_exact")
        self.assertEqual(matched_01.sku_code, "ELC-025")
        self.assertEqual(matched_01.match_basis, "catalog_name_spec_exact")

    def test_alias_name_still_distinguishes_suffix(self):
        # 共享别名 "CJX2 9A 220V" 名称完全一致，仍须由末尾后缀决定 SKU
        agent = self._agent()
        matched_10 = agent._match_item(
            self._item("CJX2-0910 AC220V 10", material_name="CJX2 9A 220V")
        )
        matched_01 = agent._match_item(
            self._item("CJX2-0910 AC220V 01", material_name="CJX2 9A 220V")
        )

        self.assertEqual(matched_10.sku_code, "ELC-001")
        self.assertEqual(matched_10.match_basis, "catalog_alias_spec_exact")
        self.assertEqual(matched_01.sku_code, "ELC-025")
        self.assertEqual(matched_01.match_basis, "catalog_alias_spec_exact")


class AmbiguousMatchRiskTests(unittest.TestCase):
    def test_ambiguous_candidate_blocks_auto_completion(self):
        item = MatchedOrderItem(
            material_name="交流接触器",
            specification="CJX2-0910 AC220V",
            quantity=10,
            unit="个",
            confidence_score=0.9,
            match_score=0.98,
            candidate_skus=["ELC-025"],
            rejection_reason="规格 'CJX2-0910 AC220V' 缺少区分候选 ELC-025（CJX2-0910 AC220V 01）的关键属性",
        )

        result = RiskControlAgent(config=Config()).run(
            {"matched_order": MatchedOrder(items=[item])}
        )

        risk_result = result["risk_result"]
        issue_types = [issue.issue_type for issue in risk_result.issues]
        self.assertTrue(risk_result.needs_confirmation)
        self.assertIn("ambiguous_match", issue_types)


if __name__ == "__main__":
    unittest.main()
