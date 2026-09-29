import unittest

from application.agents import PolicyRisk
from config import Config
from domain.models import BusinessAction, MatchedOrder, MatchedOrderItem
from tests.support import FakeFAISSManager, build_harness, item, order_payload

# 同名（屏蔽控制电缆）异规格：归一化后规格主字段一致，仅屏蔽类型限定词不同，
# 一旦错配参考价相差数倍（4.16 vs 23.36）。
CBL_003 = {
    "sku_code": "CBL-003", "material_name": "屏蔽控制电缆",
    "specification": "RVVP 4×0.5mm² 普通屏蔽", "unit": "米", "reference_price": 4.16,
    "category": "线缆", "aliases": ["屏蔽电缆"],
}
CBL_043 = {
    "sku_code": "CBL-043", "material_name": "屏蔽控制电缆",
    "specification": "RVVP 4×0.5mm² 耐油屏蔽", "unit": "米", "reference_price": 23.36,
    "category": "线缆", "aliases": [],
}

# 同名（交流接触器）仅末尾后缀不同：10/01 代表不同 SKU，参考价 62.00 vs 215.60。
ELC_001 = {
    "sku_code": "ELC-001", "material_name": "交流接触器",
    "specification": "CJX2-0910 AC220V 10", "unit": "个", "reference_price": 62.00,
    "category": "电气", "aliases": ["CJX2 9A 220V"],
}
ELC_025 = {
    "sku_code": "ELC-025", "material_name": "交流接触器",
    "specification": "CJX2-0910 AC220V 01", "unit": "个", "reference_price": 215.60,
    "category": "电气", "aliases": ["CJX2 9A 220V"],
}

CATALOG = [CBL_003, CBL_043, ELC_001, ELC_025]

# 含规格的登记别名：用户习惯按别名整串书写，抽取后规格字段为空。
# 别名整串本身已唯一确定 SKU，不得因「规格字段为空」而拒识。
SPEC_BEARING_CATALOG = [
    {"sku_code": "FST-4", "material_name": "不锈钢内六角圆柱头螺钉",
     "specification": "304 M8×12", "unit": "个", "reference_price": 0.33,
     "category": "紧固件", "aliases": ["304内六角螺丝 M8*12"]},
    {"sku_code": "FST-10", "material_name": "不锈钢内六角圆柱头螺钉",
     "specification": "304 M10×16", "unit": "个", "reference_price": 0.63,
     "category": "紧固件", "aliases": ["304内六角螺丝 M10*16"]},
]


def _match(catalog, name, spec, *, search_results=None, quantity=100, unit="米", price=1.0):
    """通过真实 Supervisor 跑单行订单，返回匹配后的明细项。"""
    store = FakeFAISSManager(catalog, search_results=search_results or [])
    harness = build_harness(
        payloads=[order_payload([item(name, spec, quantity, unit, price)])],
        faiss_manager=store,
    )
    result = harness.orchestrator.process_order_from_text(
        f"1 {name} {spec} {quantity} {unit} {price}"
    )
    assert result["success"], result.get("message")
    return result["final_result"].matched_order.items[0]


