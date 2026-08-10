"""自动化模块：事件分发应用服务（按规则生成任务）"""

from sqlmodel import Session

from app.core.db import engine
from app.modules.automation.models import AutomationEvent, AutomationTask
from app.modules.automation.repositories.rule import (
    list_enabled_rules_by_event,
)
from app.modules.automation.repositories.task import create_task


def dispatch_event(*, event: AutomationEvent) -> list[AutomationTask]:
    """按事件类型查找启用的规则，为每条规则创建一个自动化任务。"""
    with Session(engine) as session:
        rules = list_enabled_rules_by_event(
            session=session,
            event_type=event.event_type,
        )
        tasks = []
        for rule in rules:
            config = dict(rule.config)
            task_options = config.pop("task_options", {})
            payload = {**event.payload, **config}
            task = create_task(
                session=session,
                task_type=rule.action_type,
                payload=payload,
                priority=int(task_options.get("priority", 0)),
                max_retry=int(task_options.get("max_retry", 3)),
            )
            tasks.append(task)
        session.commit()
        for task in tasks:
            session.refresh(task)
    return tasks
