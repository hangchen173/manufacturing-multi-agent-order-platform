import math
import unittest
from datetime import date

from pydantic import ValidationError

from application.agents import PolicyRisk, ScheduleRisk
from config import Config
from domain.constants import FIELD_MISSING_POLICY
from domain.models import MatchedOrderItem, OrderItem, ParsedOrder
from tests.support import build_harness, item, order_payload


def _item(**overrides):
    values = dict(
        material_name="螺丝", specification="M8", quantity=10, unit="个", unit_price=1.0,
        delivery_date=None, confidence_score=0.95, sku_code="SCR-001",
        matched_material_name="螺丝", match_score=0.98,
    )
    values.update(overrides)
    return MatchedOrderItem(**values)


def _policy(evaluation_as_of="2026-05-10"):
    config = Config()
    config.risk.evaluation_as_of = evaluation_as_of
    return PolicyRisk(config=config)


def _schedule(evaluation_as_of="2026-05-10"):
    config = Config()
    config.risk.evaluation_as_of = evaluation_as_of
    return ScheduleRisk(config=config)


def _issue_types(issues):
    return [issue["issue_type"] for issue in issues]


class FieldMissingPolicyTests(unittest.TestCase):
    def test_policy_covers_all_declared_fields(self):
        self.assertEqual(
            set(FIELD_MISSING_POLICY),
            {"material_name", "specification", "quantity", "unit", "unit_price",
             "delivery_date", "total_amount"},
        )

    def test_material_name_missing_is_rejected_by_schema(self):
        with self.assertRaises(ValidationError):
            OrderItem(material_name=None, specification="M8", quantity=10)

    def test_specification_missing_escalates(self):
        agent = _policy()

        self.assertEqual(agent.check_ambiguous_specification(_item().model_dump(), 0), [])
        issues = agent.check_ambiguous_specification(_item(specification=None).model_dump(), 0)

        self.assertEqual(_issue_types(issues), ["ambiguous_missing_specification"])
        self.assertEqual(issues[0]["severity"], "high")

    def test_quantity_missing_escalates(self):
        agent = _policy()

        self.assertEqual(agent.check_missing_quantity(_item().model_dump(), 0), [])
        issues = agent.check_missing_quantity(_item(quantity=None).model_dump(), 0)

        self.assertEqual(_issue_types(issues), ["missing_quantity"])
        self.assertEqual(issues[0]["severity"], "high")

    def test_unit_price_missing_escalates(self):
        agent = _policy()

        self.assertEqual(agent.check_missing_unit_price(_item().model_dump(), 0), [])
        issues = agent.check_missing_unit_price(_item(unit_price=None).model_dump(), 0)

        self.assertEqual(_issue_types(issues), ["missing_unit_price"])
        self.assertEqual(issues[0]["severity"], "high")

    def test_missing_total_amount_skips_amount_check(self):
        agent = _policy()

        self.assertEqual(agent.check_line_total([_item().model_dump()], None), [])

    def test_schema_preserves_unknown_numbers_as_none(self):
        item_row = OrderItem(material_name="螺丝", specification="M8", quantity=None, unit_price=None)

        self.assertIsNone(item_row.quantity)
        self.assertIsNone(item_row.unit_price)

    def test_missing_quantity_is_not_a_parse_failure(self):
        harness = build_harness(payloads=[order_payload([item("螺丝", "M8", None, "个", 1.0)])])

        result = harness.orchestrator.process_order_from_text("1 螺丝 M8")

        self.assertTrue(result["success"])
        self.assertEqual(len(harness.prompts), 1)
        self.assertEqual(result["diagnostics"]["parse"]["challenges"], [])
        issue_types = [issue.issue_type for issue in result["final_result"].risk_result.issues]
        self.assertIn("missing_quantity", issue_types)


class IllegalValueTests(unittest.TestCase):
    def test_non_finite_quantity_is_rejected(self):
        with self.assertRaises(ValidationError):
            OrderItem(material_name="螺丝", specification="M8", quantity=math.inf)

    def test_non_finite_unit_price_is_rejected(self):
        with self.assertRaises(ValidationError):
            OrderItem(material_name="螺丝", specification="M8", unit_price=math.nan)

    def test_confidence_out_of_range_is_rejected(self):
        for value in (1.5, -0.1):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    OrderItem(material_name="螺丝", specification="M8", confidence_score=value)

    def test_parsing_confidence_out_of_range_is_rejected(self):
        with self.assertRaises(ValidationError):
            ParsedOrder(items=[], parsing_confidence=1.2)

    def test_non_finite_total_amount_is_rejected(self):
        with self.assertRaises(ValidationError):
            ParsedOrder(items=[], total_amount=math.inf, parsing_confidence=0.9)

    def test_negative_quantity_is_flagged(self):
        issues = _policy().check_quantity(_item(quantity=-1).model_dump(), 0)

        self.assertEqual(_issue_types(issues), ["invalid_quantity"])
        self.assertEqual(issues[0]["severity"], "high")

    def test_zero_price_is_flagged(self):
        issues = _policy().check_price_abnormality(_item(unit_price=0.0).model_dump(), 0)

        self.assertEqual(_issue_types(issues), ["invalid_price"])
        self.assertEqual(issues[0]["severity"], "high")

    def test_bad_delivery_date_format_is_flagged(self):
        issues = _schedule().check_delivery_date(
            _item(delivery_date="2026/05/10").model_dump(), 0, date(2026, 5, 10)
        )

        self.assertEqual(_issue_types(issues), ["invalid_date_format"])
        self.assertEqual(issues[0]["severity"], "medium")


