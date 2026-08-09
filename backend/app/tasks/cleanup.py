"""数据清理定时任务"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from celery import shared_task
from sqlalchemy import delete
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.modules.schedule.models import ScheduleRun

SCHEDULE_RUN_RETENTION_DAYS = 30


@shared_task(ignore_result=False)
def cleanup_expired_data() -> dict:
    """清理过期数据

    当前清理项：
    1. 删除超过 30 天未使用的临时上传文件（孤立的磁盘文件）
    2. 标记软删除超过 30 天的记录

    返回清理统计。
    """
    stats = {
        "orphan_files_deleted": 0,
        "records_cleaned": 0,
        "errors": [],
    }

    try:
        with Session(engine) as session:
            # 1. 清理数据库中被软删除且超过 30 天的记录
            # TODO: 如果有 is_active 标记的表，清理已软删除的记录

            session.commit()

        # 2. 清理磁盘上孤立的临时文件（超过 24 小时未被引用的上传文件）
        tmp_dir = Path(settings.UPLOAD_DIR) / "tmp"
        if tmp_dir.exists():
            tmp_cutoff = datetime.now().timestamp() - 86400  # 24 小时
            for f in tmp_dir.iterdir():
                if f.is_file() and f.stat().st_mtime < tmp_cutoff:
                    f.unlink(missing_ok=True)
                    stats["orphan_files_deleted"] += 1

    except Exception as e:
        stats["errors"].append(str(e))

    return stats



@shared_task(ignore_result=False)
def cleanup_schedule_runs(retention_days: int = 30) -> dict:
    """清理超过保留期的计划任务失败执行记录"""
    stats = {"schedule_runs_deleted": 0, "errors": []}

    # 使用传入的参数计算截止时间
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    try:
        with Session(engine) as session:
            # 使用 exec() 代替 execute()
            result = session.exec(
                delete(ScheduleRun).where(ScheduleRun.created_at < cutoff)
            )
            stats["schedule_runs_deleted"] = result.rowcount or 0
            session.commit()
    except Exception as e:
        stats["errors"].append(str(e))

    return stats
