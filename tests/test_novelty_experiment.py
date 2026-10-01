"""新颖性判决实验脚本的离线守卫。

这些测试不调用任何模型，也不依赖被 git 忽略的 `datasets/generated_complex`：
它们用临时 xlsx 走一遍**真实代码路径**，确认三件事：

1. 样本构造给出可复现的 locator，且 locator 指向的源单元格就是 gold；
2. 两臂的 feedback 确实被逐字注入 prompt —— 规格 §7 的头号陷阱是
   「feedback 没生效」，那会让整个实验变成两次无差别的重抽；
3. 两臂 prompt 除 feedback 外逐字节相同 —— 这是「单变量」的形式化证明。
"""
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from langchain_core.messages import AIMessage
from openpyxl import Workbook

from application.agents.extractor import Extractor
from application.protocol import build_counter_evidence_feedback
from config import Config
from infrastructure.document_processing import DocumentLoader
from scripts import novelty_experiment as experiment

HEADER = ["序号", "物料名称", "规格型号", "数量", "单位", "含税单价"]
ROWS = [
    [1, "深沟球轴承", "6200-OPEN", 100, "套", 28.7],
    [2, "不锈钢球阀", "Q11F-25P DN32", 500, "个", 124.5],
    [3, "硬质合金立铣刀", "D5×100 4刃", 50, "支", 83.94],
]


def _write_order(path: Path, rows=None) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "采购订单"
    sheet.append(HEADER)
    for row in rows or ROWS:
        sheet.append(row)
    workbook.save(str(path))


def _annotation(order_id: str) -> dict:
    return {
        "document_id": order_id,
        "items": [
            {"line_index": row[0], "material_name_raw": row[1],
             "specification_raw": row[2], "quantity": row[3], "unit": row[4],
             "unit_price": row[5]}
            for row in ROWS
        ],
    }


def _fake_llm(items, captured=None):
    """按调用顺序记录 prompt 的假模型；返回一份结构合法的 ParsedOrder。"""
    def call(prompt_value):
        if captured is not None:
            captured.append(prompt_value.to_string())
        return AIMessage(content=json.dumps({
            "order_number": "PO-1", "customer_name": "客户01", "items": items,
            "total_amount": 100.0, "parsing_confidence": 0.95,
        }, ensure_ascii=False))
    return call


def _parsed_item(**overrides):
    item = {"material_name": "深沟球轴承", "specification": "6200-OPEN",
            "quantity": 100, "unit": "套", "unit_price": 28.7,
            "delivery_date": None, "confidence_score": 0.95}
    item.update(overrides)
    return item


class SampleConstructionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp.name)
        self.loader = DocumentLoader()

    def tearDown(self):
        self._tmp.cleanup()

    def _build(self, ordinal=0, usage=None, seed=1):
        path = self.directory / "order.xlsx"
        _write_order(path)
        return experiment.build_sample(
            path, _annotation("order"), self.loader, ordinal,
            random.Random(seed), usage if usage is not None else {},
        )

    def test_locator_points_at_the_gold_cell(self):
        sample = self._build()
        locator = sample["locator"]

        document_ir, _ = self.loader.load_ir(str(self.directory / "order.xlsx"))
        sheet = next(item for item in document_ir["sheets"]
                     if item["name"] == locator["sheet"])
        cell = sheet["rows"][locator["row"] - 1][locator["column"] - 1]

        self.assertEqual(cell, sample["gold_value"])
        self.assertEqual(sample["gold_value"], sample["annotation_gold"])

    def test_injected_value_differs_from_gold(self):
        for ordinal in range(6):
            sample = self._build(ordinal=ordinal)
            self.assertNotEqual(
                str(sample["injected_value"]), str(sample["gold_value"]),
                f"ordinal={ordinal} 注入值与 gold 相同",
            )

    def test_field_allocation_is_balanced(self):
        usage = {}
        fields = [self._build(ordinal=index, usage=usage)["field"] for index in range(8)]

        self.assertEqual(set(fields), set(experiment.FIELD_ROTATION))
        self.assertLessEqual(max(fields.count(name) for name in set(fields))
                             - min(fields.count(name) for name in set(fields)), 1)

    def test_collect_samples_redirects_to_the_temp_directory(self):
        for index in range(4):
            order_id = f"order_{index}"
            _write_order(self.directory / f"{order_id}.xlsx")
            (self.directory / f"{order_id}.json").write_text(
                json.dumps(_annotation(order_id), ensure_ascii=False), encoding="utf-8"
            )

        with mock.patch.object(experiment, "ORDERS_DIR", self.directory), \
                mock.patch.object(experiment, "ANNOTATIONS_DIR", self.directory):
            samples = experiment.collect_samples(limit=4, seed=7)

        self.assertEqual(len(samples), 4)
        self.assertEqual(len({sample["field"] for sample in samples}), 4)


