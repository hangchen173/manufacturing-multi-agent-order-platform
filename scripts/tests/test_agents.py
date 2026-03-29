import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from application.agents import ParserAgent, MatchingAgent, RiskControlAgent
from config import Config
from domain.models import OrderItem, ParsedOrder
from infrastructure.vector_store import FAISSManager

def test_parser_agent():
    print("\n" + "="*60)
    print("测试 Parser Agent")
    print("="*60)
    
    sample_order_text = """
    订单编号: ORD-2024-001
    客户名称: 某某机械制造有限公司
    
    订单明细:
    1. 物料名称: 不锈钢螺丝, 规格: M8x30mm, 数量: 1000, 单位: 个, 单价: 0.5, 交期: 2024-03-15
    2. 物料名称: 铝合金板材, 规格: 2mm x 1000mm x 2000mm, 数量: 50, 单位: 张, 单价: 150.0, 交期: 2024-03-20
    3. 物料名称: PVC管材, 规格: DN50 x 4m, 数量: 200, 单位: 根, 单价: 25.0, 交期: 2024-03-25
    
    总金额: 15000.0
    """
    
    parser_agent = ParserAgent()
    result = parser_agent.run({"order_text": sample_order_text})
    
    if result["success"]:
        print("✅ Parser Agent 测试成功!")
        parsed_order = result["parsed_order"]
        print(f"   订单编号: {parsed_order.order_number}")
        print(f"   客户名称: {parsed_order.customer_name}")
        print(f"   物料数量: {len(parsed_order.items)}")
        for idx, item in enumerate(parsed_order.items):
            print(f"   {idx+1}. {item.material_name} - {item.quantity} {item.unit}")
    else:
        print(f"❌ Parser Agent 测试失败: {result['message']}")
    
    return result

def test_matching_agent():
    print("\n" + "="*60)
    print("测试 Matching Agent")
    print("="*60)
    
    sample_parsed_order = ParsedOrder(
        order_number="ORD-2024-001",
        customer_name="测试客户",
        items=[
            OrderItem(
                material_name="不锈钢螺丝",
                specification="M8x30mm",
                quantity=1000.0,
                unit="个",
                unit_price=0.5,
                delivery_date="2024-03-15",
                confidence_score=0.95
            ),
            OrderItem(
                material_name="铝合金板",
                specification="2mm厚",
                quantity=50.0,
                unit="张",
                unit_price=150.0,
                delivery_date="2024-03-20",
                confidence_score=0.85
            )
        ],
        total_amount=15000.0,
        parsing_confidence=0.9
    )
    
    matching_agent = MatchingAgent()
    result = matching_agent.run({"parsed_order": sample_parsed_order})
    
    if result["success"]:
        print("✅ Matching Agent 测试成功!")
        matched_order = result["matched_order"]
        for idx, item in enumerate(matched_order.items):
            print(f"   {idx+1}. {item.material_name}")
            print(f"      匹配 SKU: {item.sku_code}")
            print(f"      匹配得分: {item.match_score:.2f}")
    else:
        print(f"❌ Matching Agent 测试失败: {result['message']}")
    
    return result

def test_risk_control_agent():
    print("\n" + "="*60)
    print("测试 Risk Control Agent")
    print("="*60)
    
    from domain.models import MatchedOrder, MatchedOrderItem
    
    sample_matched_order = MatchedOrder(
        order_number="ORD-2024-001",
        customer_name="测试客户",
        items=[
            MatchedOrderItem(
                material_name="不锈钢螺丝",
                specification="M8x30mm",
                quantity=1000.0,
                unit="个",
                unit_price=0.5,
                delivery_date="2024-03-15",
                confidence_score=0.95,
                sku_code="SKU001",
                matched_material_name="不锈钢螺丝",
                match_score=0.98
            ),
            MatchedOrderItem(
                material_name="异常物料",
                specification="无规格",
                quantity=-50.0,
                unit="个",
                unit_price=0.0,
                delivery_date="2023-01-01",
                confidence_score=0.5,
                sku_code=None,
                matched_material_name=None,
                match_score=0.3
            )
        ],
        total_amount=15000.0
    )
    
    risk_agent = RiskControlAgent()
    result = risk_agent.run({"matched_order": sample_matched_order})
    
    if result["success"]:
        print("✅ Risk Control Agent 测试成功!")
        risk_result = result["risk_result"]
        print(f"   整体置信度: {risk_result.overall_confidence:.2f}")
        print(f"   需要人工确认: {risk_result.needs_confirmation}")
        print(f"   发现问题数: {len(risk_result.issues)}")
        for issue in risk_result.issues:
            print(f"   - [ {issue.severity.upper()} ] {issue.issue_type}: {issue.description}")
    else:
        print(f"❌ Risk Control Agent 测试失败: {result['message']}")
    
    return result

def main():
    print("开始 Phase 2 Agent 测试...")
    
    config = Config()
    
    print("\n初始化 FAISS 索引...")
    try:
        faiss_manager = FAISSManager(index_path=config.FAISS_INDEX_PATH)
        if faiss_manager.get_document_count() == 0:
            print("FAISS 索引为空，请先运行 scripts/bootstrap/init_faiss_index.py")
        else:
            print(f"FAISS 索引已加载，包含 {faiss_manager.get_document_count()} 个文档")
    except Exception as e:
        print(f"FAISS 索引初始化警告: {e}")
    
    test_matching_agent()
    test_risk_control_agent()
    
    print("\n" + "="*60)
    print("注意: Parser Agent 需要有效的 qwen API Key 才能完整测试")
    print("请在 .env 文件中配置 QWEN_API_KEY")
    print("="*60)

if __name__ == "__main__":
    main()
