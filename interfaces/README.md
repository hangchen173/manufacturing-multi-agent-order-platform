# Interface Layer

放对外入口与展示层。

- `http/`: Flask API 与 HTTP 序列化。
- `ui/`: Streamlit 页面与交互逻辑。

顶层 `app.py`、`streamlit_app.py` 只是转发到这里的启动壳。
