"""应用层端口（六边形架构的抽象边界）。

设计文档 §3.1 承诺 `application → infrastructure via abstract ports`。端口必须
定义在 application 层：infrastructure 提供实现，application 只依赖这里的抽象。
此前 4 个 ABC 定义在 `infrastructure/repositories/` 下，application 反向依赖
infrastructure，依赖倒置只做了一半。

`OrderRepository.collaboration_repositories()` 让适配器自行声明与其**同源**的
协作仓储（黑板/任务/消息）。这样 OrderManager 无需 isinstance 具体类型，也无需
import 任何 infrastructure 模块，即可保证「四个仓储同源」——订单落 Postgres 而
协作状态落内存会造成重启后订单卡在中间态且不报错（见 P0-1）。
"""