class SameNameDifferentSpecTests(unittest.TestCase):
    def test_exact_spec_resolves_to_its_own_sku(self):
        matched_003 = _match(CATALOG, "屏蔽控制电缆", "RVVP 4×0.5mm² 普通屏蔽")
        matched_043 = _match(CATALOG, "屏蔽控制电缆", "RVVP 4×0.5mm² 耐油屏蔽")

        self.assertEqual(matched_003.sku_code, "CBL-003")
        self.assertEqual(matched_043.sku_code, "CBL-043")

    def test_normalized_spec_variants_resolve_to_its_own_sku(self):
        # 全角/半角乘号、上标²与字符2、空格大小写差异均应归一化到同一 SKU
        matched_003 = _match(CATALOG, "屏蔽控制电缆", "RVVP 4*0.5mm2 普通屏蔽")
        matched_043 = _match(CATALOG, "屏蔽控制电缆", "rvvp4ｘ0.5mm²耐油屏蔽")

        self.assertEqual(matched_003.sku_code, "CBL-003")
        self.assertEqual(matched_043.sku_code, "CBL-043")

    def test_missing_spec_qualifier_is_not_forced_to_a_sibling_sku(self):
        # 只给出规格主字段、缺少屏蔽类型限定词时，不得在同规格 SKU 间任选一个
        matched = _match(CATALOG, "屏蔽控制电缆", "RVVP 4×0.5mm²")

        self.assertIsNone(matched.sku_code)

    def test_underspecified_spec_falls_back_without_fabricating_sku(self):
        # 确定性层拒识后走向量兜底；兜底无结果时不得凭空给出 SKU
        matched = _match(CATALOG, "屏蔽控制电缆", "RVVP 4×0.5mm²", search_results=[])

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.match_score, 0.0)

    def test_matching_carries_parsing_issues_downstream(self):
        # 解析自检未解决的问题必须随匹配结果继续向下游传递
        harness = build_harness(
            payloads=[order_payload([item("螺丝", "M8", 10, "个", 1.0)]),
                      order_payload([item("螺丝", "M8", 10, "个", 1.0)])],
            catalog=[{"sku_code": "SKU-1", "material_name": "螺丝", "specification": "M8",
                      "unit": "个", "reference_price": 1.0, "aliases": []}],
        )
        result = harness.orchestrator.process_order_from_text("1 螺丝 M8 10 个 1.0\n2 螺母 M8 5 个 2.0")

        matched_order = result["final_result"].matched_order
        self.assertEqual(len(matched_order.parsing_issues), 1)
        self.assertIn("明细数量不一致", matched_order.parsing_issues[0].description)