class DeliveryDateSemanticsTests(unittest.TestCase):
    def test_today_delivery_is_not_past(self):
        issues = _schedule().check_delivery_date(
            _item(delivery_date="2026-05-10").model_dump(), 0, date(2026, 5, 10)
        )

        self.assertEqual(issues, [])

    def test_future_delivery_is_not_past(self):
        issues = _schedule().check_delivery_date(
            _item(delivery_date="2026-05-11").model_dump(), 0, date(2026, 5, 10)
        )

        self.assertEqual(issues, [])

    def test_previous_day_delivery_is_past(self):
        issues = _schedule().check_delivery_date(
            _item(delivery_date="2026-05-09").model_dump(), 0, date(2026, 5, 10)
        )

        self.assertEqual(_issue_types(issues), ["past_delivery"])
        self.assertEqual(issues[0]["severity"], "high")


class LineTotalPolicyTests(unittest.TestCase):
    def test_consistent_total_passes(self):
        agent = _policy()

        self.assertEqual(agent.check_line_total([_item(quantity=10, unit_price=1.0).model_dump()], 10.0), [])

    def test_mismatched_total_is_blocking_when_complete(self):
        issues = _policy().check_line_total([_item(quantity=10, unit_price=1.0).model_dump()], 20.0)

        self.assertEqual(_issue_types(issues), ["line_total_mismatch"])
        self.assertEqual(issues[0]["severity"], "high")

    def test_incomplete_line_data_is_marked_without_fabrication(self):
        issues = _policy().check_line_total([_item(quantity=None).model_dump()], 10.0)

        self.assertEqual(_issue_types(issues), ["insufficient_amount_info"])
        self.assertEqual(issues[0]["severity"], "medium")
        self.assertIn("未按零参与计算", issues[0]["description"])

    def test_missing_price_does_not_create_false_mismatch(self):
        issues = _policy().check_line_total([_item(unit_price=None).model_dump()], 10.0)
        issue_types = _issue_types(issues)

        self.assertNotIn("line_total_mismatch", issue_types)
        self.assertIn("insufficient_amount_info", issue_types)


class PackQuantityScopeTests(unittest.TestCase):
    def test_pack_rule_applies_to_count_units(self):
        issues = _policy().check_non_pack_quantity(_item(quantity=15, unit="个").model_dump(), 0)

        self.assertEqual(_issue_types(issues), ["non_pack_quantity"])
        self.assertEqual(issues[0]["severity"], "high")

    def test_pack_rule_skips_other_units(self):
        issues = _policy().check_non_pack_quantity(_item(quantity=15, unit="米").model_dump(), 0)

        self.assertEqual(issues, [])

    def test_pack_rule_skips_missing_unit(self):
        issues = _policy().check_non_pack_quantity(_item(quantity=15, unit=None).model_dump(), 0)

        self.assertEqual(issues, [])


class MissingFieldEndToEndTests(unittest.TestCase):
    def test_missing_quantity_and_price_escalate(self):
        harness = build_harness(
            payloads=[order_payload([item("螺丝", "M8", None, "个", None)])]
        )

        result = harness.orchestrator.process_order_from_text("1 螺丝 M8")

        self.assertTrue(result["needs_confirmation"])
        issue_types = [issue.issue_type for issue in result["final_result"].risk_result.issues]
        self.assertIn("missing_quantity", issue_types)
        self.assertIn("missing_unit_price", issue_types)

    def test_missing_unit_only_stays_auto_approved(self):
        harness = build_harness(
            payloads=[order_payload([item("螺丝", "M8", 10, None, 1.0)])],
            catalog=[{"sku_code": "SCR-001", "material_name": "螺丝", "specification": "M8",
                      "unit": "个", "reference_price": 1.0, "aliases": []}],
        )

        result = harness.orchestrator.process_order_from_text("1 螺丝 M8 10 1.0")

        self.assertFalse(result["needs_confirmation"])


if __name__ == "__main__":
    unittest.main()
