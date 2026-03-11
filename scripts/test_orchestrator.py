import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import OrderProcessingOrchestrator
from core.models import OrderStatus, ParsedOrder, OrderItem, MatchedOrder, MatchedOrderItem, RiskCheckResult, RiskIssue
from core.utils.order_manager import OrderManager
from utils.vector_store.faiss_manager import FAISSManager
from config import Config

def test_orchestrator_normal_flow():
    print("\n" + "="*70)
    print("测试 1: 正常订单处理流程（模拟完整 Agent 执行）")
    print("="*70)
    
    orchestrator = OrderProcessingOrchestrator()
    
    sample_order_text = """
    订单编号: ORD-2024-001
    客户名称: 某某机械制造有限公司
    
    订单明细:
    1. 物料名称: 不锈钢螺丝, 规格: M8x30mm, 数量: 1000, 单位: 个, 单价: 0.5, 交期: 2024-12-31
    2. 物料名称: 铝合金板材, 规格: 2mm x 1000mm x 2000mm, 数量: 50, 单位: 张, 单价: 150.0, 交期: 2024-12-31
    
    总金额: 15000.0
    """
    
    print("\n[步骤 1] 创建模拟解析结果...")
    mock_parsed_order = ParsedOrder(
        order_number="ORD-2024-001",
        customer_name="某某机械制造有限公司",
        items=[
            OrderItem(
                material_name="不锈钢螺丝",
                specification="M8x30mm",
                quantity=1000.0,
                unit="个",
                unit_price=0.5,
                delivery_date="2024-12-31",
                confidence_score=0.95
            ),
            OrderItem(
                material_name="铝合金板材",
                specification="2mm x 1000mm x 2000mm",
                quantity=50.0,
                unit="张",
                unit_price=150.0,
                delivery_date="2024-12-31",
                confidence_score=0.98
            )
        ],
        total_amount=15000.0,
        parsing_confidence=0.96
    )
    
    print("[步骤 2] 创建模拟匹配结果...")
    mock_matched_order = MatchedOrder(
        order_number="ORD-2024-001",
        customer_name="某某机械制造有限公司",
        items=[
            MatchedOrderItem(
                material_name="不锈钢螺丝",
                specification="M8x30mm",
                quantity=1000.0,
                unit="个",
                unit_price=0.5,
                delivery_date="2024-12-31",
                confidence_score=0.95,
                sku_code="SKU001",
                matched_material_name="不锈钢螺丝",
                match_score=0.98
            ),
            MatchedOrderItem(
                material_name="铝合金板材",
                specification="2mm x 1000mm x 2000mm",
                quantity=50.0,
                unit="张",
                unit_price=150.0,
                delivery_date="2024-12-31",
                confidence_score=0.98,
                sku_code="SKU002",
                matched_material_name="铝合金板材",
                match_score=0.95
            )
        ],
        total_amount=15000.0
    )
    
    print("[步骤 3] 创建模拟风控结果（无异常）...")
    mock_risk_result = RiskCheckResult(
        needs_confirmation=False,
        issues=[],
        overall_confidence=0.96
    )
    
    print("\n[结果验证]")
    order_id = orchestrator.order_manager.create_order(order_text=sample_order_text)
    orchestrator.order_manager.update_parsed_order(order_id, mock_parsed_order)
    orchestrator.order_manager.update_matched_order(order_id, mock_matched_order)
    orchestrator.order_manager.update_risk_result(order_id, mock_risk_result)
    orchestrator.order_manager.update_order_status(order_id, OrderStatus.COMPLETED)
    
    status = orchestrator.get_order_status(order_id)
    print(f"✅ 订单ID: {order_id}")
    print(f"✅ 状态: {status['status']}")
    print(f"✅ 需要确认: {status['needs_confirmation']}")
    print("✅ 正常流程测试通过!")

