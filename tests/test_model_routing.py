"""角色级多模型路由测试。

覆盖两种形态：

1. **单模型模式（默认）** —— 未配置任何角色级变量时，所有 LLM 角色共用 `config.model`，
   行为与改造前完全一致；
2. **多模型模式** —— 通过 `<ROLE>_MODEL` / `<ROLE>_API_KEY` / `<ROLE>_BASE_URL` 覆盖，
   缺项自动回落，从而让不同角色跑在不同厂商的模型上。

同时验证「推理控制参数按服务商分流」：DeepSeek 认 `effort`，DashScope 认
`enable_thinking`，参数名发错会被静默忽略并白烧 token。
"""
import os
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from application.agents import Extractor, ReviewAssistant
from config import Config, ModelConfig
from tests.support import OfflineFAISSManager

DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEEPSEEK_URL = "https://api.deepseek.com/v1"

#: 固定的基线环境：测试必须完全掌控这些变量，否则仓库里的 .env 会污染断言。
BASE_ENV = {
    "QWEN_API_KEY": "default-key",
    "QWEN_BASE_URL": DASHSCOPE_URL,
    "QWEN_MODEL": "qwen3.7-plus",
    "EXTRACTOR_MODEL": "",
    "EXTRACTOR_API_KEY": "",
    "EXTRACTOR_BASE_URL": "",
    "REVIEW_ASSISTANT_MODEL": "",
    "REVIEW_ASSISTANT_API_KEY": "",
    "REVIEW_ASSISTANT_BASE_URL": "",
}


@contextmanager
def _env(**overrides):
    env = dict(BASE_ENV)
    env.update(overrides)
    with patch.dict(os.environ, env, clear=False):
        yield


class SingleModelModeTests(unittest.TestCase):
    """默认形态：所有 LLM 角色共用一个模型。"""

    def test_no_role_override_keeps_every_role_on_the_default_model(self):
        with _env():
            config = Config()
            extractor_model = config.model_for("extractor")
            review_model = config.model_for("review_assistant")

        self.assertIs(extractor_model, config.model)
        self.assertIs(review_model, config.model)
        self.assertEqual(extractor_model.model, "qwen3.7-plus")

    def test_agents_share_one_client_when_no_override(self):
        with _env():
            config = Config()
            extractor = Extractor(config=config)
            assistant = ReviewAssistant(faiss_manager=OfflineFAISSManager(), config=config)
            extractor_llm = extractor._get_llm()
            assistant_llm = assistant._get_llm()

        self.assertEqual(extractor_llm.model_name, "qwen3.7-plus")
        self.assertEqual(assistant_llm.model_name, "qwen3.7-plus")
        self.assertEqual(extractor_llm.openai_api_base, assistant_llm.openai_api_base)


class MultiModelRoutingTests(unittest.TestCase):
    """多模型形态：不同角色路由到不同厂商的模型。"""

    def test_two_roles_route_to_two_different_models(self):
        with _env(
            EXTRACTOR_MODEL="deepseek-flash",
            EXTRACTOR_API_KEY="ds-key",
            EXTRACTOR_BASE_URL=DEEPSEEK_URL,
            REVIEW_ASSISTANT_MODEL="qwen3.8-max",
        ):
            config = Config()
            extractor_model = config.model_for("extractor")
            review_model = config.model_for("review_assistant")

        self.assertEqual(extractor_model.model, "deepseek-flash")
        self.assertEqual(extractor_model.api_key, "ds-key")
        self.assertEqual(extractor_model.base_url, DEEPSEEK_URL)

        self.assertEqual(review_model.model, "qwen3.8-max")
        # 只覆盖了模型名，其余字段回落到默认模型
        self.assertEqual(review_model.api_key, "default-key")
        self.assertEqual(review_model.base_url, DASHSCOPE_URL)

    def test_agents_build_clients_for_their_own_role(self):
        with _env(
            EXTRACTOR_MODEL="deepseek-flash",
            EXTRACTOR_API_KEY="ds-key",
            EXTRACTOR_BASE_URL=DEEPSEEK_URL,
            REVIEW_ASSISTANT_MODEL="qwen3.8-max",
            REVIEW_ASSISTANT_API_KEY="qw-key",
        ):
            config = Config()
            extractor_llm = Extractor(config=config)._get_llm()
            assistant_llm = ReviewAssistant(
                faiss_manager=OfflineFAISSManager(), config=config
            )._get_llm()

        self.assertEqual(extractor_llm.model_name, "deepseek-flash")
        self.assertEqual(extractor_llm.openai_api_base, DEEPSEEK_URL)
        self.assertEqual(assistant_llm.model_name, "qwen3.8-max")
        self.assertEqual(assistant_llm.openai_api_base, DASHSCOPE_URL)
        # 两个角色的客户端确实是不同的实例
        self.assertIsNot(extractor_llm, assistant_llm)

    def test_role_override_alone_is_enough_without_default_api_key(self):
        with _env(QWEN_API_KEY="", EXTRACTOR_MODEL="deepseek-flash",
                  EXTRACTOR_API_KEY="ds-key", EXTRACTOR_BASE_URL=DEEPSEEK_URL):
            config = Config()
            extractor_model = config.model_for("extractor")
            extractor_llm = Extractor(config=config)._get_llm()

        self.assertEqual(extractor_model.api_key, "ds-key")
        self.assertEqual(extractor_llm.model_name, "deepseek-flash")


class ProviderRequestBodyTests(unittest.TestCase):
    """推理控制参数必须按服务商分流，发错会被静默忽略。"""

    def test_request_body_follows_provider_host(self):
        deepseek = ModelConfig(api_key="k", base_url=DEEPSEEK_URL, model="deepseek-flash")
        qwen = ModelConfig(api_key="k", base_url=DASHSCOPE_URL, model="qwen3.8-flash")
        unknown = ModelConfig(api_key="k", base_url="https://example.com/v1", model="x")

        self.assertEqual(deepseek.request_body(), {"effort": "low"})
        self.assertEqual(qwen.request_body(), {"enable_thinking": False})
        self.assertEqual(unknown.request_body(), {})

    def test_explicit_extra_body_wins_over_detection(self):
        explicit = ModelConfig(
            api_key="k", base_url=DEEPSEEK_URL, model="deepseek-flash",
            extra_body={"effort": "max"},
        )
        self.assertEqual(explicit.request_body(), {"effort": "max"})

    def test_routed_clients_carry_provider_specific_body(self):
        with _env(
            EXTRACTOR_MODEL="deepseek-flash",
            EXTRACTOR_API_KEY="ds-key",
            EXTRACTOR_BASE_URL=DEEPSEEK_URL,
        ):
            config = Config()
            extractor_llm = Extractor(config=config)._get_llm()

        self.assertEqual(extractor_llm.model_kwargs["extra_body"], {"effort": "low"})


if __name__ == "__main__":
    unittest.main()
