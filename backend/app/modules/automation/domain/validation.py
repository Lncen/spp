"""自动化模块：调度配置领域校验"""

from app.modules.automation.domain.constants import ScheduleType
from app.modules.automation.schemas import CrontabScheduleIn, IntervalScheduleIn


def validate_schedule_input(
    *,
    schedule_type: ScheduleType,
    crontab: CrontabScheduleIn | None,
    interval: IntervalScheduleIn | None,
) -> None:
    """校验调度类型与对应配置的配对关系，不满足时抛出 ValueError。"""
    if schedule_type == ScheduleType.CRONTAB and crontab is None:
        raise ValueError("schedule_type=crontab 时必须提供 crontab 配置")
    if schedule_type == ScheduleType.INTERVAL and interval is None:
        raise ValueError("schedule_type=interval 时必须提供 interval 配置")
