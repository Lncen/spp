"""自动化模块：任务执行领域规则"""

from app.modules.automation.domain.constants import AutomationTaskStatus


def should_retry(*, retry_count: int, max_retry: int) -> bool:
    """失败后是否允许重试：已重试次数未达上限。"""
    return retry_count < max_retry


def failure_status(
    *,
    terminal: bool,
    retry_count: int,
    max_retry: int,
) -> AutomationTaskStatus:
    """失败后的目标状态：业务终态或重试耗尽进入 failed，否则回退 pending 等待重试。"""
    if terminal or not should_retry(
        retry_count=retry_count,
        max_retry=max_retry,
    ):
        return AutomationTaskStatus.FAILED
    return AutomationTaskStatus.PENDING


def can_cancel(*, status: AutomationTaskStatus) -> bool:
    """仅待执行任务可取消。"""
    return status == AutomationTaskStatus.PENDING


def can_retry(*, status: AutomationTaskStatus) -> bool:
    """仅失败任务可重新进入队列。"""
    return status == AutomationTaskStatus.FAILED
