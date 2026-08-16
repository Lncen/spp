"""数据备份定时任务"""

import logging

from celery import shared_task
from sqlmodel import Session

from app.core.db import engine
from app.modules.backup.application.create import create_backup
from app.modules.system_log.application.audit_log_create import record_audit_log

logger = logging.getLogger(__name__)


@shared_task(
    ignore_result=False,
    name="app.modules.backup.infrastructure.tasks.create_backup",
)
def create_backup_task() -> dict:
    """定时创建数据备份并记录系统操作审计。"""
    try:
        with Session(engine) as session:
            result = create_backup(session=session)
            record_audit_log(
                session=session,
                actor=None,
                action="backup.create",
                resource_type="backup",
                resource_id=result.filename,
                after=result.model_dump(mode="json"),
                changes={"filename": {"old": None, "new": result.filename}},
            )
            return result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        logger.exception("数据备份任务执行失败")
        return {"error": str(exc)}
