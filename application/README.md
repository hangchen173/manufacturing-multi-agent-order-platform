# Application Layer

放用例编排与应用服务。

- `agents/`: 面向业务流程的 Agent 实现。
- `orchestrators/`: 串联多个阶段的用例编排。
- `pipeline/`: 可复用的阶段执行协议。
- `services/`: 跨阶段共享的应用服务，如订单状态管理。
- `container.py`: 依赖装配入口。
