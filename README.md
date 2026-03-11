# 制造业多 Agent 智能订单解析系统

基于 LangChain 和 Multi-Agent 架构的智能订单解析系统，支持处理 PDF/Excel/图片等多种格式的非结构化订单，并将其转化为 ERP 可用的标准结构化数据。

## 技术栈

- **语言**: Python 3.10+
- **框架**: LangChain (LCEL 架构)
- **LLM API**: 阿里云 Qwen 系列 (通义千问)
  - `qwen-max` - Agent 逻辑决策、字段提取
  - `qwen-plus` - 通用订单解析（性价比最高）
  - `qwen-vl-plus` - 图片/OCR/扫描件订单
- **向量数据库**: FAISS
- **后端**: Flask + Flask-CORS
- **文档处理**: PyMuPDF (PDF), Pandas (Excel), OpenPyXL

## 迁移说明

从 Deepseek 迁移到 Qwen，请参考 [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)

## 系统架构

### Multi-Agent 协作

1. **Parser Agent (解析智能体)**
   - 从不同格式文档中提取字段（物料名、规格、数量、交期、单价等）
   - 使用 Prompt Chain 结合 Pydantic 进行结构化输出

2. **Matching Agent (匹配智能体)**
   - 将提取的非标字段映射到工厂的标准物料库
   - 利用 FAISS 进行语义向量检索，寻找最匹配的 SKU 编号

3. **Risk Control Agent (风控智能体)**
   - 检测异常逻辑（单价异常高、交期冲突等）
   - 置信度阈值：若 < 0.8 或逻辑冲突，触发多轮反问机制

## 项目结构

```
AGENT_project/
├── app.py                  # Flask 应用主入口
├── config.py               # 配置文件
├── core/
│   ├── agents/             # Agent 实现
│   │   ├── base_agent.py       # Agent 基类
│   │   ├── parser_agent.py     # 解析智能体
│   │   ├── matching_agent.py   # 匹配智能体
│   │   └── risk_control_agent.py  # 风控智能体
│   ├── models.py           # 数据模型
│   ├── utils/              # 核心工具
│   │   └── order_manager.py    # 订单状态管理
│   └── orchestrator.py     # Agent 协作编排器
├── data/
│   ├── faiss_index/        # FAISS 索引
│   ├── sample_orders/      # 示例订单
│   └── standard_materials/ # 标准物料库
├── routes/                 # Flask 路由
├── scripts/                # 工具脚本
│   ├── init_faiss_index.py # 初始化 FAISS 索引
│   ├── test_agents.py      # Agent 测试脚本
│   ├── test_orchestrator.py  # 编排器测试脚本
│   └── test_api.py         # API 测试脚本
├── utils/
│   ├── data_processing/    # 文档处理工具
│   │   └── document_loader.py
│   └── vector_store/       # 向量存储工具
│       └── faiss_manager.py
├── .env                    # 环境变量
├── .env.example            # 环境变量示例
├── .gitignore
├── requirements.txt        # Python 依赖
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，并填写你的 Deepseek API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置 `DEEPSEEK_API_KEY`。

### 3. 初始化 FAISS 向量索引

```bash
python scripts/init_faiss_index.py
```

### 4. 测试 Agent

```bash
python scripts/test_agents.py
```

### 5. 测试编排器

```bash
python scripts/test_orchestrator.py
```

### 6. 启动 Flask 服务

```bash
python3 app.py
```

服务将在 http://localhost:5000 启动

### 7. 测试 API

```bash
python3 scripts/test_api.py
```

## Phase 1 - 已完成

- [x] 创建标准的 Python 项目结构
- [x] 配置 `.env` 环境文件
- [x] 建立 `core/`, `api/`, `utils/`, `data/` 文件夹
- [x] 创建配置文件和数据模型

## Phase 2 - 已完成

- [x] 实现基础 Agent 基类 (`core/agents/base_agent.py`)
- [x] 实现 Parser Agent，支持 Pydantic Output Parser (`core/agents/parser_agent.py`)
- [x] 实现 Matching Agent，集成 FAISS 向量检索 (`core/agents/matching_agent.py`)
- [x] 实现 Risk Control Agent (`core/agents/risk_control_agent.py`)
- [x] 提供标准物料库示例数据 (`data/standard_materials/sample_materials.json`)
- [x] 创建 FAISS 索引初始化脚本 (`scripts/init_faiss_index.py`)
- [x] 创建 Agent 测试脚本 (`scripts/test_agents.py`)

## Phase 3 - 已完成

- [x] 创建订单状态管理模块 (`core/utils/order_manager.py`)
- [x] 实现 Agent 协作编排器 (`core/orchestrator.py`)
- [x] 实现 Parser Agent -> Matching Agent -> Risk Control Agent 完整流程
- [x] 实现多轮反问逻辑（需要人工确认时返回特定 JSON 结构）
- [x] 支持订单确认/拒绝操作
- [x] 创建编排器测试脚本 (`scripts/test_orchestrator.py`)

## Phase 4 - 已完成

- [x] 创建 Flask 应用主入口 (`app.py`)
- [x] 实现 `/api/health` 健康检查接口
- [x] 实现 `/api/upload` 接口（接收文档并启动解析流）
- [x] 实现 `/api/upload_text` 接口（接收纯文本订单）
- [x] 实现 `/api/query_status/<order_id>` 接口（查看解析进度与人工干预状态）
- [x] 实现 `/api/confirm/<order_id>` 接口（处理人工确认/拒绝）
- [x] 支持 CORS 跨域请求
- [x] 创建 API 测试脚本 (`scripts/test_api.py`)

### API 接口文档

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/upload` | 上传订单文档 (PDF/Excel/图片) |
| POST | `/api/upload_text` | 上传纯文本订单 |
| GET | `/api/query_status/<order_id>` | 查询订单状态 |
| POST | `/api/confirm/<order_id>` | 确认或拒绝订单 (action: confirm/reject)

## License

MIT
