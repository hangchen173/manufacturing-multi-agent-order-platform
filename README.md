# 🏭 制造业多 Agent 智能订单解析系统

基于 LangChain 和 Multi-Agent 架构的智能订单解析系统，支持处理 PDF/Excel/图片等多种格式的非结构化订单，并将其转化为 ERP 可用的标准结构化数据。

## ✨ 核心特性

- 🤖 **三 Agent 协作**: Parser Agent + Matching Agent + Risk Control Agent
- 🎯 **智能模型选择**: 根据场景自动选择最优 Qwen 模型
- 📊 **可视化前端**: Streamlit 演示界面，实时展示 Agent 协作过程
- 🔍 **向量检索**: FAISS + Sentence-Transformers 语义匹配
- 🛡️ **智能风控**: 自动检测异常，触发人工确认机制

---

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| **语言** | Python 3.10+ |
| **框架** | LangChain (LCEL 架构) |
| **LLM** | 阿里云 Qwen 系列 (通义千问) |
| **向量数据库** | FAISS |
| **后端** | Flask + Flask-CORS |
| **前端** | Streamlit |
| **文档处理** | PyMuPDF (PDF), Pandas (Excel), OpenPyXL |

### Qwen 模型策略

| 场景 | 使用模型 | 说明 |
|------|---------|------|
| Agent 逻辑决策 | `qwen-max` | 最强逻辑能力 |
| 通用订单解析 | `qwen-plus` | 性价比最高 |
| 图片/OCR/扫描件 | `qwen-vl-plus` | 视觉理解能力 |

---

## 🏗️ 系统架构

### Multi-Agent 协作流程

```
┌─────────────────────────────────────────────────────────────┐
│                        订单输入                              │
│              (文本/PDF/Excel/图片)                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   Parser Agent (解析智能体)                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ • 提取订单字段 (物料名、规格、数量、交期、单价等)      │  │
│  • 使用 Pydantic 进行结构化输出                          │  │
│  • 模型: qwen-plus/qwen-vl-plus                          │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Matching Agent (匹配智能体)                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ • FAISS 语义向量检索                                    │  │
│  • 将非标字段映射到标准物料库                              │  │
│  • 计算匹配得分 (match_score)                              │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                Risk Control Agent (风控智能体)               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ • 检测异常: 单价、交期、匹配得分                         │  │
│  • 置信度阈值: < 0.8 或发现问题 → 触发人工确认             │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│   COMPLETED     │    │ NEEDS_CONFIRMATION│
│   (已完成)      │    │   (需人工确认)    │
└─────────────────┘    └────────┬─────────┘
                                  │
                           用户确认/拒绝
                                  │
                           ┌──────┴──────┐
                           ▼             ▼
                    ┌──────────┐  ┌─────────┐
                    │ COMPLETED│  │ FAILED  │
                    │ (已完成) │  │ (已失败)│
                    └──────────┘  └─────────┘
```

### 核心 Agent 详解

#### 1. Parser Agent (解析智能体)
- **功能**: 从不同格式文档中提取结构化字段
- **输出**: `ParsedOrder` 对象
- **支持场景**:
  - 通用文本/PDF/Excel → `qwen-plus`
  - 图片/OCR/扫描件 → `qwen-vl-plus`
  - 复杂逻辑决策 → `qwen-max`

#### 2. Matching Agent (匹配智能体)
- **功能**: 将非标字段映射到工厂标准物料库
- **技术**: FAISS 向量检索 + Sentence-Transformers
- **输出**: `MatchedOrder` 对象，包含 SKU 和匹配得分

#### 3. Risk Control Agent (风控智能体)
- **功能**: 检测异常逻辑
- **检查项**:
  - 单价异常 (参考标准价格)
  - 交期冲突 (过期/无效格式)
  - 匹配得分低 (< 0.8)
  - 解析置信度低
- **输出**: `RiskCheckResult`，决定是否需要人工确认

---

## 📁 项目结构

