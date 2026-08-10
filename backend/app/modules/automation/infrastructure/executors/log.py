"""自动化模块：日志执行器（通用）"""

import logging

from app.modules.automation.infrastructure.executors.base import (
    BaseExecutor,
    register_executor,
)
from app.modules.automation.models import AutomationTask

logger = logging.getLogger(__name__)


@register_executor("log")
class LogExecutor(BaseExecutor):
    """记录日志执行器：仅输出任务参数，用于链路验证与通用占位。"""

    def execute(self, *, task: AutomationTask) -> None:
        logger.info(
            "自动化任务 %s 执行: type=%s payload=%s",
            task.id,
            task.task_type,
            task.payload,
        )
