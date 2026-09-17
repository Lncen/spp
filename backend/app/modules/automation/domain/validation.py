"""自动化模块：调度配置领域校验"""

from typing import Any

from app.modules.automation.domain.constants import ScheduleType

MAX_TASK_DELAY_SECONDS = 30 * 24 * 3600
MAX_TASK_MAX_RETRY = 1000


def validate_schedule_input(
    *,
    schedule_type: ScheduleType,
    has_crontab: bool,
    has_interval: bool,
) -> None:
    """校验调度类型与对应配置的配对关系，不满足时抛出 ValueError。"""
    if schedule_type == ScheduleType.CRONTAB:
        if not has_crontab:
            raise ValueError("schedule_type=crontab 时必须提供 crontab 配置")
        if has_interval:
            raise ValueError("schedule_type=crontab 时不能提供 interval 配置")
    elif schedule_type == ScheduleType.INTERVAL:
        if not has_interval:
            raise ValueError("schedule_type=interval 时必须提供 interval 配置")
        if has_crontab:
            raise ValueError("schedule_type=interval 时不能提供 crontab 配置")


def _validate_task_option_int(
    *,
    task_options: dict[str, Any],
    key: str,
    default: int,
    minimum: int,
    maximum: int,
) -> None:
    """校验 task_options 中的整数项，非法值抛出 ValueError。"""
    value = task_options.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"task_options.{key} 必须是整数")
    if isinstance(value, int):
        numeric_value = value
    elif isinstance(value, str):
        try:
            numeric_value = int(value)
        except ValueError as exc:
            raise ValueError(f"task_options.{key} 必须是整数") from exc
    else:
        raise ValueError(f"task_options.{key} 必须是整数")
    if not minimum <= numeric_value <= maximum:
        raise ValueError(
            f"task_options.{key} 必须在 {minimum} 到 {maximum} 之间"
        )


def validate_rule_config(config: dict[str, Any] | None) -> None:
    """校验规则配置中的保留键 task_options，防止生成非法任务参数。"""
    if config is None:
        return
    if not isinstance(config, dict):
        raise ValueError("规则配置 config 必须是对象")

    task_options = config.get("task_options")
    if task_options is None:
        return
    if not isinstance(task_options, dict):
        raise ValueError("task_options 必须是对象")

    _validate_task_option_int(
        task_options=task_options,
        key="delay_seconds",
        default=0,
        minimum=0,
        maximum=MAX_TASK_DELAY_SECONDS,
    )
    _validate_task_option_int(
        task_options=task_options,
        key="max_retry",
        default=3,
        minimum=0,
        maximum=MAX_TASK_MAX_RETRY,
    )
    _validate_task_option_int(
        task_options=task_options,
        key="priority",
        default=0,
        minimum=-1_000_000,
        maximum=1_000_000,
    )