class RegisteredAliasTests(unittest.TestCase):
    def test_registered_alias_name_resolves_to_catalog_sku(self):
        # 标准完整规格 + 已登记别名：正例仍应通过确定性匹配
        matched = _match(CATALOG, "屏蔽电缆", "RVVP 4×0.5mm² 普通屏蔽")

        self.assertEqual(matched.sku_code, "CBL-003")
        self.assertEqual(matched.match_basis, "catalog_alias_spec_exact")

    def test_matched_item_carries_standard_specification(self):
        # 原始规格为等价书写时，匹配结果需保留标准规格供下游归一化记录使用
        matched = _match(CATALOG, "屏蔽电缆", "RVVP 4*0.5mm2 普通屏蔽")

        self.assertEqual(matched.sku_code, "CBL-003")
        self.assertEqual(matched.specification, "RVVP 4*0.5mm2 普通屏蔽")
        self.assertEqual(matched.matched_specification, "RVVP 4×0.5mm² 普通屏蔽")

    def test_duplicate_name_spec_key_is_rejected_as_ambiguous(self):
        # 完整名称与规格的目录键对应多个 SKU 时属于歧义，不能默认取第一条
        duplicate_catalog = [
            {"sku_code": "DUP-1", "material_name": "屏蔽控制电缆",
             "specification": "RVVP 4×0.5mm² 普通屏蔽", "unit": "米", "reference_price": 4.16,
             "aliases": []},
            {"sku_code": "DUP-2", "material_name": "屏蔽控制电缆",
             "specification": "RVVP 4×0.5mm² 普通屏蔽", "unit": "米", "reference_price": 4.16,
             "aliases": []},
        ]
        matched = _match(duplicate_catalog, "屏蔽控制电缆", "RVVP 4×0.5mm² 普通屏蔽")

        self.assertIsNone(matched.sku_code)

    def test_spec_bearing_alias_written_verbatim_resolves_without_separate_spec(self):
        # 用户把含规格的登记别名整串写进物料名称、规格字段为空：
        # 别名整串已唯一确定 SKU，不得因「规格为空」降级为人工审核
        matched = _match(SPEC_BEARING_CATALOG, "304内六角螺丝 M8*12", None, quantity=10, unit="个")

        self.assertEqual(matched.sku_code, "FST-4")
        self.assertEqual(matched.match_basis, "catalog_alias_exact")

    def test_alias_exact_match_records_explainable_name_normalization(self):
        # 别名整串命中后，改写为标准名的动作必须可解释，而不是静默替换
        harness = build_harness(
            payloads=[order_payload([item("304内六角螺丝 M8*12", None, 10, "个", 0.33)])],
            catalog=SPEC_BEARING_CATALOG,
        )
        result = harness.orchestrator.process_order_from_text("1 304内六角螺丝 M8*12 10 个 0.33")
        decision = result["business_decision"]

        self.assertEqual(decision.action, BusinessAction.AUTO_CORRECT)
        self.assertEqual(len(decision.normalizations), 1)
        change = decision.normalizations[0]
        self.assertEqual(change.field, "material_name")
        self.assertEqual(change.original_value, "304内六角螺丝 M8*12")
        self.assertEqual(change.standard_value, "不锈钢内六角圆柱头螺钉")
        self.assertEqual(change.basis, "物料名称整串命中标准库已登记别名（别名内含规格）")

    def test_alias_shared_by_multiple_skus_is_still_ambiguous_without_spec(self):
        # 别名本身有歧义（ELC-001/ELC-025 共享 "CJX2 9A 220V"）时不得任选其一
        matched = _match(CATALOG, "CJX2 9A 220V", None, quantity=10, unit="个")

        self.assertIsNone(matched.sku_code)

    def test_alias_split_across_name_and_spec_still_resolves(self):
        # 同一输入的另一种抽取形态：规格被拆进规格字段。名称与规格拼合后
        # 仍等于同一条别名，必须同样命中，否则结果取决于模型如何切分
        matched = _match(SPEC_BEARING_CATALOG, "304内六角螺丝", "M8*12", quantity=10, unit="个")

        self.assertEqual(matched.sku_code, "FST-4")
        self.assertEqual(matched.match_basis, "catalog_alias_joined_exact")

    def test_alias_split_still_distinguishes_sibling_specs(self):
        # 拼合命中不得抹平同族不同规格：M10*16 必须落到另一个 SKU
        matched = _match(SPEC_BEARING_CATALOG, "304内六角螺丝", "M10*16", quantity=10, unit="个")

        self.assertEqual(matched.sku_code, "FST-10")
        self.assertEqual(matched.match_basis, "catalog_alias_joined_exact")

    def test_split_alias_form_is_auto_corrected_end_to_end(self):
        # 拆开书写（名称 + 规格两字段）也必须走确定性归一化，而不是人工审核
        harness = build_harness(
            payloads=[order_payload([item("304内六角螺丝", "M8*12", 10, "个", 0.33)])],
            catalog=SPEC_BEARING_CATALOG,
        )
        result = harness.orchestrator.process_order_from_text("1 304内六角螺丝 M8*12 10 个 0.33")
        decision = result["business_decision"]
        risk = result["final_result"].risk_result

        self.assertFalse(risk.needs_confirmation)
        self.assertEqual(decision.action, BusinessAction.AUTO_CORRECT)
        self.assertEqual(
            sorted(change.field for change in decision.normalizations),
            ["material_name", "specification"],
        )
        self.assertNotIn(
            "ambiguous_missing_specification",
            [issue.issue_type for issue in risk.issues],
        )

    def test_split_alias_with_a_wrong_spec_fragment_is_rejected(self):
        # 拼合键必须整体命中别名：规格片段不成立时不得凭名称前缀接受
        matched = _match(SPEC_BEARING_CATALOG, "304内六角螺丝", "M9*99", quantity=10, unit="个")

        self.assertIsNone(matched.sku_code)

    def test_canonical_name_without_spec_is_not_accepted_by_alias_index(self):
        # 别名索引只认 aliases 列；标准名不含规格，缺规格时仍须拒识
        matched = _match(CATALOG, "屏蔽控制电缆", None, quantity=100, unit="米")

        self.assertIsNone(matched.sku_code)

    def test_alias_verbatim_does_not_override_a_conflicting_spec(self):
        # 已给出规格且与目录冲突时，别名整串不得覆盖规格硬冲突
        matched = _match(
            SPEC_BEARING_CATALOG, "304内六角螺丝 M8*12", "304 M10×16", quantity=10, unit="个",
        )

        self.assertIsNone(matched.sku_code)

    def test_spec_bearing_alias_does_not_raise_missing_specification_risk(self):
        # 规格内嵌在别名整串里、抽取规格为空时，标准库行才是规格的权威来源：
        # 物料已被唯一确定，不得再以「规格缺失」判为高风险转人工
        harness = build_harness(
            payloads=[order_payload([item("304内六角螺丝 M8*12", None, 10, "个", 0.33)])],
            catalog=SPEC_BEARING_CATALOG,
        )
        result = harness.orchestrator.process_order_from_text("1 304内六角螺丝 M8*12 10 个 0.33")
        risk = result["final_result"].risk_result

        self.assertFalse(risk.needs_confirmation)
        self.assertNotIn(
            "ambiguous_missing_specification",
            [issue.issue_type for issue in risk.issues],
        )
        # 抽取规格仍为空：不补造原文字段，只在 matched_specification 记录标准规格
        matched_item = result["final_result"].matched_order.items[0]
        self.assertIsNone(matched_item.specification)
        self.assertEqual(matched_item.matched_specification, "304 M8×12")

    def test_missing_specification_still_escalates_without_a_catalog_spec(self):
        # 未命中任何 SKU 时不适用豁免：缺规格仍须送审
        harness = build_harness(
            payloads=[order_payload([item("304内六角螺丝 M9*99", None, 10, "个", 0.33)])],
            catalog=SPEC_BEARING_CATALOG,
        )
        result = harness.orchestrator.process_order_from_text("1 304内六角螺丝 M9*99 10 个 0.33")
        risk = result["final_result"].risk_result

        self.assertTrue(risk.needs_confirmation)
        self.assertIn(
            "ambiguous_missing_specification",
            [issue.issue_type for issue in risk.issues],
        )


