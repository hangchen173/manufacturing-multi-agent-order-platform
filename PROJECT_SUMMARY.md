# 制造业多 Agent 智能订单解析系统 - 项目完成总结

## 项目概述

已成功构建完整的制造业多 Agent 智能订单解析系统，支持处理 PDF/Excel/图片等多种格式的非结构化订单，并将其转化为 ERP 可用的标准结构化数据。

## 完整技术栈

- **语言**: Python 3.10+
- **框架**: LangChain (LCEL 架构)
- **LLM API**: Deepseek API
- **向量数据库**: FAISS
- **后端**: Flask + Flask-CORS
- **文档处理**: PyMuPDF (PDF), Pandas (Excel), OpenPyXL
- **结构化输出**: Pydantic

## 项目结构

```
AGENT_project/
├── app.py                          # Flask 启动壳
├── config.py                       # 配置管理
├── application/                    # 应用层
│   ├── agents/                     # Agent 实现
│   ├── orchestrators/              # 用例编排
│   ├── pipeline/                   # Stage 抽象
│   ├── services/                   # 应用服务
│   └── container.py                # 依赖注入
├── domain/                         # 领域层
│   ├── models.py                   # Pydantic 数据模型
│   ├── constants.py                # 常量
│   ├── exceptions.py               # 异常定义
│   └── order_state_machine.py      # 状态机规则
├── infrastructure/                 # 基础设施层
│   ├── document_processing/        # 文档加载
│   ├── repositories/               # 订单仓储
│   └── vector_store/               # 向量检索
├── interfaces/                     # 交互层
│   ├── http/                       # Flask API
│   └── ui/                         # Streamlit UI
├── data/
│   ├── faiss_index/                # FAISS 索引存储
│   ├── orders/                     # 活动订单与归档订单
│   ├── sample_orders/              # 示例订单存储
│   └── standard_materials/         # 标准物料示例
│       └── sample_materials.json   # 示例物料数据
├── scripts/                        # 工具脚本
│   ├── bootstrap/                    # 初始化脚本
│   ├── tests/                        # 测试脚本
│   ├── dev/                          # 开发辅助脚本
│   └── README.md                     # 使用说明
├── .env                            # 环境变量
├── .env.example                    # 环境变量示例
├── .gitignore
├── requirements.txt                # Python 依赖
├── README.md                       # 项目说明
└── PROJECT_SUMMARY.md              # 本文件
```

## 核心功能模块

### 1. Multi-Agent 系统

#### Parser Agent (解析智能体)
- 位置: `application/agents/parser_agent.py`
- 功能: 从订单文本中提取结构化信息
- 技术: LangChain Prompt + Deepseek API + Pydantic Output Parser
- 输出: `ParsedOrder` 模型

#### Matching Agent (匹配智能体)
- 位置: `application/agents/matching_agent.py`
- 功能: 将非标物料映射到标准 SKU
- 技术: FAISS 语义向量检索 + Sentence-Transformers
- 输出: `MatchedOrder` 模型

#### Risk Control Agent (风控智能体)
- 位置: `application/agents/risk_control_agent.py`
- 功能: 检测异常逻辑
- 检测项:
  - 解析置信度过低 (< 0.8)
  - 匹配得分过低 (< 0.8)
  - 单价异常 (负数、偏离参考价过大)
  - 交期异常 (已过期、格式错误)
  - 数量异常 (负数或零)
- 输出: `RiskCheckResult` 模型

### 2. 编排与状态管理

#### 订单状态管理
- 位置: `application/services/order_manager.py`
- 状态流转: PENDING → PARSING → MATCHING → RISK_CHECKING → COMPLETED/NEEDS_CONFIRMATION
- 支持: 状态查询、数据持久化、确认请求管理

#### Agent 协作编排器
- 位置: `application/orchestrators/order_processing.py`
- 功能: 完整的订单处理流程编排
- 支持: 文档输入/纯文本输入、多轮反问触发、确认/拒绝操作

### 3. Flask API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/upload` | 上传订单文档 (PDF/Excel/图片) |
| POST | `/api/upload_text` | 上传纯文本订单 |
| GET | `/api/query_status/<order_id>` | 查询订单状态 |
| POST | `/api/confirm/<order_id>` | 确认或拒绝订单 |

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
编辑 `.env` 文件，设置 `DEEPSEEK_API_KEY`

### 3. 初始化 FAISS 索引
```bash
python3 scripts/bootstrap/init_faiss_index.py
```

### 4. 运行测试
```bash
# 测试 Agent
python3 scripts/tests/test_agents.py

# 测试编排器
python3 scripts/tests/test_orchestrator.py

# 测试 API
python3 scripts/tests/test_api.py
```

### 5. 启动服务
```bash
python3 app.py
```

服务将在 http://localhost:5000 启动

## 多轮反问机制

当 Risk Control Agent 检测到异常时：
1. 订单状态自动变为 `NEEDS_CONFIRMATION`
2. 返回特定 JSON 结构的确认请求，包含：
   - 风险问题列表（问题类型、描述、严重程度）
   - 整体置信度
   - 所需操作（review_issues, confirm_or_reject）
3. 前端调用 `/api/confirm/<order_id>` 接口进行确认或拒绝

## 已完成的阶段

- ✅ **Phase 1**: 项目基础骨架搭建
- ✅ **Phase 2**: 核心 Agent 类实现
- ✅ **Phase 3**: Agent 协作 SOP 编排
- ✅ **Phase 4**: Flask API 接口开发

## 数据模型

所有数据模型定义在 `domain/models.py` 中：
- `OrderStatus`: 订单状态枚举
- `OrderItem`, `ParsedOrder`: 解析结果
- `MatchedOrderItem`, `MatchedOrder`: 匹配结果
- `RiskIssue`, `RiskCheckResult`: 风控检查结果
- `FinalOrderResult`: 最终处理结果

## 许可证

MIT