class InjectionDifficultyTests(unittest.TestCase):
    """D19 难度阶梯：gross 一眼可辨，subtle 是同列真实值（行错位）。"""

    def test_subtle_picks_the_most_similar_value_in_the_column(self):
        locators = [{"values": {"quantity": value}} for value in (100, 120, 1000)]

        injected = experiment.inject_wrong_value(
            "quantity", 100, locators, random.Random(0), difficulty="subtle")

        self.assertEqual(injected, 1000, "同列候选中「1000」与 gold「100」最像，应被选中")

    def test_subtle_value_always_exists_in_the_same_column(self):
        values = (10, 25, 100, 3)
        locators = [{"values": {"quantity": value}} for value in values]

        injected = experiment.inject_wrong_value(
            "quantity", 10, locators, random.Random(0), difficulty="subtle")

        self.assertIn(injected, (25, 100, 3))
        self.assertNotEqual(str(injected), "10")

    def test_subtle_covers_text_fields_too(self):
        locators = [{"values": {"material_name": name}}
                    for name in ("轴承", "轴承座", "阀门")]

        injected = experiment.inject_wrong_value(
            "material_name", "轴承", locators, random.Random(0), difficulty="subtle")

        self.assertEqual(injected, "轴承座")

    def test_gross_numeric_is_an_order_of_magnitude_off(self):
        locators = [{"values": {"quantity": value}} for value in (100, 120, 1000)]

        injected = experiment.inject_wrong_value(
            "quantity", 100, locators, random.Random(0), difficulty="gross")

        self.assertEqual(injected, 1000.0)

    def test_no_alternative_means_no_injection(self):
        locators = [{"values": {"quantity": 100}}]

        self.assertIsNone(experiment.inject_wrong_value(
            "quantity", 100, locators, random.Random(0), difficulty="subtle"))

    def test_unknown_difficulty_is_rejected(self):
        with self.assertRaises(ValueError):
            experiment.inject_wrong_value(
                "quantity", 100, [{"values": {"quantity": 1}}], random.Random(0),
                difficulty="medium")

    def test_default_difficulty_matches_the_2026_10_02_pilot(self):
        self.assertEqual(experiment.DIFFICULTIES, ("gross", "subtle"))