class NameConflictTests(unittest.TestCase):
    def test_name_conflict_is_not_accepted_on_unique_spec(self):
        # 规格在目录中唯一，但名称与标准名/已登记别名均不兼容 → 不自动接受
        matched = _match(CATALOG, "工业电气", "RVVP 4×0.5mm² 普通屏蔽")

        self.assertIsNone(matched.sku_code)

    def test_high_similarity_does_not_override_name_conflict(self):
        # 分数接近满分也不能覆盖名称硬冲突，候选须保留并送审
        matched = _match(
            CATALOG, "工业电气", "RVVP 4×0.5mm² 普通屏蔽",
            search_results=[(CBL_003, 0.02)],
        )

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.candidate_skus, ["CBL-003"])
        self.assertGreater(matched.match_score, 0.98)
        self.assertIn("不兼容", matched.rejection_reason)


class HighScoreCandidateTests(unittest.TestCase):
    def test_same_name_missing_spec_qualifier_keeps_candidate(self):
        # 同名异规格、缺区分限定词：高相似度候选只保留、不自动接受
        matched = _match(
            CATALOG, "屏蔽控制电缆", "RVVP 4×0.5mm²",
            search_results=[(CBL_003, 0.02)],
        )

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.candidate_skus, ["CBL-003"])
        self.assertIn("缺少区分候选", matched.rejection_reason)

    def test_multiple_acceptable_candidates_are_ambiguous(self):
        # 多个候选同时满足规格一致与名称兼容 → 歧义，不得任选其一
        duplicate_catalog = [
            {"sku_code": "DUP-1", "material_name": "屏蔽控制电缆",
             "specification": "RVVP 4×0.5mm² 耐油屏蔽", "unit": "米", "reference_price": 23.36,
             "aliases": []},
            {"sku_code": "DUP-2", "material_name": "屏蔽控制电缆",
             "specification": "RVVP 4×0.5mm² 耐油屏蔽", "unit": "米", "reference_price": 23.36,
             "aliases": []},
        ]
        matched = _match(
            duplicate_catalog, "屏蔽控制电缆", "RVVP 4×0.5mm² 耐油屏蔽",
            search_results=[(duplicate_catalog[0], 0.02), (duplicate_catalog[1], 0.02)],
        )

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.candidate_skus, ["DUP-1", "DUP-2"])
        self.assertIn("多个规格与名称一致的候选", matched.rejection_reason)

    def test_missing_trailing_suffix_is_not_forced_to_candidate(self):
        # 接触器 10/01：解析漏掉末尾后缀时，不得按最高相似度接受 ELC-025
        matched = _match(
            CATALOG, "交流接触器", "CJX2-0910 AC220V",
            search_results=[(ELC_025, 0.03206)], quantity=10, unit="个", price=200.0,
        )

        self.assertIsNone(matched.sku_code)
        self.assertEqual(matched.candidate_skus, ["ELC-025"])
        self.assertIn("缺少区分候选", matched.rejection_reason)
        self.assertIn("ELC-025", matched.rejection_reason)


