"""自动化模块：领域常量"""

from enum import StrEnum


# 事件类型中文展示名（用于任务来源等前端展示），未知类型回退原始事件类型
EVENT_TYPE_LABELS: dict[str, str] = {
    "order.paid": "订单支付",
    "order.fulfillment_failed": "订单履约失败",
}


class AutomationEventStatus(StrEnum):
    """自动化事件状态"""

    PENDING = "pending"  # 待分发
    DISPATCHING = "dispatching"  # 分发中
    DISPATCHED = "dispatched"  # 已分发
    FAILED = "failed"  # 分发失败


class AutomationTaskStatus(StrEnum):
    """自动化任务状态"""

    PENDING = "pending"  # 待执行
    RUNNING = "running"  # 执行中（已被 worker 认领）
    SUCCESS = "success"  # 执行成功
    FAILED = "failed"  # 执行失败（重试耗尽）
    CANCELED = "canceled"  # 已取消（人工取消，不再执行）


class ScheduleType(StrEnum):
    """计划任务调度类型"""

    CRONTAB = "crontab" # 定时任务
    INTERVAL = "interval"# 间隔任务


class IntervalPeriod(StrEnum):
    """Interval 周期单位"""

    DAYS = "days"# 天
    HOURS = "hours"# 小时
    MINUTES = "minutes"# 分钟
    SECONDS = "seconds"# 秒
    MICROSECONDS = "microseconds"# 微秒
