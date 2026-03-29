# Domain Layer

放纯业务概念与规则，不依赖 Flask、FAISS、文件系统等实现细节。

- `models.py`: 领域数据模型。
- `constants.py`: 业务常量与枚举。
- `exceptions.py`: 领域异常。
- `order_state_machine.py`: 订单状态流转规则。
