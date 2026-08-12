"""自动化模块：自动化任务查询应用服务"""

import uuid

from sqlalchemy.orm import Session
from sqlmodel import select

from app.modules.automation.domain.constants import (
    EVENT_TYPE_LABELS,
    AutomationTaskStatus,
)
from app.modules.automation.models import (
    AutomationEvent,
    AutomationRule,
    AutomationTask,
)
from app.modules.automation.repositories.task import (
    count_tasks,
    get_task_or_404,
    list_tasks,
)
from app.modules.automation.schemas import (
    AutomationTaskPublic,
    AutomationTasksPublic,
)

__all__ = [
    "get_automation_task_public",
    "list_automation_tasks",
    "to_automation_task_public",
]

TaskSource = tuple[str | None, str | None]


def _task_source(*, session: Session, task: AutomationTask) -> TaskSource:
    """查询单个任务的来源（事件类型、规则名称），手动创建任务返回 (None, None)。"""
    event_type = None
    rule_name = None
    if task.event_id is not None:
        event = session.get(AutomationEvent, task.event_id)
        if event:
            event_type = EVENT_TYPE_LABELS.get(event.event_type, event.event_type)
    if task.rule_id is not None:
        rule = session.get(AutomationRule, task.rule_id)
        rule_name = rule.name if rule else None
    return event_type, rule_name


def _task_sources_map(
    *,
    session: Session,
    tasks: list[AutomationTask],
) -> dict[uuid.UUID, TaskSource]:
    """批量查询任务来源，避免逐条查询造成 N+1。"""
    event_ids = {task.event_id for task in tasks if task.event_id is not None}
    rule_ids = {task.rule_id for task in tasks if task.rule_id is not None}
    events: dict[uuid.UUID, str] = {}
    rules: dict[uuid.UUID, str] = {}
    if event_ids:
        events = {
            event.id: EVENT_TYPE_LABELS.get(event.event_type, event.event_type)
            for event in session.exec(
                select(AutomationEvent).where(AutomationEvent.id.in_(event_ids))
            ).all()
        }
    if rule_ids:
        rules = {
            rule.id: rule.name
            for rule in session.exec(
                select(AutomationRule).where(AutomationRule.id.in_(rule_ids))
            ).all()
        }
    return {
        task.id: (
            events.get(task.event_id) if task.event_id else None,
            rules.get(task.rule_id) if task.rule_id else None,
        )
        for task in tasks
    }


def list_automation_tasks(
    *,
    session: Session,
    skip: int,
    limit: int,
    status: AutomationTaskStatus | None,
) -> AutomationTasksPublic:
    """分页获取自动化任务列表。"""
    count = count_tasks(session=session, status=status)
    tasks = list_tasks(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
    )
    sources = _task_sources_map(session=session, tasks=tasks)
    return AutomationTasksPublic(
        data=[
            to_automation_task_public(task, source=sources[task.id])
            for task in tasks
        ],
        count=count,
    )


def get_automation_task_public(
    *,
    session: Session,
    task_id: uuid.UUID,
) -> AutomationTaskPublic:
    """按 ID 获取自动化任务公开响应。"""
    task = get_task_or_404(session=session, task_id=task_id)
    return to_automation_task_public(
        task,
        source=_task_source(session=session, task=task),
    )


def to_automation_task_public(
    task: AutomationTask,
    *,
    source: TaskSource | None = None,
) -> AutomationTaskPublic:
    """将 AutomationTask 转为公开响应模型，可选附带来源信息。"""
    public = AutomationTaskPublic.model_validate(task)
    if source is not None:
        public.event_type_label, public.rule_name = source
    return public
