"""对照实验驱动脚本的离线守卫测试（**零模型调用**）。

这里钉的是一个**曾经真实发生过、而且错得很安静**的缺陷：

首次实跑时 ``run_veap`` 写成了 ``raw["final_result"].get("parsed_order")``，
但编排器的 ``final_result`` 是 pydantic 对象 ``FinalOrderResult``，**不是 dict**。
后果是 ``AttributeError`` 被 ``except`` 吞掉，**每一份** VEAP 结果都被记成失败，
而准确率表照常生成、排版毫无异常，表现为「VEAP 准确率 0」——
极易被误读成「系统不行」，进而推翻一个其实成立的结论。

故本文件的核心断言不是「函数能跑」，而是**「函数在两种形状下都返回同一个对象」**。
"""
from __future__ import annotations

import unittest

from domain.models import FinalOrderResult, OrderItem, OrderStatus, ParsedOrder
from scripts.baseline_comparison import (
    _category,
    parsed_order_from_response,
    select_order_paths,
)


def _parsed(order_number="SO-001", confidence=0.9):
    return ParsedOrder(
        order_number=order_number,
        customer_name="华东机械",
        total_amount=2870.0,
        items=[OrderItem(material_name="轴承", specification="6200",
                         quantity=100, unit="套", unit_price=28.7)],
        parsing_confidence=confidence,
    )


class ParsedOrderFromResponseTests(unittest.TestCase):
    """编排器响应 → ParsedOrder 的取值口径。"""

    def test_pydantic_object_shape_is_supported(self):
        """**回归断言**：真实编排器的返回形状。

        编排器返回 ``FinalOrderResult`` 实例而非 dict，这里必须能取出
        ``parsed_order``，且**不得**抛 AttributeError。
        """
        parsed = _parsed()
        raw = {
            "success": True,
            "final_result": FinalOrderResult(
                status=OrderStatus.COMPLETED, parsed_order=parsed, message="ok"),
            "usage": {"total_tokens": 100},
        }
        self.assertIs(parsed_order_from_response(raw), parsed)

    def test_dict_shape_is_supported(self):
        """dict 形状（序列化后的响应，例如从 jsonl 回放）同样支持。"""
        raw = {
            "success": True,
            "final_result": {"parsed_order": _parsed().model_dump()},
        }
        result = parsed_order_from_response(raw)
        self.assertIsInstance(result, ParsedOrder)
        self.assertEqual(result.order_number, "SO-001")
        self.assertEqual(len(result.items), 1)

    def test_missing_final_result_returns_none(self):
        """失败样本：没有 ``final_result`` 键 → 返回 None，由调用方记为失败。"""
        self.assertIsNone(parsed_order_from_response({"success": False}))
        self.assertIsNone(parsed_order_from_response({}))

    def test_none_final_result_returns_none(self):
        """显式 None（抽取阶段就失败）不能抛异常。"""
        self.assertIsNone(parsed_order_from_response({"final_result": None}))

    def test_pydantic_object_without_parsed_order_returns_none(self):
        """编排器跑了但没产出解析结果（如提前风控拦截）→ None。"""
        raw = {"final_result": FinalOrderResult(
            status=OrderStatus.NEEDS_CONFIRMATION, parsed_order=None)}
        self.assertIsNone(parsed_order_from_response(raw))

    def test_two_shapes_agree(self):
        """两种形状必须给出**等价的**解析结果，否则线上/回放会不一致。"""
        parsed = _parsed(order_number="SO-777")
        object_result = parsed_order_from_response(
            {"final_result": FinalOrderResult(
                status=OrderStatus.COMPLETED, parsed_order=parsed)})
        dict_result = parsed_order_from_response(
            {"final_result": {"parsed_order": parsed.model_dump()}})
        self.assertEqual(object_result.order_number, dict_result.order_number)
        self.assertEqual(object_result.total_amount, dict_result.total_amount)
        self.assertEqual(object_result.items[0].quantity, dict_result.items[0].quantity)

    def test_bug_shape_would_have_raised(self):
        """把当年的错误写法固化下来，说明它为什么错。

        若 ``final_result`` 真是 dict，``.get`` 可用；但它是 pydantic 对象。
        本测试断言「对象形状没有 ``get`` 方法」，从而证明旧写法必然抛错。
        """
        final_result = FinalOrderResult(
            status=OrderStatus.COMPLETED, parsed_order=_parsed())
        self.assertFalse(hasattr(final_result, "get"))
        with self.assertRaises(AttributeError):
            final_result.get("parsed_order")  # type: ignore[attr-defined]


