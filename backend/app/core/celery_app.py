"""Celery 应用配置"""
from datetime import timedelta

from celery import Celery

# 注册任务失败记录信号（导入即注册，worker 与 app 共用）
import app.modules.schedule.signals  # noqa: F401
from app.core.config import settings

from app.tasks.main import init_tasks

celery_app = Celery(
    "spp",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# 时区与任务序列化
celery_app.conf.update(
    timezone="Asia/Shanghai",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_scheduler="sqlalchemy_celery_beat.schedulers:DatabaseScheduler",
    beat_dburi=str(settings.SQLALCHEMY_DATABASE_URI),
    beat_schema="celery_schema",
)


# 定时任务配置
from celery.schedules import crontab  # noqa: E402

celery_app.conf.beat_schedule = init_tasks


def discover_tasks() -> None:
    """自动发现任务模块（确保模块被导入，Celery 能注册到任务表中）"""
    import app.tasks.cleanup  # noqa: F401
    import app.tasks.order  # noqa: F401
    import app.tasks.product  # noqa: F401
    import app.tasks.supplier  # noqa: F401
