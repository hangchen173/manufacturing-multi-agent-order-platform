# 从 Deepseek 迁移到 Qwen 指南

## 概述

已成功将系统从 Deepseek 模型迁移到 Qwen 系列模型，支持不同场景使用不同的最优模型。

## 模型配置

| 场景 | 使用模型 | 说明 |
|------|---------|------|
| Agent 逻辑决策、字段提取 | `qwen-max` | 最强逻辑能力，适合多 Agent 协作 |
| 通用订单解析 | `qwen-plus` | 性价比最高 |
| 图片/OCR/扫描件订单 | `qwen-vl-plus` | 视觉理解能力 |

## 主要变更

### 1. 配置文件更新 (`config.py`)

**变更前 (Deepseek):**
```python
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
```

**变更后 (Qwen):**
```python
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

QWEN_MODEL_MAX = os.getenv("QWEN_MODEL_MAX", "qwen-max")
QWEN_MODEL_PLUS = os.getenv("QWEN_MODEL_PLUS", "qwen-plus")
QWEN_MODEL_VL = os.getenv("QWEN_MODEL_VL", "qwen-vl-plus")
```

### 2. Parser Agent 重构 (`core/agents/parser_agent.py`)

**新增功能:**
- `ParserScenario` 枚举：定义三种使用场景
- 多模型支持：根据场景自动选择合适的 Qwen 模型
- 图片 OCR 支持：使用 `qwen-vl-plus` 处理图片订单
- `set_scenario()` 方法：动态切换模型

**使用示例:**
```python
from core.agents.parser_agent import ParserAgent, ParserScenario

# 通用订单解析（默认）
parser_general = ParserAgent(scenario=ParserScenario.GENERAL_PARSING)

# 逻辑决策场景
parser_logic = ParserAgent(scenario=ParserScenario.LOGIC_DECISION)

# 图片 OCR 场景
parser_vl = ParserAgent(scenario=ParserScenario.IMAGE_OCR)
result = parser_vl.run({
    "image_path": "order.jpg",
    "image_type": "jpeg"
})
```

### 3. Orchestrator 更新 (`core/orchestrator.py`)

**新增功能:**
- 自动检测文档类型
- 图片文件自动使用 `qwen-vl-plus` 处理
- 文本/PDF/Excel 使用 `qwen-plus` 处理
- 预初始化所有三种场景的 Parser Agent

### 4. 环境变量更新

**`.env` 和 `.env.example` 更新:**
```env
# 旧配置（已移除）
# DEEPSEEK_API_KEY=...
# DEEPSEEK_BASE_URL=...
# DEEPSEEK_MODEL=...

# 新配置
QWEN_API_KEY=your_qwen_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

QWEN_MODEL_MAX=qwen-max
QWEN_MODEL_PLUS=qwen-plus
QWEN_MODEL_VL=qwen-vl-plus
```

## 迁移步骤

### 1. 获取 Qwen API Key

访问 [阿里云百炼平台](https://bailian.console.aliyun.com/) 获取 API Key。

### 2. 更新环境变量

编辑 `.env` 文件：
```bash
# 删除旧的 Deepseek 配置
# 添加新的 Qwen 配置
```

### 3. 安装依赖（如有需要）

现有依赖应已足够，如遇到问题可重新安装：
```bash
pip install -r requirements.txt
```

### 4. 测试系统

```bash
# 初始化 FAISS 索引
python3 scripts/init_faiss_index.py

# 测试 API
python3 scripts/test_api.py
```

## 模型选择策略

系统会根据以下规则自动选择模型：

| 输入类型 | 使用模型 | 触发条件 |
|---------|---------|---------|
| 纯文本 | `qwen-plus` | `process_order_from_text()` |
| PDF/Excel | `qwen-plus` | `process_order_from_document()` + 非图片文件 |
| 图片 (PNG/JPG) | `qwen-vl-plus` | `process_order_from_document()` + 图片文件 |

## 注意事项

1. **API 端点**: Qwen 使用 OpenAI 兼容模式，端点为 `https://dashscope.aliyuncs.com/compatible-mode/v1`
2. **图片处理**: 图片会被 Base64 编码后发送给 `qwen-vl-plus`
3. **成本优化**: 通用场景使用 `qwen-plus`，仅在需要时使用 `qwen-max` 或 `qwen-vl-plus`
4. **向后兼容**: API 接口保持不变，无需修改调用代码

## 故障排除

### 问题: 认证失败
**解决方案**: 检查 `QWEN_API_KEY` 是否正确配置

### 问题: 图片解析失败
**解决方案**: 
- 确认图片格式为 PNG/JPG/JPEG
- 检查图片文件是否存在
- 确认使用的是 `ParserScenario.IMAGE_OCR` 场景

### 问题: 模型调用超时
**解决方案**:
- 检查网络连接
- 考虑在 `config.py` 中调整 `TIMEOUT` 参数