class CategoryTests(unittest.TestCase):
    def test_strips_trailing_index(self):
        from pathlib import Path
        self.assertEqual(_category(Path("mfg_auto_approve_0009.xlsx")), "mfg_auto_approve")
        self.assertEqual(_category(Path("mfg_manual_review_0071.xlsx")), "mfg_manual_review")
        self.assertEqual(_category(Path("cord_0001.xlsx")), "cord")


class SamplingStrategyTests(unittest.TestCase):
    """抽样策略：**默认必须分层**，否则样本只覆盖单一业务场景。"""

    def test_head_takes_filename_order(self):
        """``head`` 复现旧行为：取排序后前 N 份（即只有同一类业务场景）。"""
        paths = select_order_paths(3, "head")
        self.assertEqual(len(paths), 3)
        self.assertEqual(len({_category(p) for p in paths}), 1)

    def test_stratified_covers_every_category_at_small_limit(self):
        """**核心断言**：limit=3 必须覆盖全部三个业务场景。

        这正是旧实现的缺陷所在——旧实现按文件名取前 3 份，三份全来自
        ``mfg_auto_approve``，结论无法覆盖另外两类场景。
        """
        paths = select_order_paths(3, "stratified")
        self.assertEqual(len(paths), 3)
        self.assertEqual(
            {_category(p) for p in paths},
            {"mfg_auto_approve", "mfg_auto_correct", "mfg_manual_review"},
        )

    def test_stratified_balances_across_categories(self):
        """limit=6 → 每档恰好 2 份。"""
        paths = select_order_paths(6, "stratified")
        counts: dict = {}
        for path in paths:
            counts[_category(path)] = counts.get(_category(path), 0) + 1
        self.assertEqual(counts, {
            "mfg_auto_approve": 2, "mfg_auto_correct": 2, "mfg_manual_review": 2})

    def test_stratified_is_deterministic(self):
        """同一 limit 必须给出**同一份**样本集合，否则结果不可复现。"""
        self.assertEqual(select_order_paths(7, "stratified"),
                         select_order_paths(7, "stratified"))

    def test_stratified_respects_limit(self):
        for limit in (1, 2, 5, 11):
            self.assertEqual(len(select_order_paths(limit, "stratified")), limit)

    def test_stratified_no_duplicates(self):
        paths = select_order_paths(12, "stratified")
        self.assertEqual(len(paths), len(set(paths)))


