"""自动化模块：任务执行器"""

from app.modules.automation.infrastructure.executors import (
    log,  # noqa: F401  注册内置执行器
    order_submit,  # noqa: F401  注册订单履约执行器
)
from app.modules.automation.infrastructure.executors.base import (
    EXECUTORS,
    BaseExecutor,
    ExecutorTerminalError,
    get_executor,
    register_executor,
)

__all__ = [
    "EXECUTORS",
    "BaseExecutor",
    "ExecutorTerminalError",
    "get_executor",
    "register_executor",
]
