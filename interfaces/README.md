# Interface Layer

放对外入口与展示层。

- `http/`: Flask API 与 HTTP 序列化。
- `ui/`: Streamlit 页面与交互逻辑。

顶层 `app.py` 是 Flask API 的启动壳；React 前端通过 Nginx 的同源 `/api` 代理调用它。