class DifficultyIsolatesTheSampleIdentityTests(unittest.TestCase):
    """两档必须是**同一批样本**，否则难度阶梯就不是单变量对照。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp.name)
        for index in range(4):
            order_id = f"order_{index}"
            _write_order(self.directory / f"{order_id}.xlsx")
            (self.directory / f"{order_id}.json").write_text(
                json.dumps(_annotation(order_id), ensure_ascii=False), encoding="utf-8"
            )

    def tearDown(self):
        self._tmp.cleanup()

    def _collect(self, difficulty):
        with mock.patch.object(experiment, "ORDERS_DIR", self.directory), \
                mock.patch.object(experiment, "ANNOTATIONS_DIR", self.directory):
            return experiment.collect_samples(limit=4, seed=7, difficulty=difficulty)

    def test_both_difficulties_select_the_identical_samples(self):
        gross = self._collect("gross")
        subtle = self._collect("subtle")

        for key in ("sample_id", "order_id", "item_index", "field", "gold_value", "locator"):
            self.assertEqual(
                [sample[key] for sample in gross],
                [sample[key] for sample in subtle],
                f"两档的 {key} 必须逐一相同，否则难度与样本身份混淆",
            )

    def test_difficulty_is_recorded_on_every_sample(self):
        for sample in self._collect("subtle"):
            self.assertEqual(sample["difficulty"], "subtle")


class OutputTokenBudgetTests(unittest.TestCase):
    """弱模型的 max_tokens 上限可能低于生产默认值，需要实验专用下调旋钮。"""

    def setUp(self):
        from application.agents import extractor as extractor_module
        from application.agents import review_assistant as review_module

        self.extractor = extractor_module
        self.review = review_module
        self.original = (extractor_module.EXTRACTION_MAX_TOKENS,
                         review_module.REVIEW_MAX_TOKENS)

    def tearDown(self):
        self.extractor.EXTRACTION_MAX_TOKENS = self.original[0]
        self.review.REVIEW_MAX_TOKENS = self.original[1]

    def test_production_defaults_are_pinned(self):
        effective = experiment.apply_output_token_budget(None)

        self.assertEqual(effective, {"EXTRACTION_MAX_TOKENS": 16384,
                                     "REVIEW_MAX_TOKENS": 4096})

    def test_override_lowers_extraction_but_never_raises_review(self):
        effective = experiment.apply_output_token_budget(8192)

        self.assertEqual(effective["EXTRACTION_MAX_TOKENS"], 8192)
        self.assertEqual(effective["REVIEW_MAX_TOKENS"], 4096,
                         "review 的 4096 已低于 8192，不应被抬高")
        self.assertEqual(self.extractor.EXTRACTION_MAX_TOKENS, 8192)

    def test_non_positive_is_rejected(self):
        with self.assertRaises(ValueError):
            experiment.apply_output_token_budget(0)


class FeedbackInjectionTests(unittest.TestCase):
    """单变量对照的形式化证明：两臂 prompt 只差 feedback 那一小段。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        directory = Path(self._tmp.name)
        path = directory / "order.xlsx"
        _write_order(path)
        self.sample = experiment.build_sample(
            path, _annotation("order"), DocumentLoader(), 0, random.Random(1), {}
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _prompt_for(self, mode: str, items) -> str:
        captured = []
        extractor = Extractor(llm=_fake_llm(items, captured), config=Config())
        experiment.run_once(extractor, self.sample, mode)
        self.assertEqual(len(captured), 1, "假模型应恰好被调用一次")
        return captured[0]

    def test_feedback_is_injected_verbatim_in_both_arms(self):
        challenge = experiment.build_challenge(self.sample)

        for mode in ("locator", "natural_language"):
            feedback = build_counter_evidence_feedback([challenge], mode=mode)
            prompt = self._prompt_for(mode, [_parsed_item()])
            self.assertIn(feedback, prompt, f"{mode} 的 feedback 没有进入 prompt")

    def test_two_arms_prompts_differ_only_in_the_feedback(self):
        challenge = experiment.build_challenge(self.sample)
        feedback_b = build_counter_evidence_feedback([challenge], mode="locator")
        feedback_a = build_counter_evidence_feedback([challenge], mode="natural_language")

        prompt_b = self._prompt_for("locator", [_parsed_item()])
        prompt_a = self._prompt_for("natural_language", [_parsed_item()])

        self.assertNotEqual(prompt_a, prompt_b)
        self.assertEqual(
            prompt_a.replace(feedback_a, "\x00"),
            prompt_b.replace(feedback_b, "\x00"),
            "两臂 prompt 的差异不止 feedback，单变量对照被破坏",
        )

    def test_arm_a_prompt_never_mentions_the_source_coordinates(self):
        challenge = experiment.build_challenge(self.sample)
        feedback_a = build_counter_evidence_feedback([challenge], mode="natural_language")

        self.assertNotIn(str(self.sample["locator"]["row"]), feedback_a)
        self.assertNotIn(str(self.sample["locator"]["column"]), feedback_a)
        self.assertNotIn(repr(self.sample["gold_value"]), feedback_a)


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        path = Path(self._tmp.name) / "order.xlsx"
        _write_order(path)
        self.sample = experiment.build_sample(
            path, _annotation("order"), DocumentLoader(), 0, random.Random(1), {}
        )
        self.assertEqual(self.sample["field"], "quantity")
        self.assertEqual(self.sample["gold_value"], 100)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, items):
        extractor = Extractor(llm=_fake_llm(items), config=Config())
        return experiment.run_once(extractor, self.sample, "locator")

    def test_restoring_the_gold_value_counts_as_corrected(self):
        result = self._run([_parsed_item(quantity=100)])
        self.assertEqual(result["outcome"], experiment.OUTCOME_CORRECTED)

    def test_keeping_the_injected_value_counts_as_unchanged(self):
        result = self._run([_parsed_item(quantity=self.sample["injected_value"])])
        self.assertEqual(result["outcome"], experiment.OUTCOME_UNCHANGED)

    def test_null_counts_as_abstention_not_correction(self):
        result = self._run([_parsed_item(quantity=None)])
        self.assertEqual(result["outcome"], experiment.OUTCOME_ABSTAINED)

    def test_a_third_value_counts_as_over_correction(self):
        result = self._run([_parsed_item(quantity=7)])
        self.assertEqual(result["outcome"], experiment.OUTCOME_OTHER_WRONG)

    def test_model_failure_is_recorded_instead_of_crashing_the_run(self):
        def broken(_prompt_value):
            raise RuntimeError("boom")

        extractor = Extractor(llm=broken, config=Config())
        result = experiment.run_once(extractor, self.sample, "locator")

        self.assertEqual(result["outcome"], experiment.OUTCOME_ERROR)
        self.assertIn("boom", result["error"])


