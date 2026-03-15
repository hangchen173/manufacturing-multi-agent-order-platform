#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import ModelType, SeverityLevel, IssueType, DEFAULT_CONFIDENCE_THRESHOLD
from core.exceptions import AgentBaseException, ParserException, MatchingException, RiskControlException
from config import Config

def test_constants():
    print('=== 测试常量模块 ===')
    print(f'ModelType.QWEN_MAX: {ModelType.QWEN_MAX.value}')
    print(f'SeverityLevel.HIGH: {SeverityLevel.HIGH.value}')
    print(f'IssueType.LOW_CONFIDENCE: {IssueType.LOW_CONFIDENCE.value}')
    print(f'DEFAULT_CONFIDENCE_THRESHOLD: {DEFAULT_CONFIDENCE_THRESHOLD}')
    print('✅ 常量模块测试通过\n')

def test_exceptions():
    print('=== 测试异常模块 ===')
    try:
        raise ParserException('测试解析异常', agent_name='ParserAgent', details={'key': 'value'})
    except AgentBaseException as e:
        print(f'异常类型: {type(e).__name__}')
        print(f'异常消息: {e.message}')
        print(f'Agent名称: {e.agent_name}')
        print(f'详细信息: {e.details}')
    print('✅ 异常模块测试通过\n')

def test_config():
    print('=== 测试配置模块 ===')
    config = Config()
    print(f'API Key已配置: {bool(config.model.api_key)}')
    print(f'Max Model: {config.model.max_model}')
    print(f'Plus Model: {config.model.plus_model}')
    print(f'VL Model: {config.model.vl_model}')
    print('✅ 配置模块测试通过\n')

def test_base_agent():
    print('=== 测试 BaseAgent ===')
    from core.agents.base_agent import BaseAgent
    from config import Config
    
    class TestAgent(BaseAgent):
        def run(self, input_data):
            return {"success": True}
    
    agent = TestAgent(config=Config())
    print(f'Agent名称: {agent.name}')
    agent.log_info('测试日志信息')
    result = agent.run({})
    print(f'运行结果: {result}')
    print('✅ BaseAgent测试通过\n')

def test_imports():
    print('=== 测试所有导入 ===')
    from core.agents import ParserAgent, MatchingAgent, RiskControlAgent
    from core.models import OrderStatus, ParsedOrder, MatchedOrder, RiskCheckResult
    from core.utils.order_manager import OrderManager
    print('✅ 所有导入测试通过\n')

if __name__ == '__main__':
    test_constants()
    test_exceptions()
    test_config()
    test_base_agent()
    test_imports()
    print('=' * 50)
    print('🎉 所有测试通过！代码结构优化成功！')
    print('=' * 50)
