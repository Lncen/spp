"""自动化模块：任务归档查询应用服务"""

from sqlalchemy.orm import Session

from app.modules.automation.domain.constants import AutomationTaskStatus
from app.modules.automation.models import AutomationTaskArchive
from app.modules.automation.repositories.task import (
    count_archives,
    list_archives,
)
from app.modules.automation.schemas import (
    AutomationTaskArchivePublic,
    AutomationTaskArchivesPublic,
)


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
    return AutomationTaskArchivesPublic(
        data=[to_archive_public(archive) for archive in archives],
        count=count,
    )


def to_archive_public(
    archive: AutomationTaskArchive,
) -> AutomationTaskArchivePublic:
    """将 AutomationTaskArchive 转为公开响应模型。"""
    return AutomationTaskArchivePublic.model_validate(archive)
