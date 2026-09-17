"""自动化模块：任务池执行状态流转应用服务

任务池扫描（`infrastructure/tasks/scan.py`）在每次执行 Executor 后调用本模块：
先按认领令牌锁定任务行，再由 `domain/execution.py` 的规则判定目标状态，
最后交给 `repositories/task.py` 持久化。
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.automation.domain.constants import AutomationTaskStatus
from app.modules.automation.domain.execution import failure_status
from app.modules.automation.models import AutomationTask
from app.modules.automation.repositories.task import (
    apply_task_auto_retry,
    apply_task_failure,
    apply_task_success,
    lock_claimed_task,
)


def finish_task_successfully(
    *,
    session: Session,
    task: AutomationTask,
    expected_claimed_at: datetime | None = None,
) -> AutomationTaskStatus | None:
    """成功终态：锁定任务行后归档，返回实际落库状态；任务已被接管时返回 None。"""
    locked = lock_claimed_task(
        session=session,
        task=task,
        expected_claimed_at=expected_claimed_at,
    )
    if locked is None:
        return None
    apply_task_success(session=session, task=locked)
    return AutomationTaskStatus.SUCCESS


def handle_task_failure(
    *,
    session: Session,
    task: AutomationTask,
    error_message: str,
    now: datetime,
    terminal: bool = False,
    expected_claimed_at: datetime | None = None,
) -> AutomationTaskStatus | None:
    """执行失败处理：业务终态或重试耗尽失败归档，否则回退待执行等待自动重试。

    terminal=True 表示业务已进入终态（如订单转人工确认），跳过重试；
    返回实际落库的状态，任务已被其他 worker 接管时返回 None。
    """
    locked = lock_claimed_task(
        session=session,
        task=task,
        expected_claimed_at=expected_claimed_at,
    )
    if locked is None:
        return None
    target_status = failure_status(
        terminal=terminal,
        retry_count=locked.retry_count,
        max_retry=locked.max_retry,
    )
    if target_status == AutomationTaskStatus.PENDING:
        apply_task_auto_retry(
            session=session,
            task=locked,
            error_message=error_message,
            now=now,
        )
    else:
        apply_task_failure(
            session=session,
            task=locked,
            error_message=error_message,
            now=now,
        )
    return target_status
