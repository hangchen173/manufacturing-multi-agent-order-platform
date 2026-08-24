# 制造业多 Agent 智能订单解析系统

系统使用 Qwen 解析 PDF、Excel、图片和文本订单，以 FAISS 匹配标准物料库，并对低置信度、价格和交期风险发起人工确认。

## 架构

- React + TypeScript 工作台：提交订单、查看匹配与风控结果、确认异常订单、浏览完整历史。
- Nginx：在 `http://localhost:8080` 提供前端并将 `/api` 同源代理到后端。
- Flask + Gunicorn：订单处理 API。
- PostgreSQL：订单快照、状态和归档记录，数据由 Docker 命名卷持久化。
- FAISS：物料索引；索引和上传文件保存在挂载的 `data/` 目录。

## 一键启动

1. 创建环境配置：

   ```bash
   cp .env.example .env
   ```

2. 在 `.env` 中设置强密码和 Qwen API Key：

   ```env
   POSTGRES_PASSWORD=replace_with_a_strong_password
   QWEN_API_KEY=your_qwen_api_key_here
   ```

3. 构建并启动全部服务：

   ```bash
   docker compose up -d --build
   ```

4. 打开 [http://localhost:8080](http://localhost:8080)。

首次构建会下载 Python 依赖和 `all-MiniLM-L6-v2` 嵌入模型。PostgreSQL 不暴露给宿主机；停止或重建服务不会删除订单数据。只有执行 `docker compose down -v` 才会删除 PostgreSQL 命名卷。

查看运行状态：

```bash
docker compose ps
docker compose logs -f api
```

## 配置

`.env.example` 包含全部环境变量。Compose 会自动用 PostgreSQL 服务名构造 `DATABASE_URL`，无需改动该变量。`data/standard_materials.csv` 是标准物料库，`data/faiss_index/` 是已构建的索引；如更新物料库，可在后端容器中重新初始化：

```bash
docker compose exec api python scripts/bootstrap/init_faiss_index.py
```

## HTTP API

所有接口均由 Web 服务的 `/api` 同源代理提供。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 服务健康检查 |
| `POST` | `/api/upload_text` | JSON `{ "order_text": "..." }` 提交文本订单 |
| `POST` | `/api/upload` | `multipart/form-data` 字段 `file` 上传订单文件 |
| `GET` | `/api/orders` | 获取按创建时间倒序的订单摘要 |
| `GET` | `/api/orders/{order_id}` | 获取订单完整结果、风险与状态流转 |
| `POST` | `/api/confirm/{order_id}` | JSON `{ "action": "confirm" | "reject" }` 处理人工确认 |

## 本地验证

后端测试需要安装 Python 依赖；仓储业务测试使用内存替身，不依赖本机 PostgreSQL：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

前端构建与测试：

```bash
cd frontend
npm install
npm run build
npm test
```
