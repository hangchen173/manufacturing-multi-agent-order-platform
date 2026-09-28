"""Supervisor Agent：DAG 拆解、任务分配、并行调度、预算控制、重试与降级。

**唯一有权创建/取消任务的角色**。它把一张订单编译成依赖图，按阶段推进订单状态，
并在抽取环节执行对抗协议（PROPOSE → CHALLENGE → 带反证重抽 → 争议升级）。

Agent 之间零直接调用：Supervisor 只做两件事——把上下文切片喂给 Agent、
把 Agent 产出的消息写回黑板。
"""
from __future__ import annotations

import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor
from threading import Semaphore
from typing import Any, Callable, Dict, List, Optional, Tuple

from application.blackboard.blackboard import Blackboard, record
from application.pipeline.stages import TaskNodeExecutor
from application.protocol.adversarial import build_counter_evidence_feedback
from application.protocol.budget import Budget, BudgetExhausted
from domain.agent_roles import AgentRole
from domain.messages import AgentMessage, Performative
from domain.models import OrderStatus
from domain.tasks import Task, TaskGraph, TaskStatus

STAGE_STATUS = {
    "parse": OrderStatus.PARSING,
    "match": OrderStatus.MATCHING,
    "risk": OrderStatus.RISK_CHECKING,
}
STAGE_REASON = {
    "parse": "parser_started",
    "match": "matching_started",
    "risk": "risk_check_started",
}

#: 抽取重抽的最大次数（与旧 MAX_PARSING_ATTEMPTS 对齐）
MAX_EXTRACTION_ATTEMPTS = 2

LLM_ROLES = {AgentRole.EXTRACTOR, AgentRole.REVIEW_ASSISTANT}