class RebuildFromRowsTests(unittest.TestCase):
    """断点重算：部分完成的运行也必须能出报告，且**必须标记为部分**。"""

    def _write_rows(self, directory, rows):
        import json
        from pathlib import Path
        path = Path(directory) / "rows.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                        encoding="utf-8")
        return path

    def _row(self, method, doc_id, category, matched=1, total=1, tokens=100):
        return {
            "document_id": doc_id, "category": category, "method": method,
            "error": None,
            "usage": {"prompt_tokens": tokens, "completion_tokens": 0,
                      "total_tokens": tokens},
            "calls": 1, "latency_ms": 10.0,
            "evidence_chain": [{"a": 1}] if method == "veap" else [],
            "score": {
                "order_fields": {"order_number": {"matched": matched, "total": total}},
                "item_fields": {"material_name": {"matched": matched, "total": total}},
                "items_expected": 1, "items_predicted": 1,
            },
        }

    def test_load_rows_skips_blank_lines(self):
        import tempfile
        from pathlib import Path
        from scripts.baseline_comparison import load_rows
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text('{"a":1}\n\n{"a":2}\n', encoding="utf-8")
            self.assertEqual([r["a"] for r in load_rows(path)], [1, 2])

    def test_cases_from_rows_dedupes_and_keeps_order(self):
        from scripts.baseline_comparison import cases_from_rows
        rows = [self._row("veap", "d1", "easy"), self._row("mad", "d1", "easy"),
                self._row("veap", "d2", "hard")]
        cases = cases_from_rows(rows)
        self.assertEqual([c["document_id"] for c in cases], ["d1", "d2"])
        self.assertEqual(cases[1]["category"], "hard")

    def test_partial_run_is_flagged(self):
        """**核心断言**：行数不足时必须写 `partial: true` 并在报告顶部加警告。

        若缺了这个标记，一个只跑了 1/3 的实验会生成一张**看起来完整**的表格，
        而判定会被当成最终结论——这是比数字算错更危险的失效方式。
        """
        import json
        import tempfile
        from pathlib import Path
        from scripts.baseline_comparison import rebuild_from_rows

        with tempfile.TemporaryDirectory() as tmp:
            # 2 个样本 × 2 方法 = 4 行才算完整，这里只有 3 行
            rows = [self._row("veap", "d1", "easy"), self._row("mad", "d1", "easy"),
                    self._row("veap", "d2", "hard")]
            path = self._write_rows(tmp, rows)
            self.assertEqual(rebuild_from_rows(path), 0)
            payload = json.loads((Path(tmp) / "summary.json").read_text(encoding="utf-8"))
            self.assertTrue(payload["partial"])
            self.assertEqual((payload["rows"], payload["expected_rows"]), (3, 4))
            markdown = (Path(tmp) / "summary.md").read_text(encoding="utf-8")
            self.assertIn("部分结果", markdown)
            self.assertIn("不可当作最终结论", markdown)

    def test_complete_run_is_not_flagged(self):
        import json
        import tempfile
        from pathlib import Path
        from scripts.baseline_comparison import rebuild_from_rows

        with tempfile.TemporaryDirectory() as tmp:
            rows = [self._row("veap", "d1", "easy"), self._row("mad", "d1", "easy")]
            path = self._write_rows(tmp, rows)
            rebuild_from_rows(path)
            payload = json.loads((Path(tmp) / "summary.json").read_text(encoding="utf-8"))
            self.assertFalse(payload["partial"])
            self.assertNotIn("部分结果",
                             (Path(tmp) / "summary.md").read_text(encoding="utf-8"))

    def test_empty_rows_is_an_error(self):
        import tempfile
        from pathlib import Path
        from scripts.baseline_comparison import rebuild_from_rows

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text("", encoding="utf-8")
            self.assertEqual(rebuild_from_rows(path), 1)
        self.assertEqual(rebuild_from_rows(Path(tmp) / "missing.jsonl"), 1)

    def test_model_read_from_nested_model_config(self):
        """模型名在 `model_config.model`，不是顶层 `model`（写错会静默变 unknown）。"""
        import json
        import tempfile
        from pathlib import Path
        from scripts.baseline_comparison import rebuild_from_rows

        with tempfile.TemporaryDirectory() as tmp:
            rows = [self._row("veap", "d1", "easy"), self._row("mad", "d1", "easy")]
            path = self._write_rows(tmp, rows)
            (Path(tmp) / "run_manifest.json").write_text(json.dumps({
                "run_identity": {
                    "model_config": {"model": "qwen3.7-plus"},
                    "evaluation_as_of": "2026-10-01",
                    "sampling_strategy": "stratified",
                }
            }), encoding="utf-8")
            rebuild_from_rows(path)
            markdown = (Path(tmp) / "summary.md").read_text(encoding="utf-8")
            self.assertIn("qwen3.7-plus", markdown)
            self.assertNotIn("`unknown`", markdown)


if __name__ == "__main__":
    unittest.main()
