import os
import sys
import tempfile
import pandas as pd
import streamlit as st
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from core.orchestrator import OrderProcessingOrchestrator
from core.models import OrderStatus

st.set_page_config(
    page_title="多 Agent 订单解析系统",
    page_icon="🤖",
    layout="wide"
)

config = Config()

if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = OrderProcessingOrchestrator()

if 'processed_orders' not in st.session_state:
    st.session_state.processed_orders = 0

if 'total_saved_hours' not in st.session_state:
    st.session_state.total_saved_hours = 0.0

with st.sidebar:
    st.title("🤖 Agent 控制台")
    
    st.subheader("📊 统计数据")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("处理订单数", st.session_state.processed_orders)
    with col2:
        st.metric("节省工时(小时)", f"{st.session_state.total_saved_hours:.1f}")
    
    st.divider()
    
    st.subheader("⚙️ 配置")
    api_key = st.text_input("Qwen API Key", value=config.QWEN_API_KEY or "", type="password")
    
    st.divider()
    
    st.subheader("🛠️ 工具")
    if st.button("🔄 清除缓存"):
        st.session_state.processed_orders = 0
        st.session_state.total_saved_hours = 0.0
        st.success("缓存已清除！")
    
    st.divider()
    
    st.subheader("📋 Agent 状态")
    st.success("✅ Parser Agent: 就绪")
    st.success("✅ Matching Agent: 就绪")
    st.success("✅ Risk Control Agent: 就绪")

st.title("🏭 制造业多 Agent 智能订单解析系统")
st.markdown("基于 LangChain 和 Qwen 模型的智能订单解析系统")

tab1, tab2 = st.tabs(["📄 订单解析", "📊 历史记录"])

