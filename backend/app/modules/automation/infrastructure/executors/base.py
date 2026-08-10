"""自动化模块：执行器基类与注册表"""

from abc import ABC, abstractmethod

from app.modules.automation.models import AutomationTask


class ExecutorTerminalError(Exception):
    """执行器判定任务无法通过重试完成（业务已进入终态），应直接进入失败终态。"""


class BaseExecutor(ABC):
    """自动化任务执行器基类：子类实现 execute，并通过 register_executor 注册。"""

    @abstractmethod
    def execute(self, *, task: AutomationTask) -> None:
        """执行任务，失败时抛出异常交由任务池重试 / 失败处理。"""


EXECUTORS: dict[str, type[BaseExecutor]] = {}


def register_executor(task_type: str):
    """类装饰器：将执行器注册到任务类型映射。"""

    def decorator(cls: type[BaseExecutor]) -> type[BaseExecutor]:
        EXECUTORS[task_type] = cls
        return cls

    return decorator


def get_executor(task_type: str) -> type[BaseExecutor]:
    """按任务类型获取执行器类，未注册时抛出 ValueError。"""
    try:
        return EXECUTORS[task_type]
    except KeyError as e:
        raise ValueError(f"未注册的任务类型: {task_type}") from e
