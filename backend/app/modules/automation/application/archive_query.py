"""自动化模块：任务归档查询应用服务"""

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
    AutomationTaskArchive,
)
from app.modules.automation.repositories.task import (
    count_archives,
    list_archives,
)
from app.modules.automation.schemas import (
    AutomationTaskArchivePublic,
    AutomationTaskArchivesPublic,
)


def _archive_sources_map(
    *,
    session: Session,
    archives: list[AutomationTaskArchive],
) -> dict[uuid.UUID, tuple[str | None, str | None]]:
    """批量查询归档任务来源，避免逐条查询造成 N+1。"""
    event_ids = {a.event_id for a in archives if a.event_id is not None}
    rule_ids = {a.rule_id for a in archives if a.rule_id is not None}
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
        archive.id: (
            events.get(archive.event_id) if archive.event_id else None,
            rules.get(archive.rule_id) if archive.rule_id else None,
        )
        for archive in archives
    }


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
    sources = _archive_sources_map(session=session, archives=archives)
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
    source: tuple[str | None, str | None] | None = None,
) -> AutomationTaskArchivePublic:
    """将 AutomationTaskArchive 转为公开响应模型，可选附带来源信息。"""
    public = AutomationTaskArchivePublic.model_validate(archive)
    if source is not None:
        public.event_type_label, public.rule_name = source
    return public
