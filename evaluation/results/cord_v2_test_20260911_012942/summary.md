# Evaluation Summary: cord_v2_test

## Run Info

- Input dir: `/Users/cmh/Documents/AGENT_project/datasets/public/cord/processed/images`
- Annotation dir: `/Users/cmh/Documents/AGENT_project/datasets/public/cord/processed/annotations`
- Total samples: 100
- Success count: 84
- Failure count: 16
- Success rate: 84.00%
- Annotated samples: 84
- Avg latency: 149809.47 ms
- Needs confirmation rate: 84.00%

## Order-Level Accuracy

- `order_number`: 0/0 (0.00%)
- `customer_name`: 0/0 (0.00%)
- `total_amount`: 56/74 (75.68%)

## Item-Level Accuracy

- `material_name_raw`: 106/218 (48.62%)
- `specification_raw`: 0/0 (0.00%)
- `quantity`: 176/186 (94.62%)
- `unit`: 0/0 (0.00%)
- `unit_price`: 26/57 (45.61%)
- `delivery_date`: 0/0 (0.00%)

## Extra Metrics

- Item count exact match: 63/84 (75.00%)
- SKU Top-1 accuracy: 0/0 (0.00%)
- Confirmation accuracy: 0/0 (0.00%)
- Business decision accuracy: 0/0 (0.00%)
- Error auto-release rate: 0.00%

## Failures

- `cord_v2_test_008`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Invalid json output:
- `cord_v2_test_083`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-f30e156e-58c3-9b71-b9ae-fc54267a3783', 'request_id': 'f30e156e-58c3-9b71-b9ae-fc54267a3783'}
- `cord_v2_test_084`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-22be40f2-2f6a-9aee-895b-9e57d35d9599', 'request_id': '22be40f2-2f6a-9aee-895b-9e57d35d9599'}
- `cord_v2_test_085`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-7ab13e5a-4054-9fd8-a380-c1a3f505f6ab', 'request_id': '7ab13e5a-4054-9fd8-a380-c1a3f505f6ab'}
- `cord_v2_test_088`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-bd3a450d-a1c9-97cd-9e60-4a43133811e7', 'request_id': 'bd3a450d-a1c9-97cd-9e60-4a43133811e7'}
- `cord_v2_test_089`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-fcaf64b9-47fe-9a4d-9aa0-3227a3b11ccb', 'request_id': 'fcaf64b9-47fe-9a4d-9aa0-3227a3b11ccb'}
- `cord_v2_test_090`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-000091ef-2fd2-91d0-8bb7-c82d10f8c33f', 'request_id': '000091ef-2fd2-91d0-8bb7-c82d10f8c33f'}
- `cord_v2_test_091`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-92160888-5377-93d8-998d-98508c7b08fd', 'request_id': '92160888-5377-93d8-998d-98508c7b08fd'}
- `cord_v2_test_092`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-2a238409-c09c-9ddb-a217-5194c77aeb2f', 'request_id': '2a238409-c09c-9ddb-a217-5194c77aeb2f'}
- `cord_v2_test_093`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-6c891a76-1735-9aee-8c33-453c1d99ab80', 'request_id': '6c891a76-1735-9aee-8c33-453c1d99ab80'}
- `cord_v2_test_094`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-b25d102f-b5fb-95ec-a0cc-3d4c4063c388', 'request_id': 'b25d102f-b5fb-95ec-a0cc-3d4c4063c388'}
- `cord_v2_test_095`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-0e6d4f5a-e922-9746-8064-4aecbe2267f5', 'request_id': '0e6d4f5a-e922-9746-8064-4aecbe2267f5'}
- `cord_v2_test_096`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-abb1c8de-a6a5-9e7b-8d61-9da0f4c6bb48', 'request_id': 'abb1c8de-a6a5-9e7b-8d61-9da0f4c6bb48'}
- `cord_v2_test_097`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-d4484069-eeaa-978d-b5fa-68de26259fe9', 'request_id': 'd4484069-eeaa-978d-b5fa-68de26259fe9'}
- `cord_v2_test_098`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-45b2d2c9-9603-9310-85b8-41ed439e3724', 'request_id': '45b2d2c9-9603-9310-85b8-41ed439e3724'}
- `cord_v2_test_099`: 解析失败: [ParserAgent] 上一次输出无法通过结构校验，必须修正这些字段后重新输出：Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing. For details, see: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment', 'type': 'Arrearage', 'param': None, 'code': 'Arrearage'}, 'id': 'chatcmpl-c2c3435e-ca5b-943b-acdf-062062b8b7c4', 'request_id': 'c2c3435e-ca5b-943b-acdf-062062b8b7c4'}
