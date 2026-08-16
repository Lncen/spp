"""系统日志模块

职责边界：

- SystemLog 记录“系统发生了什么”；
- AuditLog 记录“谁对什么数据做了什么操作”；
- Notification 只负责触达，Automation 只负责决定接下来执行什么。
"""