with tab1:
    st.subheader("📤 上传订单")
    
    input_method = st.radio("选择输入方式", ["📝 粘贴文本", "📁 上传文件"])
    
    order_text = ""
    uploaded_file = None
    
    if input_method == "📝 粘贴文本":
        order_text = st.text_area("粘贴订单文本", height=200, placeholder="""订单编号: ORD-2024-001
客户: XX制造公司
物料: 不锈钢螺丝 M8x30, 数量: 1000, 单价: 0.5, 交期: 2024-06-30
物料: 铝合金板 6061-T6 2mm, 数量: 50, 单价: 180, 交期: 2024-07-15""")
    else:
        uploaded_file = st.file_uploader("选择订单文件", type=['pdf', 'xlsx', 'xls', 'png', 'jpg', 'jpeg'])
    
    process_button = st.button("🚀 开始解析", type="primary")
    
    if process_button:
        if (input_method == "📝 粘贴文本" and order_text) or (input_method == "📁 上传文件" and uploaded_file):
            st.divider()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                parser_status = st.status("🔍 Parser Agent: 解析中...", expanded=True)
            with col2:
                matching_status = st.status("🔗 Matching Agent: 等待中...", expanded=False)
            with col3:
                risk_status = st.status("🛡️ Risk Control Agent: 等待中...", expanded=False)
            
            try:
                result = None
                
                with parser_status:
                    st.write("正在提取订单字段...")
                    
                    if input_method == "📝 粘贴文本":
                        result = st.session_state.orchestrator.process_order_from_text(order_text)
                    else:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name
                        
                        try:
                            result = st.session_state.orchestrator.process_order_from_document(tmp_path)
                        finally:
                            os.unlink(tmp_path)
                
                parser_status.update(label="✅ Parser Agent: 完成", state="complete", expanded=False)
                
                if result and result.get('success'):
                    st.session_state.processed_orders += 1
                    st.session_state.total_saved_hours += 0.5
                    
                    final_result = result.get('final_result')
                    
                    with matching_status:
                        matching_status.update(label="🔗 Matching Agent: 匹配中...", expanded=True)
                        st.write("正在匹配标准物料库...")
                        matching_status.update(label="✅ Matching Agent: 完成", state="complete", expanded=False)
                    
                    with risk_status:
                        risk_status.update(label="🛡️ Risk Control Agent: 检查中...", expanded=True)
                        st.write("正在进行风控检查...")
                        risk_status.update(label="✅ Risk Control Agent: 完成", state="complete", expanded=False)
                    
                    st.divider()
                    st.success("🎉 订单解析完成！")
                    
                    if final_result:
                        if final_result.status == OrderStatus.NEEDS_CONFIRMATION:
                            st.warning("⚠️ 需要人工确认")
                            
                            col_a, col_b = st.columns([1, 1])
                            
                            with col_a:
                                st.subheader("🔍 确认原因")
                                order = st.session_state.orchestrator.order_manager.get_order(result['order_id'])
                                if order and order.confirmation_requests:
                                    req = order.confirmation_requests[-1]
                                    for reason in req.get('needs_confirmation_reasons', []):
                                        st.info(f"• {reason}")
                                    
                                    if req.get('issues'):
                                        st.error("发现的问题:")
                                        for issue in req['issues']:
                                            st.error(f"  - 第 {issue['item_index'] + 1} 项: {issue['description']}")
                            
                            with col_b:
                                st.subheader("✏️ 手动确认")
                                confirm_action = st.radio("选择操作", ["✅ 确认通过", "❌ 拒绝"])
                                if st.button("提交确认"):
                                    action = "confirm" if confirm_action == "✅ 确认通过" else "reject"
                                    confirm_result = st.session_state.orchestrator.confirm_order(result['order_id'], {'action': action})
                                    if confirm_result.get('success'):
                                        st.success(f"订单已{'确认' if action == 'confirm' else '拒绝'}！")
                                        st.rerun()
                        
                        st.subheader("📋 解析结果")
                        
                        if final_result.matched_order:
                            items_data = []
                            for idx, item in enumerate(final_result.matched_order.items):
                                row = {
                                    "序号": idx + 1,
                                    "物料名称": getattr(item, 'material_name', '-'),
                                    "规格": getattr(item, 'specification', '-'),
                                    "数量": getattr(item, 'quantity', '-'),
                                    "单位": getattr(item, 'unit', '-'),
                                    "单价": getattr(item, 'unit_price', '-'),
                                    "交期": getattr(item, 'delivery_date', '-')
                                }
                                
                                if hasattr(item, 'sku_code'):
                                    row["匹配SKU"] = item.sku_code or '-'
                                if hasattr(item, 'matched_material_name'):
                                    row["匹配物料"] = item.matched_material_name or '-'
                                if hasattr(item, 'match_score'):
                                    row["匹配得分"] = f"{item.match_score:.2f}"
                                
                                items_data.append(row)
                            
                            df = pd.DataFrame(items_data)
                            
                            def highlight_match_score(val):
                                try:
                                    score = float(val)
                                    if score < 0.8:
                                        return 'background-color: #ffcccc'
                                    elif score < 0.9:
                                        return 'background-color: #fff3cd'
                                    else:
                                        return 'background-color: #d4edda'
                                except:
                                    return ''
                            
                            if '匹配得分' in df.columns:
                                styled_df = df.style.applymap(highlight_match_score, subset=['匹配得分'])
                                st.dataframe(styled_df, use_container_width=True)
                            else:
                                st.dataframe(df, use_container_width=True)
                            
                            st.divider()
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("订单编号", final_result.parsed_order.order_number or "-")
                            with col2:
                                st.metric("客户名称", final_result.parsed_order.customer_name or "-")
                            with col3:
                                total = final_result.parsed_order.total_amount
                                if total:
                                    st.metric("总金额", f"¥{total:.2f}")
                                else:
                                    st.metric("总金额", "-")
                else:
                    st.error(f"解析失败: {result.get('message', '未知错误')}")
            
            except Exception as e:
                st.error(f"处理出错: {str(e)}")
                import traceback
                st.error(traceback.format_exc())
        else:
            st.warning("请输入订单文本或上传文件！")

with tab2:
    st.subheader("📊 处理历史")
    
    orders = st.session_state.orchestrator.order_manager.get_all_orders()
    
    if orders:
        history_data = []
        for order_id, order in orders.items():
            history_data.append({
                "订单ID": order_id[:8] + "...",
                "状态": order.status.value,
                "创建时间": order.created_at.strftime("%Y-%m-%d %H:%M"),
                "是否需确认": len(order.confirmation_requests) > 0
            })
        
        st.dataframe(pd.DataFrame(history_data), use_container_width=True)
    else:
        st.info("暂无处理记录")