```
AGENT_project/
├── app.py                      # Flask 启动壳
├── streamlit_app.py            # Streamlit 启动壳
├── config.py                   # 配置文件
├── requirements.txt            # Python 依赖
│
├── application/                # 应用层: 编排、Agent、服务
│   ├── agents/                 # Agent 实现
│   ├── orchestrators/          # 用例编排
│   ├── pipeline/               # Pipeline Stage 抽象
│   ├── services/               # 应用服务
│   └── container.py            # 依赖注入容器
│
├── domain/                     # 领域层: 规则、模型、异常
│   ├── constants.py
│   ├── exceptions.py
│   ├── models.py
│   └── order_state_machine.py
│
├── infrastructure/             # 基础设施层
│   ├── document_processing/    # 文档加载
│   ├── repositories/           # 持久化仓储
│   └── vector_store/           # 向量检索
│
├── interfaces/                 # 交互层
│   ├── http/                   # Flask API
│   └── ui/                     # Streamlit UI
│
├── data/
│   ├── standard_materials.csv  # 标准物料库 (CSV)
│   ├── faiss_index/            # FAISS 向量索引
│   ├── orders/                 # 订单持久化仓储
│   └── sample_orders/          # 示例订单存储
│
├── scripts/
│   ├── bootstrap/              # 初始化脚本
│   ├── tests/                  # 测试脚本
│   ├── dev/                    # 开发辅助脚本
│   └── README.md               # 脚本约定
│
├── .env                        # 环境变量
├── .env.example                # 环境变量示例
└── README.md
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置 Qwen API Key：

```env
# Qwen 配置
QWEN_API_KEY=your_qwen_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 模型选择
QWEN_MODEL_MAX=qwen-max
QWEN_MODEL_PLUS=qwen-plus
QWEN_MODEL_VL=qwen-vl-plus

# Flask 配置
FLASK_PORT=5001
FLASK_DEBUG=true

# 风控配置
RISK_CONFIDENCE_THRESHOLD=0.8

# 路径配置
DATA_DIR=data
FAISS_INDEX_PATH=data/faiss_index
STANDARD_MATERIALS_PATH=data/standard_materials.csv
SAMPLE_ORDERS_PATH=data/sample_orders
ORDER_STORE_PATH=data/orders/orders.json
ORDER_ARCHIVE_PATH=data/orders/orders.archive.json
ORDER_AUTO_ARCHIVE_DAYS=30
```

### 3. 准备标准物料库

`data/standard_materials.csv` 已包含示例数据，格式如下：

| sku_code | material_name | specification | unit | reference_price | category |
|----------|---------------|---------------|------|-----------------|----------|
| SKU-001 | 不锈钢螺丝 | M8x30 | 个 | 0.50 | 紧固件 |
| SKU-002 | 不锈钢螺丝 | M6x20 | 个 | 0.35 | 紧固件 |
| ... | ... | ... | ... | ... | ... |

### 4. 初始化 FAISS 向量索引

```bash
python3 scripts/bootstrap/init_faiss_index.py
```

### 5. 启动服务

#### 方式一: Streamlit 可视化演示 (推荐)

```bash
streamlit run streamlit_app.py
```

访问: http://localhost:8501

#### 方式二: Flask API 服务

```bash
python3 app.py
```

服务将在 http://localhost:5001 启动

---

## 🌐 API 接口

### 健康检查
```http
GET /api/health
```

### 上传文件解析
```http
POST /api/upload
Content-Type: multipart/form-data

file: [PDF/Excel/PNG/JPG 订单文件]
```

### 文本订单解析
```http
POST /api/upload_text
Content-Type: application/json

{
  "order_text": "订单文本内容..."
}
```

### 查询订单状态
```http
GET /api/query_status/{order_id}
```

### 人工确认
```http
POST /api/confirm/{order_id}
Content-Type: application/json

{
  "action": "confirm"  // 或 "reject"
}
```

---

## 📊 Streamlit 演示功能

### 左侧边栏
- 📊 **统计数据**: 处理订单数、节省工时
- ⚙️ **配置**: Qwen API Key 设置
- 🛠️ **工具**: 清除缓存、Agent 状态显示

### 订单解析
- 📝 **文本输入**: 直接粘贴订单文本
- 📁 **文件上传**: 支持 PDF/Excel/图片
- 🔄 **实时状态**: 动态展示三个 Agent 的协作过程
- 📋 **结果展示**: 美观的数据表格，高亮低匹配得分

### 人工确认
- ⚠️ **异常高亮**: 红色显示风险问题
- ✏️ **手动修正**: 提供确认/拒绝操作

---

## 🔧 数据模型

### ParsedOrder (解析结果)
```python
{
  "order_number": "ORD-2024-001",
  "customer_name": "XX公司",
  "items": [...],
  "total_amount": 1000.0,
  "parsing_confidence": 0.95
}
```

### MatchedOrder (匹配结果)
```python
{
  "order_number": "ORD-2024-001",
  "items": [
    {
      "material_name": "不锈钢螺丝",
      "specification": "M8x30",
      "quantity": 1000,
      "sku_code": "SKU-001",
      "matched_material_name": "不锈钢螺丝",
      "match_score": 0.95
    }
  ]
}
```

### RiskCheckResult (风控结果)
```python
{
  "needs_confirmation": true,
  "issues": [
    {
      "item_index": 0,
      "issue_type": "low_match_score",
      "description": "匹配得分低于阈值",
      "severity": "medium"
    }
  ],
  "overall_confidence": 0.75
}
```

---

## 📚 迁移说明

从 Deepseek 迁移到 Qwen，请参考 [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License
