"""反馈媒介两臂的单变量守卫。

新颖性判决实验（paper/06_NOVELTY_EXPERIMENT.md）把「反证媒介」当作唯一自变量：
Arm B 给 locator + 原文真实值，Arm A 只给「哪一项的哪个字段不一致」的措辞。
一旦 Arm A 的输出里漏进坐标或原文值，两臂就不再可比，整个实验作废。
这个文件就是防止那种泄漏的自动化闸门。
"""
import unittest

from application.protocol import (
    FEEDBACK_MODES,
    build_counter_evidence_feedback,
    challenge_evidence,
)
from domain.messages import AgentMessage, Evidence, Performative

SHEET = "采购订单"
ROW = 17
COLUMN = 5
GOLD_VALUE = 100
WRONG_VALUE = 98765

#: Arm A 输出中一律不得出现的字符串：坐标、工作表名、原文真实值、验证者措辞骨架。
LOCATOR_AND_VALUE_TOKENS = (
    SHEET,
    f"第 {ROW} 行",
    f"第 {COLUMN} 列",
    str(GOLD_VALUE),
    str(WRONG_VALUE),
    "原单元格",
    "反证位置",
)


def _cell_challenge() -> AgentMessage:
    """一条形态与 GroundingVerifier._verify_against_cells 完全一致的单元格挑战。"""
    return AgentMessage(
        order_id="order-1",
        task_id="task-1",
        sender="grounding_verifier",
        performative=Performative.CHALLENGE,
        subject={"claim_subject": "item[2].quantity", "item_index": 2, "field": "quantity"},
        payload={
            "reason": (
                f"第 3 项 quantity 与工作表 {SHEET} 第 {ROW} 行对应列不一致："
                f"原单元格为 {GOLD_VALUE!r}，抽取为 {WRONG_VALUE!r}。"
            ),
            "item_index": 2,
            "field": "quantity",
        },
        evidence=challenge_evidence(
            subject="item[2].quantity",
            locator={"kind": "cell", "sheet": SHEET, "row": ROW, "column": COLUMN},
            expected=WRONG_VALUE,
            actual=GOLD_VALUE,
        ),
    )


def _text_challenge() -> AgentMessage:
    """文本路径的挑战：验证者只能给出片段，没有行列坐标。"""
    return AgentMessage(
        order_id="order-1",
        task_id="task-1",
        sender="grounding_verifier",
        performative=Performative.CHALLENGE,
        subject={"claim_subject": "item[0].material_name", "item_index": 0, "field": "material_name"},
        payload={"reason": "第 1 行物料名称「不存在的物料」无法在原文中定位",
                 "item_index": 0, "field": "material_name"},
        evidence=[Evidence(kind="source_span",
                           locator={"kind": "span", "text": "不存在的物料"},
                           value=None, reproducible=True)],
    )


def _order_level_challenge() -> AgentMessage:
    """订单级挑战：没有 item_index，措辞必须仍可读。"""
    return AgentMessage(
        order_id="order-1",
        task_id="task-1",
        sender="grounding_verifier",
        performative=Performative.CHALLENGE,
        subject={"claim_subject": "order.item_count"},
        payload={"reason": "订单明细数量不一致", "field": "item_count"},
        evidence=[Evidence(kind="rule_id", locator={"rule": "non_empty_items"},
                           value=0, reproducible=True)],
    )


class FeedbackModeTests(unittest.TestCase):
    def test_supported_modes_are_exactly_the_two_arms(self):
        self.assertEqual(FEEDBACK_MODES, ("locator", "natural_language"))

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            build_counter_evidence_feedback([_cell_challenge()], mode="hybrid")

    def test_locator_mode_carries_locator_and_source_value(self):
        feedback = build_counter_evidence_feedback([_cell_challenge()], mode="locator")

        self.assertIn(SHEET, feedback)
        self.assertIn(f"第 {ROW} 行", feedback)
        self.assertIn(f"第 {COLUMN} 列", feedback)
        self.assertIn(repr(GOLD_VALUE), feedback)

    def test_natural_language_mode_leaks_no_locator_and_no_source_value(self):
        feedback = build_counter_evidence_feedback([_cell_challenge()], mode="natural_language")

        for token in LOCATOR_AND_VALUE_TOKENS:
            self.assertNotIn(token, feedback, f"Arm A 反馈泄漏了 {token!r}：{feedback}")

    def test_natural_language_mode_still_says_which_field_is_wrong(self):
        feedback = build_counter_evidence_feedback([_cell_challenge()], mode="natural_language")

        self.assertIn("第 3 项", feedback)
        self.assertIn("quantity", feedback)

    def test_two_arms_differ_only_in_the_evidence_medium(self):
        challenge = [_cell_challenge()]
        arm_b = build_counter_evidence_feedback(challenge, mode="locator")
        arm_a = build_counter_evidence_feedback(challenge, mode="natural_language")

        # 两臂都必须指出同一个字段，差异只应出现在「给出多少可核查信息」上。
        self.assertNotEqual(arm_a, arm_b)
        self.assertIn("quantity", arm_a)
        self.assertIn("quantity", arm_b)
        # Arm B 是 Arm A 的超集：它额外给出坐标与原文值，而不是换一套说法。
        self.assertGreater(len(arm_b), len(arm_a))

    def test_default_mode_is_locator_so_baseline_semantics_are_unchanged(self):
        challenge = [_cell_challenge()]

        self.assertEqual(
            build_counter_evidence_feedback(challenge),
            build_counter_evidence_feedback(challenge, mode="locator"),
        )

    def test_text_path_challenge_stays_locator_free_in_arm_a(self):
        feedback = build_counter_evidence_feedback([_text_challenge()], mode="natural_language")

        self.assertNotIn("不存在的物料", feedback)
        self.assertIn("material_name", feedback)

    def test_order_level_challenge_has_readable_wording_in_both_arms(self):
        challenge = [_order_level_challenge()]

        locator_feedback = build_counter_evidence_feedback(challenge, mode="locator")
        natural_feedback = build_counter_evidence_feedback(challenge, mode="natural_language")

        # locator 模式沿用验证者措辞 + 规则定位符；natural_language 模式自行组织措辞。
        self.assertIn("订单明细数量不一致", locator_feedback)
        self.assertIn("non_empty_items", locator_feedback)
        self.assertIn("item_count", natural_feedback)
        self.assertTrue(natural_feedback.strip())

    def test_unreproducible_evidence_is_never_fed_back_in_locator_mode(self):
        message = _cell_challenge()
        message.evidence[0].reproducible = False

        feedback = build_counter_evidence_feedback([message], mode="locator")

        self.assertNotIn("反证位置", feedback)
        self.assertIn("quantity", feedback)


if __name__ == "__main__":
    unittest.main()
