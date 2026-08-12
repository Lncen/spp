"""自动化模块：执行器基类与注册表"""

from abc import ABC, abstractmethod

from app.modules.automation.models import AutomationTask


class ExecutorTerminalError(Exception):
    """执行器判定任务无法通过重试完成（业务已进入终态），应直接进入失败终态。"""


class BaseExecutor(ABC):
    """自动化任务执行器基类：子类实现 execute，并通过 register_executor 注册。

    幂等约束（所有执行器必须显式声明 idempotent）：
    - idempotent=True：重复执行同一业务任务安全；有外部副作用时
      必须实现 check_already_done 先查后写，防止崩溃重跑产生重复副作用；
    - idempotent=False：不保证重复执行安全，类 docstring 必须标注风险。
    """

    idempotent: bool = False

    @abstractmethod
    def execute(self, *, task: AutomationTask) -> None:
        """执行任务，失败时抛出异常交由任务池重试 / 失败处理。"""

    def check_already_done(self, *, task: AutomationTask) -> bool:
        """预执行幂等检查：业务目标已达成时返回 True，任务池将直接标记成功并归档。

        默认返回 False；天然幂等（无外部副作用）执行器无需覆盖。
        有外部副作用且 idempotent=True 的执行器必须覆盖，
        基于业务唯一标识（如订单号 / 外部单号）先查后写。
        """
        return False


EXECUTORS: dict[str, type[BaseExecutor]] = {}


def register_executor(task_type: str):
    """类装饰器：将执行器注册到任务类型映射，并强制校验幂等声明。"""

    def decorator(cls: type[BaseExecutor]) -> type[BaseExecutor]:
        if "idempotent" not in cls.__dict__:
            raise TypeError(
                f"执行器 {cls.__name__!r} 必须显式声明 idempotent（True/False），"
                "确保重复执行同一业务任务的行为有明确约定"
            )
        EXECUTORS[task_type] = cls
        return cls

    return decorator


def get_executor(task_type: str) -> type[BaseExecutor]:
    """按任务类型获取执行器类，未注册时抛出 ValueError。"""
    try:
        return EXECUTORS[task_type]
    except KeyError as e:
        raise ValueError(f"未注册的任务类型: {task_type}") from e