class StatisticsTests(unittest.TestCase):
    def test_mcnemar_is_symmetric_and_bounded(self):
        self.assertAlmostEqual(experiment.mcnemar_exact(3, 7),
                               experiment.mcnemar_exact(7, 3))
        self.assertEqual(experiment.mcnemar_exact(0, 0), 1.0)

    def test_mcnemar_rejects_the_null_on_a_lopsided_split(self):
        self.assertLess(experiment.mcnemar_exact(1, 20), 0.05)

    def test_summarize_prefers_arm_b_when_only_b_corrects(self):
        # 8 个不一致配对全部偏向 B：精确双侧 p = 2·0.5^8 = 0.0078 < 0.05，足以判 GO。
        samples = [{"sample_id": f"s{i}"} for i in range(8)]
        runs = []
        for sample in samples:
            for arm in ("A_natural_language", "B_locator"):
                runs.append({
                    "sample_id": sample["sample_id"], "arm": arm, "repeat": 0,
                    "outcome": (experiment.OUTCOME_CORRECTED
                                if arm == "B_locator" else experiment.OUTCOME_UNCHANGED),
                    "total_tokens": 100, "latency_ms": 10.0,
                })

        summary = experiment.summarize(samples, runs)

        self.assertEqual(summary["discordant_a_wrong_b_right"], 8)
        self.assertEqual(summary["discordant_a_right_b_wrong"], 0)
        self.assertEqual(summary["verdict"], "GO")
        self.assertAlmostEqual(summary["delta_correction_rate"], 1.0)

    def test_summarize_stays_conservative_on_a_small_lopsided_split(self):
        # 同样的方向、只有 4 个不一致配对时 p = 0.125，检验力不足，不得判 GO。
        samples = [{"sample_id": f"s{i}"} for i in range(4)]
        runs = []
        for sample in samples:
            for arm in ("A_natural_language", "B_locator"):
                runs.append({
                    "sample_id": sample["sample_id"], "arm": arm, "repeat": 0,
                    "outcome": (experiment.OUTCOME_CORRECTED
                                if arm == "B_locator" else experiment.OUTCOME_UNCHANGED),
                    "total_tokens": 100, "latency_ms": 10.0,
                })

        summary = experiment.summarize(samples, runs)

        self.assertGreater(summary["mcnemar_p_value"], 0.05)
        self.assertEqual(summary["verdict"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
