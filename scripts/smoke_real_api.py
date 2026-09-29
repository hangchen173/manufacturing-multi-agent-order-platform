"""轻量真实 API 冒烟测试：DeepSeek + 阿里云百炼（总花费远低于 ¥0.5）。

只跑一条两行的小订单，端到端穿过真实「Supervisor + 11 个 Agent + 对抗协议」链路，
验证：

1. 真实模型客户端（OpenAI 兼容）可被接入且关闭思考；
2. 结构化抽取能产出合法 `ParsedOrder`；
3. 全链路（解析 → 溯源验证 → 匹配 → 消歧 → 风控 → 终裁）能给出裁决；
4. token 用量被正确记账。

用法：
    .venv/bin/python scripts/smoke_real_api.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from application.orchestrators import OrderProcessingOrchestrator  # noqa: E402
from application.services import OrderManager  # noqa: E402
from config import Config, ModelConfig  # noqa: E402
from infrastructure.document_processing import DocumentLoader  # noqa: E402
from infrastructure.repositories.memory import InMemoryOrderRepository  # noqa: E402


class StubVectorStore:
    """空召回向量库：冒烟测试只关心真实模型链路，不加载本地嵌入模型。"""

    def __init__(self, metadata):
        self.metadata = metadata

    def search(self, _query, k=3):
        return []


CATALOG = [
    {"sku_code": "SKU-001", "material_name": "螺丝", "specification": "M8",
     "unit": "个", "reference_price": 1.0, "category": "紧固件", "aliases": []},
    {"sku_code": "SKU-002", "material_name": "螺母", "specification": "M8",
     "unit": "个", "reference_price": 2.0, "category": "紧固件", "aliases": []},
]

ORDER_TEXT = "1 螺丝 M8 10 个 1.0\n2 螺母 M8 5 个 2.0"

PROVIDERS = {
    "deepseek": {
        "api_key": os.environ["DEEPSEEK_API_KEY"],
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
    },
    "aliyun": {
        "api_key": os.environ["ALIYUN_API_KEY"],
        "base_url": os.getenv("ALIYUN_BASE_URL",
                              "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "model": os.getenv("ALIYUN_MODEL", "qwen3.8-flash"),
    },
}


def run_provider(name: str, spec: dict) -> bool:
    config = Config()
    config.model.api_key = spec["api_key"]
    config.model.base_url = spec["base_url"]
    config.model.model = spec["model"]
    config.data.order_auto_archive_days = 0
    config.risk.evaluation_as_of = "2026-05-10"

    manager = OrderManager(repository=InMemoryOrderRepository(), config=config)
    orchestrator = OrderProcessingOrchestrator(
        order_manager=manager, document_loader=DocumentLoader(), config=config,
        faiss_manager=StubVectorStore(CATALOG),
    )

    print(f"\n=== {name} / {spec['model']} ===")
    started = time.perf_counter()
    try:
        result = orchestrator.process_order_from_text(ORDER_TEXT)
    except Exception as exc:  # noqa: BLE001 - 冒烟脚本需要打印真实失败原因
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return False
    elapsed = (time.perf_counter() - started) * 1000

    print(f"success={result['success']} "
          f"needs_confirmation={result.get('needs_confirmation')}")
    print(f"message={result.get('message')}")
    print(f"usage={result.get('usage')}")
    print(f"latency={elapsed:.0f} ms")

    if not result["success"]:
        print(f"diagnostics={result.get('diagnostics')}")
        return False

    decision = result["business_decision"]
    items = result["final_result"].matched_order.items
    parse = (result.get("diagnostics") or {}).get("parse") or {}
    print(f"action={decision.action.value}")
    print("matched=" + ", ".join(
        f"{entry.material_name}->{entry.sku_code}" for entry in items
    ))
    print(f"parse_attempts={parse.get('attempts')} "
          f"challenges={parse.get('challenges')}")
    return True


def run_two_model_pipeline() -> bool:
    """同一个订单、两个角色、两家模型。

    通过角色级环境变量把 Extractor 路由到 DeepSeek、ReviewAssistant 路由到阿里云，
    证明「多模型协作」不是两个独立的脚本，而是同一条协作链路上的不同角色各自选型。
    """
    os.environ["EXTRACTOR_MODEL"] = PROVIDERS["deepseek"]["model"]
    os.environ["EXTRACTOR_API_KEY"] = PROVIDERS["deepseek"]["api_key"]
    os.environ["EXTRACTOR_BASE_URL"] = PROVIDERS["deepseek"]["base_url"]
    os.environ["REVIEW_ASSISTANT_MODEL"] = PROVIDERS["aliyun"]["model"]
    os.environ["REVIEW_ASSISTANT_API_KEY"] = PROVIDERS["aliyun"]["api_key"]
    os.environ["REVIEW_ASSISTANT_BASE_URL"] = PROVIDERS["aliyun"]["base_url"]

    config = Config()
    config.data.order_auto_archive_days = 0
    config.risk.evaluation_as_of = "2026-05-10"
    # 默认模型（未做角色覆盖时使用）设为阿里云
    config.model = ModelConfig(
        api_key=PROVIDERS["aliyun"]["api_key"],
        base_url=PROVIDERS["aliyun"]["base_url"],
        model=PROVIDERS["aliyun"]["model"],
    )

    manager = OrderManager(repository=InMemoryOrderRepository(), config=config)
    orchestrator = OrderProcessingOrchestrator(
        order_manager=manager, document_loader=DocumentLoader(), config=config,
        faiss_manager=StubVectorStore(CATALOG),
    )

    print("\n=== 多模型协作：同一订单、两个角色、两家模型 ===")
    extractor_model = config.model_for("extractor")
    review_model = config.model_for("review_assistant")
    print(f"Extractor       -> {extractor_model.model} @ {extractor_model.base_url}")
    print(f"ReviewAssistant -> {review_model.model} @ {review_model.base_url}")

    started = time.perf_counter()
    try:
        result = orchestrator.process_order_from_text(ORDER_TEXT)
    except Exception as exc:  # noqa: BLE001 - 冒烟脚本需要打印真实失败原因
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return False
    elapsed = (time.perf_counter() - started) * 1000
    print(f"process success={result['success']} "
          f"needs_confirmation={result.get('needs_confirmation')} "
          f"usage={result.get('usage')} latency={elapsed:.0f} ms")

    if not result["success"] or not result.get("needs_confirmation"):
        print("订单未进入待人工确认状态，无法演示审核助手角色")
        return False

    suggestion = orchestrator.generate_review_suggestion(result["order_id"])
    print(f"review_suggestion success={suggestion['success']}")
    if not suggestion["success"]:
        print(f"message={suggestion.get('message')}")
        return False

    payload = suggestion["review_suggestion"]
    print(f"summary={payload['summary'][:120]!r}")
    print(f"references={[ref.get('sku_code') for ref in payload['references']]}")
    return True


def main() -> int:
    selected = sys.argv[1:] or [*PROVIDERS, "two-model"]
    outcomes = {}
    for name in selected:
        if name == "two-model":
            outcomes[name] = run_two_model_pipeline()
        else:
            outcomes[name] = run_provider(name, PROVIDERS[name])
    print("\n--- summary ---")
    for name, ok in outcomes.items():
        print(f"{name}: {'OK' if ok else 'FAILED'}")
    return 0 if all(outcomes.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
