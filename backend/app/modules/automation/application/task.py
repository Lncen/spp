"""自动化模块：任务池应用服务

按业务能力归组：任务创建与查询、归档查询、取消 / 重试、执行器清单、来源组装。
任务池的执行状态流转见 `application/task_execution.py`。
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.modules.automation.domain.constants import (
    EVENT_TYPE_LABELS,
    AutomationTaskStatus,
)
from app.modules.automation.domain.execution import can_cancel, can_retry
from app.modules.automation.infrastructure.executors import (
    EXECUTORS,
    get_executor,
)
from app.modules.automation.models import (
    AutomationTask,
    AutomationTaskArchive,
)
from app.modules.automation.repositories.event import map_event_types
from app.modules.automation.repositories.rule import map_rule_names
from app.modules.automation.repositories.task import (
    apply_task_canceled,
    count_archives,
    count_tasks,
    get_archived_task_or_404,
    get_task,
    get_task_or_404,
    list_archives,
    list_tasks,
    reset_task_for_retry,
    restore_task_from_archive,
)
from app.modules.automation.repositories.task import (
    create_task as create_task_record,
)
from app.modules.automation.schemas import (
    AutomationTaskArchivePublic,
    AutomationTaskArchivesPublic,
    AutomationTaskCreate,
    AutomationTaskPublic,
    AutomationTasksPublic,
    TaskOption,
)

# 任务来源：(事件类型展示名, 规则名称)，无对应来源时为 None
TaskSource = tuple[str | None, str | None]


def create_automation_task(
    *,
    session: Session,
    task_in: AutomationTaskCreate,
) -> AutomationTask:
    """创建自动化任务，任务类型必须已注册 Executor，否则抛出 ValueError。"""
    get_executor(task_in.task_type)
    task = create_task_record(
        session=session,
        task_type=task_in.task_type,
        payload=task_in.payload,
        priority=task_in.priority,
        execute_at=task_in.execute_at,
        max_retry=task_in.max_retry,
    )
    session.commit()
    session.refresh(task)
    return task


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
    sources = build_task_sources(session=session, items=tasks)
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
    sources = build_task_sources(session=session, items=[task])
    return to_automation_task_public(
        task,
        source=sources[task.id],
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


def cancel_automation_task(
    *,
    session: Session,
    task_id: uuid.UUID,
) -> AutomationTask:
    """取消待执行任务，非待执行状态时抛出 ValueError。"""
    task = get_task_or_404(session=session, task_id=task_id)
    if not can_cancel(status=task.status):
        raise ValueError("仅待执行任务可取消")
    apply_task_canceled(session=session, task=task)
    return task


def retry_automation_task(
    *,
    session: Session,
    task_id: uuid.UUID,
) -> AutomationTask:
    """失败任务重新进入队列：任务池中直接重置，已归档则从归档表恢复。"""
    task = get_task(session=session, task_id=task_id)
    if task is not None:
        if not can_retry(status=task.status):
            raise ValueError("仅失败任务可重新进入队列")
        reset_task_for_retry(session=session, task=task)
        return task

    archived = get_archived_task_or_404(session=session, task_id=task_id)
    if not can_retry(status=archived.status):
        raise ValueError("仅失败任务可重新进入队列")
    return restore_task_from_archive(session=session, archived=archived)


def list_automation_task_archives(
    *,
    session: Session,
    skip: int,
    limit: int,
    status: AutomationTaskStatus | None,
) -> AutomationTaskArchivesPublic:
    """分页获取自动化任务归档列表。"""
    count = count_archives(session=session, status=status)
    archives = list_archives(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
    )
    sources = build_task_sources(session=session, items=archives)
    return AutomationTaskArchivesPublic(
        data=[
            to_archive_public(archive, source=sources[archive.id])
            for archive in archives
        ],
        count=count,
    )


def to_archive_public(
    archive: AutomationTaskArchive,
    *,
    source: TaskSource | None = None,
) -> AutomationTaskArchivePublic:
    """将 AutomationTaskArchive 转为公开响应模型，可选附带来源信息。"""
    public = AutomationTaskArchivePublic.model_validate(archive)
    if source is not None:
        public.event_type_label, public.rule_name = source
    return public


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


def build_task_sources(
    *,
    session: Session,
    items: Sequence[AutomationTask | AutomationTaskArchive],
) -> dict[uuid.UUID, TaskSource]:
    """批量组装任务来源（事件类型展示名、规则名称），避免逐条查询造成 N+1。"""
    event_ids = {item.event_id for item in items if item.event_id is not None}
    rule_ids = {item.rule_id for item in items if item.rule_id is not None}
    event_types = map_event_types(session=session, event_ids=event_ids)
    rule_names = map_rule_names(session=session, rule_ids=rule_ids)
    return {
        item.id: (
            _event_type_label(event_id=item.event_id, event_types=event_types),
            rule_names.get(item.rule_id) if item.rule_id else None,
        )
        for item in items
    }


def _event_type_label(
    *,
    event_id: uuid.UUID | None,
    event_types: dict[uuid.UUID, str],
) -> str | None:
    """事件类型展示名：未知类型回退原始事件类型名，无来源事件时为 None。"""
    event_type = event_types.get(event_id) if event_id else None
    if event_type is None:
        return None
    return EVENT_TYPE_LABELS.get(event_type, event_type)
