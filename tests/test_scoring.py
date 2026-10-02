"""字段级评分的离线守卫测试（零模型调用）。

**为什么必须有**：评分口径一旦写错，整张对照表就是错的，而且**错得很安静**
——数字仍然长得像准确率。这里用**手算得出的小例子**把口径钉死。
"""
from __future__ import annotations

import unittest

from domain.models import OrderItem, ParsedOrder
from evaluation.scoring import (
    ITEM_FIELD_MAP,
    ORDER_FIELD_MAP,
    accuracy,
    merge_counts,
    score_order,
)


def _parsed(items, **order):
    return ParsedOrder(
        order_number=order.get("order_number"),
        customer_name=order.get("customer_name"),
        total_amount=order.get("total_amount"),
        items=items,
        parsing_confidence=0.9,
    )


def _item(name="轴承", spec="6200", quantity=100, unit="套", price=28.7):
    return OrderItem(material_name=name, specification=spec, quantity=quantity,
                     unit=unit, unit_price=price)


def _annotation(items, **order):
    return {
        "document_id": "case",
        "order_level": {
            "order_number": order.get("order_number"),
            "customer_name": order.get("customer_name"),
            "total_amount": order.get("total_amount"),
        },
        "items": items,
    }


def _gold(name="轴承", spec="6200", quantity=100, unit="套", price=28.7):
    return {"material_name_raw": name, "specification_raw": spec, "quantity": quantity,
            "unit": unit, "unit_price": price, "delivery_date": None}


class FieldMapsTests(unittest.TestCase):
    def test_item_map_uses_raw_suffix_for_text_fields(self):
        mapping = dict(ITEM_FIELD_MAP)
        # 标注要求「忠实保留原值」，故物料名/规格在标注里带 _raw 后缀。
        self.assertEqual(mapping["material_name"], "material_name_raw")
        self.assertEqual(mapping["specification"], "specification_raw")
        # 数值字段不带后缀。
        self.assertEqual(mapping["quantity"], "quantity")
        self.assertEqual(mapping["unit_price"], "unit_price")

    def test_order_map_is_identity(self):
        for pred_field, gold_field in ORDER_FIELD_MAP:
            self.assertEqual(pred_field, gold_field)


class ScoreOrderTests(unittest.TestCase):
    def test_perfect_prediction_scores_all_matched(self):
        parsed = _parsed([_item()], order_number="PO-1", customer_name="客户", total_amount=100.0)
        annotation = _annotation([_gold()], order_number="PO-1", customer_name="客户",
                                 total_amount=100.0)
        result = score_order(parsed, annotation)
        self.assertEqual(result["order_fields"]["order_number"], {"matched": 1, "total": 1})
        self.assertEqual(result["item_fields"]["quantity"], {"matched": 1, "total": 1})
        self.assertEqual(result["items_expected"], 1)
        self.assertEqual(result["items_predicted"], 1)

    def test_numeric_tolerance_accepts_float_noise(self):
        # 100.0001 与 100 的差在 1e-3 容差内 → 判为命中（与主评测同口径）。
        parsed = _parsed([_item(quantity=100.0001)], order_number="PO-1",
                         customer_name="客户", total_amount=100.0)
        annotation = _annotation([_gold(quantity=100)], order_number="PO-1",
                                 customer_name="客户", total_amount=100.0)
        result = score_order(parsed, annotation)
        self.assertEqual(result["item_fields"]["quantity"]["matched"], 1)

    def test_wrong_value_counts_as_miss_but_stays_in_denominator(self):
        parsed = _parsed([_item(quantity=1000)], order_number="PO-1",
                         customer_name="客户", total_amount=100.0)
        annotation = _annotation([_gold(quantity=100)], order_number="PO-1",
                                 customer_name="客户", total_amount=100.0)
        result = score_order(parsed, annotation)
        self.assertEqual(result["item_fields"]["quantity"], {"matched": 0, "total": 1})

    def test_unannotated_field_is_excluded_from_denominator(self):
        # delivery_date 标注为 None → 不计入分母，否则「标注没给」会被算成「预测错」。
        parsed = _parsed([_item()], order_number="PO-1", customer_name="客户",
                         total_amount=100.0)
        annotation = _annotation([_gold()], order_number="PO-1", customer_name="客户",
                                 total_amount=100.0)
        result = score_order(parsed, annotation)
        self.assertEqual(result["item_fields"]["delivery_date"]["total"], 0)

    def test_none_prediction_scores_zero_on_every_annotated_field(self):
        annotation = _annotation([_gold()], order_number="PO-1", customer_name="客户",
                                 total_amount=100.0)
        result = score_order(None, annotation)
        self.assertEqual(result["item_fields"]["quantity"], {"matched": 0, "total": 1})
        self.assertEqual(result["order_fields"]["order_number"], {"matched": 0, "total": 1})
        self.assertEqual(result["items_predicted"], 0)

    def test_missing_rows_are_counted_as_misses_not_skipped(self):
        # 少抽一行：第二行的字段仍进分母且全判错——「漏抽」必须受惩罚。
        parsed = _parsed([_item()], order_number="PO-1", customer_name="客户",
                         total_amount=100.0)
        annotation = _annotation([_gold(), _gold(name="阀门", spec="DN32", quantity=500)],
                                 order_number="PO-1", customer_name="客户", total_amount=100.0)
        result = score_order(parsed, annotation)
        self.assertEqual(result["items_expected"], 2)
        self.assertEqual(result["items_predicted"], 1)
        self.assertEqual(result["item_fields"]["quantity"], {"matched": 1, "total": 2})

    def test_alignment_is_positional_not_by_name(self):
        # 第一行物料名写错，但数量正确 → 数量应判命中（按位置对齐），
        # 否则字段错误会被放大成整行错误。
        parsed = _parsed([_item(name="错名", quantity=100)], order_number="PO-1",
                         customer_name="客户", total_amount=100.0)
        annotation = _annotation([_gold(name="轴承", quantity=100)], order_number="PO-1",
                                 customer_name="客户", total_amount=100.0)
        result = score_order(parsed, annotation)
        self.assertEqual(result["item_fields"]["material_name"]["matched"], 0)
        self.assertEqual(result["item_fields"]["quantity"]["matched"], 1)


class AggregateTests(unittest.TestCase):
    def test_merge_counts_accumulates_across_orders(self):
        target = {"quantity": {"matched": 1, "total": 2}}
        merge_counts(target, {"quantity": {"matched": 2, "total": 3},
                              "unit": {"matched": 1, "total": 1}})
        self.assertEqual(target["quantity"], {"matched": 3, "total": 5})
        self.assertEqual(target["unit"], {"matched": 1, "total": 1})

    def test_accuracy_reports_overall_and_per_field(self):
        counts = {"quantity": {"matched": 3, "total": 4},
                  "unit": {"matched": 1, "total": 2}}
        result = accuracy(counts)
        self.assertEqual(result["matched"], 4)
        self.assertEqual(result["total"], 6)
        self.assertAlmostEqual(result["accuracy"], 4 / 6)
        self.assertAlmostEqual(result["per_field"]["quantity"]["accuracy"], 0.75)

    def test_accuracy_of_empty_counts_is_zero_not_error(self):
        result = accuracy({})
        self.assertEqual(result["accuracy"], 0.0)
        self.assertEqual(result["total"], 0)


if __name__ == "__main__":
    unittest.main()
