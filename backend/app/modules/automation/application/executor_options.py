"""自动化模块：执行器选项应用服务"""

from app.modules.automation.infrastructure.executors import EXECUTORS
from app.modules.automation.schemas import TaskOption


def list_executor_options() -> list[TaskOption]:
    """列出已注册的 Executor，供前端任务类型下拉使用。"""
    options: list[TaskOption] = []
    for task_type, executor_cls in sorted(EXECUTORS.items()):
        options.append(
            TaskOption(
                value=task_type,
                label=task_type,
                doc=executor_cls.__doc__,
            )
        )
    return options