class Supervisor:
    def __init__(
        self,
        *,
        agents: Dict[AgentRole, Any],
        order_manager: Any = None,
        catalog: Optional[List[Dict[str, Any]]] = None,
        reference_date: Optional[str] = None,
        max_tokens: int = 200_000,
        max_llm_calls: int = 12,
        llm_concurrency: int = 4,
        worker_count: int = 8,
        rng_seed: Optional[int] = None,
        stage_observer: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        self.agents = agents
        self.order_manager = order_manager
        self.catalog = catalog or []
        self.reference_date = reference_date
        self._logger = logging.getLogger(self.__class__.__name__)
        self.max_tokens = max_tokens
        self.max_llm_calls = max_llm_calls
        self._llm_semaphore = Semaphore(max(1, llm_concurrency))
        self._worker_count = max(1, worker_count)
        self._stage_observer = stage_observer
        self.executor = TaskNodeExecutor(
            agents, llm_semaphore=self._llm_semaphore, order_manager=order_manager,
        )
        # 仅用于 V2「调度顺序无关性」验证：设定种子后打乱组内就绪任务顺序。
        self._rng = random.Random(rng_seed) if rng_seed is not None else None

    # ================================================================== entry
    def run(self, order_id: str, document_ir: Dict[str, Any],
            image_path: Optional[str] = None, image_type: str = "jpeg") -> Dict[str, Any]:
        board = Blackboard(order_id)
        board.set_fact("document_ir", document_ir)
        board.set_control("catalog", self.catalog)
        if self.reference_date:
            board.set_control("reference_date", self.reference_date)

        budget = Budget(order_id=order_id, max_tokens=self.max_tokens,
                        max_llm_calls=self.max_llm_calls)
        graph = TaskGraph(order_id=order_id)
        diagnostics: Dict[str, Any] = {}

        self._bind(board, budget)

        try:
            parse_state = self._run_parse_stage(board, graph, budget, document_ir,
                                                image_path, image_type)
            diagnostics["parse"] = parse_state
            if not parse_state["items"]:
                return self._failure(board, graph, "未从订单中解析出任何物料明细，已拒绝处理",
                                     diagnostics)

            match_state = self._run_match_stage(board, graph, budget, parse_state)
            diagnostics["match"] = {"item_count": len(match_state["items"])}

            risk_state = self._run_risk_stage(board, graph, budget, match_state, parse_state)
            diagnostics["risk"] = {"issue_count": len(risk_state["issues"])}

            verdict = self._run_adjudicate_stage(board, graph, budget)
            diagnostics["adjudicate"] = {
                "action": verdict.get("action"),
                "needs_confirmation": verdict.get("needs_confirmation"),
                "reason_chain": verdict.get("reason_chain"),
            }

            return {
                "success": True,
                "order_id": order_id,
                "verdict": verdict,
                "message": "订单处理完成",
                "usage": self._usage(board),
                "diagnostics": diagnostics,
                "blackboard": board,
                "task_graph": graph,
            }
        except BudgetExhausted as exc:
            board.set_control("escalation", {"reason": exc.reason, "snapshot": exc.snapshot})
            self._persist(board, graph)
            return self._failure(board, graph, f"预算耗尽，已升级人工处理：{exc.reason}", diagnostics)
        except Exception as exc:  # noqa: BLE001 - Supervisor 是最后一道兜底
            self._logger.exception("订单 %s 处理失败", order_id)
            return self._failure(board, graph, f"订单处理失败: {exc}", diagnostics)

    def _failure(self, board: Blackboard, graph: TaskGraph, message: str,
                 diagnostics: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "order_id": board.order_id,
            "verdict": None,
            "message": message,
            "usage": self._usage(board),
            "diagnostics": diagnostics,
            "blackboard": board,
            "task_graph": graph,
        }

    def _bind(self, board: Blackboard, budget: Budget) -> None:
        for agent in self.agents.values():
            agent.blackboard = board
            agent.budget = budget

    @staticmethod
    def _usage(board: Blackboard) -> Dict[str, int]:
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                 "attempted_calls": 0, "reported_calls": 0}
        for message in board.messages():
            message_usage = (message.payload or {}).get("usage")
            if isinstance(message_usage, dict):
                for key in usage:
                    usage[key] += int(message_usage.get(key) or 0)
        return usage

    # ================================================================== DAG runner
    def _execute_task(self, task: Task, budget: Budget) -> List[AgentMessage]:
        result = self.executor.execute(task, budget)
        if not result.success:
            raise result.error if result.error else RuntimeError(
                f"任务 {task.task_id} 执行失败"
            )
        return result.messages

    def _ordered(self, tasks: List[Task]) -> List[Task]:
        """按优先级排序；若设定了种子则再打乱同优先级任务，用于 V2 顺序无关性验证。"""
        ordered = sorted(tasks, key=lambda task: -task.priority)
        if self._rng is not None:
            self._rng.shuffle(ordered)
        return ordered

    def _run_group(self, tasks: List[Task], budget: Budget) -> Dict[str, List[AgentMessage]]:
        """并行执行一组无相互依赖的任务，消息按 task_id 归集。"""
        if not tasks:
            return {}
        ordered = self._ordered(tasks)
        results: Dict[str, List[AgentMessage]] = {}
        if len(ordered) == 1:
            results[ordered[0].task_id] = self._execute_task(ordered[0], budget)
            return results
        with ThreadPoolExecutor(max_workers=min(self._worker_count, len(ordered))) as pool:
            futures = {
                pool.submit(self._execute_task, task, budget): task for task in ordered
            }
            for future, task in futures.items():
                results[task.task_id] = future.result()
        return results

    @staticmethod
    def _publish(board: Blackboard, grouped: Dict[str, List[AgentMessage]]) -> List[AgentMessage]:
        flat: List[AgentMessage] = []
        for messages in grouped.values():
            for message in messages:
                record(board, message)
                flat.append(message)
        return flat

    # ================================================================== parse
    def _run_parse_stage(self, board: Blackboard, graph: TaskGraph, budget: Budget,
                         document_ir: Dict[str, Any], image_path: Optional[str],
                         image_type: str) -> Dict[str, Any]:
        self._enter_stage(board, "parse")

        scout_task = graph.add(Task(order_id=board.order_id, agent=AgentRole.STRUCTURE_SCOUT.value,
                                    stage="parse", slice_key={}))
        scout_messages = self._publish(
            board, {scout_task.task_id: self._execute_task(scout_task, budget)}
        )
        regions, document_type = self._regions_from(scout_messages, image_path)
        board.set_control("regions", regions)

        if not regions:
            return {"items": [], "order_facts": {}, "regions": [], "document_type": document_type,
                    "challenges": [], "parsing_issues": [], "attempts": 0,
                    "verifications": [], "model_calls": [], "item_regions": []}

        items, order_facts, item_regions = self._extract_and_verify(
            board, graph, budget, regions, image_path, image_type, scout_task.task_id,
        )

        board.set_control("parsed_order", {"order_facts": order_facts, "items": items})
        board.set_fact("order_facts", order_facts)
        board.set_fact("items", items)

        state = board.control("parse_state") or {}
        self._persist(board, graph)
        state.update({"items": items, "order_facts": order_facts, "regions": regions,
                      "document_type": document_type, "item_regions": item_regions,
                      "model_calls": self._model_calls(board)})
        return state

    def _extract_and_verify(self, board: Blackboard, graph: TaskGraph, budget: Budget,
                            regions: List[Dict[str, Any]], image_path: Optional[str],
                            image_type: str, scout_task_id: str
                            ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[int]]:
        attempts = 0
        feedback: Optional[str] = None
        items: List[Dict[str, Any]] = []
        order_facts: Dict[str, Any] = {}
        item_regions: List[int] = []
        challenges: List[AgentMessage] = []
        verifications: List[Dict[str, Any]] = []

        while attempts < MAX_EXTRACTION_ATTEMPTS:
            attempts += 1
            extract_tasks = [
                graph.add(Task(
                    order_id=board.order_id, agent=AgentRole.EXTRACTOR.value, stage="parse",
                    slice_key={"region": region, "image_path": image_path,
                               "image_type": image_type, "feedback": feedback},
                    depends_on=[scout_task_id], max_attempts=2,
                ))
                for region in regions
            ]
            extract_messages = self._publish(board, self._run_group(extract_tasks, budget))
            items, order_facts, item_regions = self._collect_extraction(extract_messages, regions)

            challenges, verifications = self._verify(board, graph, budget, items, item_regions)
            if not challenges:
                break
            feedback = build_counter_evidence_feedback(challenges)

        parsing_issues = self._parsing_issues(challenges)
        board.set_control("parsing_issues", parsing_issues)
        board.set_control("extraction_attempts", attempts)
        board.set_control("parse_state", {
            "attempts": attempts,
            "challenges": [self._challenge_reason(message) for message in challenges],
            "parsing_issues": parsing_issues,
            "verifications": verifications,
            "self_correction": {
                "attempts": attempts,
                "resolved": not challenges,
                "remaining_problems": [self._challenge_reason(message) for message in challenges],
            },
        })
        return items, order_facts, item_regions

    @staticmethod
    def _regions_from(messages: List[AgentMessage], image_path: Optional[str]
                      ) -> Tuple[List[Dict[str, Any]], str]:
        if image_path:
            return [{"kind": "image"}], "image"
        for message in messages:
            if message.sender == AgentRole.STRUCTURE_SCOUT.value:
                if message.performative == Performative.REFUSE:
                    return [], (message.payload or {}).get("document_type") or "unknown"
                return ((message.payload or {}).get("regions") or [],
                        (message.payload or {}).get("document_type") or "unknown")
        return [], "unknown"

    @staticmethod
    def _collect_extraction(messages: List[AgentMessage], regions: List[Dict[str, Any]]
                            ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[int]]:
        by_region: Dict[str, Dict[str, Any]] = {}
        order_facts: Dict[str, Any] = {}
        for message in messages:
            if message.sender != AgentRole.EXTRACTOR.value:
                continue
            if message.performative != Performative.PROPOSE:
                continue
            parsed = (message.payload or {}).get("parsed_order")
            if parsed is None:
                continue
            key = json.dumps((message.payload or {}).get("region"), sort_keys=True, ensure_ascii=False)
            by_region.setdefault(key, parsed)
            if not order_facts:
                order_facts = {
                    "order_number": parsed.get("order_number"),
                    "customer_name": parsed.get("customer_name"),
                    "total_amount": parsed.get("total_amount"),
                    "parsing_confidence": parsed.get("parsing_confidence"),
                }

        items: List[Dict[str, Any]] = []
        item_regions: List[int] = []
        for region_index, region in enumerate(regions):
            key = json.dumps(region, sort_keys=True, ensure_ascii=False)
            parsed = by_region.get(key)
            if not parsed:
                continue
            for item in parsed.get("items") or []:
                items.append(item)
                item_regions.append(region_index)
        return items, order_facts, item_regions

    def _verify(self, board: Blackboard, graph: TaskGraph, budget: Budget,
                items: List[Dict[str, Any]], item_regions: List[int]
                ) -> Tuple[List[AgentMessage], List[Dict[str, Any]]]:
        regions = board.control("regions") or []
        tasks = [
            graph.add(Task(
                order_id=board.order_id, agent=AgentRole.GROUNDING_VERIFIER.value, stage="parse",
                slice_key={
                    "item_index": index, "subject": f"item[{index}]",
                    "region": regions[item_regions[index]] if item_regions[index] < len(regions) else None,
                },
            ))
            for index in range(len(items))
        ]
        tasks.append(graph.add(Task(
            order_id=board.order_id, agent=AgentRole.GROUNDING_VERIFIER.value, stage="parse",
            slice_key={"item_index": None, "subject": "order",
                       "parsed_order": {"items": items},
                       "region": regions[0] if regions else None},
        )))

        messages = self._publish(board, self._run_group(tasks, budget))
        challenges = [message for message in messages
                      if message.performative == Performative.CHALLENGE]
        verifications = [
            {"subject": message.subject.get("claim_subject"),
             "performative": message.performative.value,
             "payload": message.payload}
            for message in messages
            if message.sender == AgentRole.GROUNDING_VERIFIER.value
        ]
        return challenges, verifications

    @staticmethod
    def _challenge_reason(message: AgentMessage) -> Dict[str, Any]:
        return {
            "subject": message.subject.get("claim_subject"),
            "item_index": message.subject.get("item_index"),
            "field": message.subject.get("field"),
            "reason": (message.payload or {}).get("reason"),
        }

    @staticmethod
    def _parsing_issues(challenges: List[AgentMessage]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        for message in challenges:
            subject = str(message.subject.get("claim_subject") or "")
            item_index = message.subject.get("item_index")
            if subject == "order.item_count":
                item_index = None
            issues.append({
                "item_index": item_index,
                "description": (message.payload or {}).get("reason") or subject,
            })
        return issues

    # ================================================================== match
    def _run_match_stage(self, board: Blackboard, graph: TaskGraph, budget: Budget,
                         parse_state: Dict[str, Any]) -> Dict[str, Any]:
        self._enter_stage(board, "match")
        items = parse_state["items"]

        catalog_tasks = [
            graph.add(Task(order_id=board.order_id, agent=AgentRole.CATALOG_MATCHER.value,
                           stage="match", slice_key={"item_index": index}))
            for index in range(len(items))
        ]
        semantic_tasks = [
            graph.add(Task(order_id=board.order_id, agent=AgentRole.SEMANTIC_MATCHER.value,
                           stage="match", slice_key={"item_index": index}))
            for index in range(len(items))
        ]
        catalog_messages = self._publish(board, self._run_group(catalog_tasks, budget))
        semantic_messages = self._publish(board, self._run_group(semantic_tasks, budget))

        for index in range(len(items)):
            board.set_control(f"candidates:{index}", {
                "catalog": self._payload_for(catalog_messages, index),
                "semantic": self._payload_for(semantic_messages, index),
            })

        disambiguate_tasks = [
            graph.add(Task(order_id=board.order_id, agent=AgentRole.DISAMBIGUATOR.value,
                           stage="match", slice_key={"item_index": index}))
            for index in range(len(items))
        ]
        decision_messages = self._publish(
            board, self._run_group(disambiguate_tasks, budget)
        )

        resolved_items = [
            self._resolve_item(item, self._decision_for(decision_messages, index))
            for index, item in enumerate(items)
        ]
        board.set_fact("items", resolved_items)
        self._persist(board, graph)
        return {"items": resolved_items}

    @staticmethod
    def _payload_for(messages: List[AgentMessage], index: int) -> Dict[str, Any]:
        for message in messages:
            if message.subject.get("item_index") == index:
                return dict(message.payload or {})
        return {}

    @staticmethod
    def _decision_for(messages: List[AgentMessage], index: int) -> Dict[str, Any]:
        for message in messages:
            if message.sender == AgentRole.DISAMBIGUATOR.value and \
                    message.subject.get("item_index") == index:
                return dict(message.payload or {})
        return {"accepted": None, "match_score": 0.0, "candidate_skus": [],
                "rejection_reason": "消歧未产出结论"}

    @staticmethod
    def _resolve_item(item: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
        accepted = decision.get("accepted") or {}
        resolved = dict(item)
        resolved.update({
            "sku_code": accepted.get("sku_code"),
            "matched_material_name": accepted.get("matched_material_name"),
            "matched_specification": accepted.get("matched_specification"),
            "match_score": float(decision.get("match_score") or 0.0),
            "candidate_skus": list(decision.get("candidate_skus") or []),
            "match_basis": accepted.get("basis"),
            "rejection_reason": decision.get("rejection_reason"),
        })
        return resolved

    # ================================================================== risk
    def _run_risk_stage(self, board: Blackboard, graph: TaskGraph, budget: Budget,
                        match_state: Dict[str, Any], parse_state: Dict[str, Any]) -> Dict[str, Any]:
        self._enter_stage(board, "risk")
        items = match_state["items"]
        grounding = self._grounding_by_item(parse_state, items)
        for index, item in enumerate(items):
            item["_grounding"] = grounding[index]
        board.set_fact("items", items)

        policy_tasks = [
            graph.add(Task(order_id=board.order_id, agent=AgentRole.POLICY_RISK.value,
                           stage="risk", slice_key={"item_index": index}))
            for index in range(len(items))
        ]
        schedule_tasks = [
            graph.add(Task(order_id=board.order_id, agent=AgentRole.SCHEDULE_RISK.value,
                           stage="risk", slice_key={"item_index": index}))
            for index in range(len(items))
        ]
        order_policy_task = graph.add(Task(
            order_id=board.order_id, agent=AgentRole.POLICY_RISK.value, stage="risk",
            slice_key={"item_index": None},
        ))

        policy_messages = self._publish(board, self._run_group(policy_tasks, budget))
        schedule_messages = self._publish(board, self._run_group(schedule_tasks, budget))
        order_messages = self._publish(
            board, {order_policy_task.task_id: self._execute_task(order_policy_task, budget)}
        )

        issues: List[Dict[str, Any]] = []
        for message in policy_messages + schedule_messages + order_messages:
            issues.extend((message.payload or {}).get("issues") or [])

        for problem in parse_state["parsing_issues"]:
            issues.append({
                "item_index": problem["item_index"] if problem["item_index"] is not None else -1,
                "issue_type": "unresolved_parsing_problem",
                "description": f"解析自检未解决：{problem['description']}",
                "severity": "high",
            })

        board.set_control("risk_issues", issues)
        self._persist(board, graph)
        return {"issues": issues, "grounding": grounding}

    @staticmethod
    def _grounding_by_item(parse_state: Dict[str, Any],
                           items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        challenged: Dict[int, set] = {}
        for challenge in parse_state.get("challenges") or []:
            index = challenge.get("item_index")
            if index is None:
                continue
            challenged.setdefault(index, set()).add(challenge.get("field") or "unknown")

        grounding: List[Dict[str, Any]] = []
        for index, item in enumerate(items):
            fields = [key for key in ("material_name", "specification", "quantity", "unit",
                                      "unit_price", "delivery_date")
                      if item.get(key) is not None]
            total = len(fields)
            disputed = challenged.get(index, set())
            verified = max(0, total - len(disputed))
            rate = (verified / total) if total else 1.0
            grounding.append({
                "verified": verified,
                "total": total,
                "rate": round(rate, 4),
                "disputed_fields": sorted(disputed),
            })
        return grounding

    # ================================================================== adjudicate
    def _run_adjudicate_stage(self, board: Blackboard, graph: TaskGraph,
                              budget: Budget) -> Dict[str, Any]:
        task = graph.add(Task(order_id=board.order_id, agent=AgentRole.ADJUDICATOR.value,
                              stage="adjudicate", slice_key={}))
        messages = self._publish(board, {task.task_id: self._execute_task(task, budget)})
        self._persist(board, graph)
        for message in messages:
            if message.performative == Performative.VERDICT:
                return dict(message.payload or {})
        raise RuntimeError("Adjudicator 未产出裁决")

    # ================================================================== helpers
    def _enter_stage(self, board: Blackboard, stage: str) -> None:
        if self.order_manager is None:
            return
        self.order_manager.update_order_status(
            board.order_id, STAGE_STATUS[stage], reason=STAGE_REASON[stage],
        )

    @staticmethod
    def _model_calls(board: Blackboard) -> List[Dict[str, Any]]:
        calls: List[Dict[str, Any]] = []
        for message in board.messages():
            payload = message.payload or {}
            if isinstance(payload.get("model_calls"), list):
                calls.extend(payload["model_calls"])
        return calls

    def _persist(self, board: Blackboard, graph: TaskGraph) -> None:
        if self.order_manager is None:
            return
        board.version += 1
        self.order_manager.save_blackboard(board.order_id, board.to_snapshot())
        self.order_manager.save_tasks(board.order_id, graph.to_snapshot())
        self.order_manager.record_messages(board.order_id, board.messages())
