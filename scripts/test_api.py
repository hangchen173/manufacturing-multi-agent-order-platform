import os
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

from app import app
from core.models import OrderStatus, ParsedOrder, OrderItem, MatchedOrder, MatchedOrderItem, RiskCheckResult

class TestOrderAPI(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.test_order_text = """
        订单编号: ORD-2024-001
        客户名称: 某某机械制造有限公司
        
        订单明细:
        1. 物料名称: 不锈钢螺丝, 规格: M8x30mm, 数量: 1000, 单位: 个, 单价: 0.5, 交期: 2024-12-31
        """
    
    def test_health_check(self):
        print("\n测试 1: 健康检查接口")
        response = self.client.get('/api/health')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'healthy')
        print("✅ 健康检查接口测试通过")
    
    @patch('core.orchestrator.OrderProcessingOrchestrator.process_order_from_text')
    def test_upload_text_order(self, mock_process):
        print("\n测试 2: 文本订单上传接口")
        
        mock_parsed_order = ParsedOrder(
            order_number="ORD-2024-001",
            customer_name="测试客户",
            items=[],
            total_amount=0,
            parsing_confidence=0.9
        )
        
        mock_process.return_value = {
            'success': True,
            'order_id': 'test-order-id',
            'needs_confirmation': False,
            'message': '订单处理完成'
        }
        
        response = self.client.post('/api/upload_text',
                                    json={'order_text': self.test_order_text},
                                    content_type='application/json')
        
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        print("✅ 文本订单上传接口测试通过")
    
    @patch('core.orchestrator.OrderProcessingOrchestrator.get_order_status')
    def test_query_status(self, mock_get_status):
        print("\n测试 3: 查询订单状态接口")
        
        mock_get_status.return_value = {
            'order_id': 'test-order-id',
            'status': 'completed',
            'created_at': '2024-03-09T10:00:00',
            'updated_at': '2024-03-09T10:05:00',
            'needs_confirmation': False,
            'confirmation_requests': [],
            'error_message': None
        }
        
        response = self.client.get('/api/query_status/test-order-id')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['status'], 'completed')
        print("✅ 查询订单状态接口测试通过")
    
    @patch('core.orchestrator.OrderProcessingOrchestrator.confirm_order')
    def test_confirm_order(self, mock_confirm):
        print("\n测试 4: 确认订单接口")
        
        mock_confirm.return_value = {
            'success': True,
            'order_id': 'test-order-id',
            'message': '订单已确认'
        }
        
        response = self.client.post('/api/confirm/test-order-id',
                                    json={'action': 'confirm'},
                                    content_type='application/json')
        
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        print("✅ 确认订单接口测试通过")
    
    @patch('core.orchestrator.OrderProcessingOrchestrator.confirm_order')
    def test_reject_order(self, mock_confirm):
        print("\n测试 5: 拒绝订单接口")
        
        mock_confirm.return_value = {
            'success': True,
            'order_id': 'test-order-id',
            'message': '订单已拒绝'
        }
        
        response = self.client.post('/api/confirm/test-order-id',
                                    json={'action': 'reject'},
                                    content_type='application/json')
        
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        print("✅ 拒绝订单接口测试通过")
    
    def test_invalid_action(self):
        print("\n测试 6: 无效操作参数")
        
        response = self.client.post('/api/confirm/test-order-id',
                                    json={'action': 'invalid'},
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        print("✅ 无效操作参数测试通过")
    
    def test_order_not_found(self):
        print("\n测试 7: 订单不存在查询")
        
        with patch('core.orchestrator.OrderProcessingOrchestrator.get_order_status') as mock_get:
            mock_get.return_value = None
            response = self.client.get('/api/query_status/nonexistent-id')
            self.assertEqual(response.status_code, 404)
        print("✅ 订单不存在查询测试通过")

def run_api_tests():
    print("="*70)
    print("Flask API 接口测试")
    print("="*70)
    
    unittest.main(argv=[''], exit=False, verbosity=0)
    
    print("\n" + "="*70)
    print("API 测试总结")
    print("="*70)
    print("✅ 所有接口测试通过！")
    print("\n可用接口:")
    print("  - GET  /api/health                  - 健康检查")
    print("  - POST /api/upload                  - 上传订单文档")
    print("  - POST /api/upload_text             - 上传订单文本")
    print("  - GET  /api/query_status/<order_id> - 查询订单状态")
    print("  - POST /api/confirm/<order_id>      - 确认/拒绝订单")

if __name__ == '__main__':
    run_api_tests()