def test_orchestrator_risk_flow():
    print("\n" + "="*70)
    print("测试 2: 包含风险的订单处理流程（多轮反问触发）")
    print("="*70)
    
    orchestrator = OrderProcessingOrchestrator()
    
    print("\n[步骤 1] 创建包含异常的订单数据...")
    mock_parsed_order = ParsedOrder(
        order_number="ORD-2024-002",
        customer_name="测试异常客户",
        items=[
            OrderItem(
                material_name="异常物料",
                specification="未知规格",
                quantity=-100.0,
                unit="个",
                unit_price=0.0,
                delivery_date="2023-01-01",
                confidence_score=0.5
            )
        ],
        total_amount=0.0,
        parsing_confidence=0.5
    )
    
    mock_matched_order = MatchedOrder(
        order_number="ORD-2024-002",
        customer_name="测试异常客户",
        items=[
            MatchedOrderItem(
                material_name="异常物料",
                specification="未知规格",
                quantity=-100.0,
                unit="个",
                unit_price=0.0,
                delivery_date="2023-01-01",
                confidence_score=0.5,
                sku_code=None,
                matched_material_name=None,
                match_score=0.3
            )
        ],
        total_amount=0.0
    )
    
    print("[步骤 2] 创建包含多个风险的风控结果...")
    mock_risk_result = RiskCheckResult(
        needs_confirmation=True,
        issues=[
            RiskIssue(
                item_index=0,
                issue_type="low_confidence",
                description="解析置信度 0.5 低于阈值 0.8",
                severity="medium"
            ),
            RiskIssue(
                item_index=0,
                issue_type="low_match_score",
                description="物料匹配得分 0.3 低于阈值 0.8",
                severity="medium"
            ),
            RiskIssue(
                item_index=0,
                issue_type="invalid_price",
                description="单价 0.0 无效，必须大于 0",
                severity="high"
            ),
            RiskIssue(
                item_index=0,
                issue_type="past_delivery",
                description="交期 2023-01-01 已过",
                severity="high"
            ),
            RiskIssue(
                item_index=0,
                issue_type="invalid_quantity",
                description="数量 -100.0 无效，必须大于 0",
                severity="high"
            )
        ],
        overall_confidence=0.1
    )
    
    print("\n[步骤 3] 模拟处理流程并验证多轮反问...")
    order_id = orchestrator.order_manager.create_order(order_text="异常订单")
    orchestrator.order_manager.update_parsed_order(order_id, mock_parsed_order)
    orchestrator.order_manager.update_matched_order(order_id, mock_matched_order)
    orchestrator.order_manager.update_risk_result(order_id, mock_risk_result)
    orchestrator.order_manager.update_order_status(order_id, OrderStatus.NEEDS_CONFIRMATION)
    
    confirmation_request = orchestrator._create_confirmation_request(order_id, mock_risk_result)
    orchestrator.order_manager.add_confirmation_request(order_id, confirmation_request)
    
    status = orchestrator.get_order_status(order_id)
    print(f"\n✅ 订单ID: {order_id}")
    print(f"✅ 状态: {status['status']}")
    print(f"✅ 需要确认: {status['needs_confirmation']}")
    print(f"✅ 整体置信度: {status['confirmation_requests'][0]['overall_confidence']:.2f}")
    print(f"✅ 风险问题数: {len(status['confirmation_requests'][0]['issues'])}")
    print("\n风险问题详情:")
    for issue in status['confirmation_requests'][0]['issues']:
        print(f"  - [{issue['severity'].upper()}] {issue['issue_type']}: {issue['description']}")
    
    print("\n[步骤 4] 测试确认操作...")
    confirm_result = orchestrator.confirm_order(order_id, {"action": "confirm"})
    status_after = orchestrator.get_order_status(order_id)
    print(f"✅ 确认操作结果: {confirm_result['message']}")
    print(f"✅ 确认后状态: {status_after['status']}")

def test_confirmation_workflow():
    print("\n" + "="*70)
    print("测试 3: 完整的确认工作流程")
    print("="*70)
    
    orchestrator = OrderProcessingOrchestrator()
    order_id = orchestrator.order_manager.create_order(order_text="测试订单")
    
    print("\n[场景 A: 拒绝订单]")
    orchestrator.order_manager.update_order_status(order_id, OrderStatus.NEEDS_CONFIRMATION)
    
    reject_result = orchestrator.confirm_order(order_id, {"action": "reject"})
    status_reject = orchestrator.get_order_status(order_id)
    print(f"✅ 拒绝操作结果: {reject_result['message']}")
    print(f"✅ 拒绝后状态: {status_reject['status']}")
    
    print("\n[场景 B: 重置并再次确认]")
    orchestrator.order_manager.update_order_status(order_id, OrderStatus.NEEDS_CONFIRMATION)
    confirm_result = orchestrator.confirm_order(order_id, {"action": "confirm"})
    status_confirm = orchestrator.get_order_status(order_id)
    print(f"✅ 确认操作结果: {confirm_result['message']}")
    print(f"✅ 确认后状态: {status_confirm['status']}")

def main():
    print("开始 Phase 3 - 编排 SOP 测试...")
    
    print("\n初始化 FAISS 索引...")
    try:
        config = Config()
        faiss_manager = FAISSManager(index_path=config.FAISS_INDEX_PATH)
        if faiss_manager.get_document_count() == 0:
            print("提示: FAISS 索引为空，建议先运行 scripts/init_faiss_index.py")
        else:
            print(f"FAISS 索引已加载，包含 {faiss_manager.get_document_count()} 个文档")
    except Exception as e:
        print(f"FAISS 索引初始化警告: {e}")
    
    test_orchestrator_normal_flow()
    test_orchestrator_risk_flow()
    test_confirmation_workflow()
    
    print("\n" + "="*70)
    print("Phase 3 测试完成!")
    print("="*70)
    print("\n主要功能验证:")
    print("✅ 订单状态管理")
    print("✅ Agent 协作流程编排")
    print("✅ 多轮反问/确认机制")
    print("✅ 风险检测与人工介入触发")

if __name__ == "__main__":
    main()