class ContactorSuffixRegressionTests(unittest.TestCase):
    """接触器 10/01：末尾后缀不同即不同 SKU，确定性匹配与向量召回两条分支都不得误配。"""

    def test_deterministic_path_distinguishes_suffix(self):
        matched_10 = _match(CATALOG, "交流接触器", "CJX2-0910 AC220V 10", quantity=10, unit="个")
        matched_01 = _match(CATALOG, "交流接触器", "CJX2-0910 AC220V 01", quantity=10, unit="个")

        self.assertEqual(matched_10.sku_code, "ELC-001")
        self.assertEqual(matched_10.match_basis, "catalog_name_spec_exact")
        self.assertEqual(matched_01.sku_code, "ELC-025")
        self.assertEqual(matched_01.match_basis, "catalog_name_spec_exact")

    def test_alias_name_still_distinguishes_suffix(self):
        # 共享别名 "CJX2 9A 220V" 名称完全一致，仍须由末尾后缀决定 SKU
        matched_10 = _match(CATALOG, "CJX2 9A 220V", "CJX2-0910 AC220V 10", quantity=10, unit="个")
        matched_01 = _match(CATALOG, "CJX2 9A 220V", "CJX2-0910 AC220V 01", quantity=10, unit="个")

        self.assertEqual(matched_10.sku_code, "ELC-001")
        self.assertEqual(matched_10.match_basis, "catalog_alias_spec_exact")
        self.assertEqual(matched_01.sku_code, "ELC-025")
        self.assertEqual(matched_01.match_basis, "catalog_alias_spec_exact")


class AmbiguousMatchRiskTests(unittest.TestCase):
    def test_ambiguous_candidate_blocks_auto_completion(self):
        item_row = MatchedOrderItem(
            material_name="交流接触器", specification="CJX2-0910 AC220V", quantity=10,
            unit="个", confidence_score=0.9, match_score=0.98, candidate_skus=["ELC-025"],
            rejection_reason="规格 'CJX2-0910 AC220V' 缺少区分候选 ELC-025"
                             "（CJX2-0910 AC220V 01）的关键属性",
        )
        agent = PolicyRisk(config=Config())

        issues = agent.check_ambiguous_match(item_row.model_dump(), 0)

        self.assertEqual([issue["issue_type"] for issue in issues], ["ambiguous_match"])
        self.assertEqual(issues[0]["severity"], "high")


if __name__ == "__main__":
    unittest.main()
