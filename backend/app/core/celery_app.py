"""Celery 应用配置"""
from datetime import timedelta

from celery import Celery

# 注册任务失败记录信号（导入即注册，worker 与 app 共用）
import app.modules.schedule.signals  # noqa: F401
from app.core.config import settings

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

celery_app.conf.beat_schedule = {
    # 商品状态同步 —— 每 30 分钟执行一次
    "同步订单的状态": {
        "task": "app.tasks.order.sync_order_status_periodic",
        "schedule": timedelta(minutes=16),
    },
    "同步商品的状态": {
        "task": "app.tasks.product.sync_product_status",
        "schedule": timedelta(minutes=30),
    },
    # 数据清理 —— 每天凌晨 5:30 执行
    "清理过期数据": {
        "task": "app.tasks.cleanup.cleanup_expired_data",
        "schedule": crontab(hour=5, minute=30),
    },
    # 失败执行记录清理 —— 每天凌晨 6:00 执行
    "清理超期的celery记录": {
        "task": "app.tasks.cleanup.cleanup_schedule_runs",
        "schedule": crontab(hour=6, minute=0),
        'args': (3,),
    },
}


def discover_tasks() -> None:
    """自动发现任务模块（确保模块被导入，Celery 能注册到任务表中）"""
    import app.tasks.cleanup  # noqa: F401
    import app.tasks.order  # noqa: F401
    import app.tasks.product  # noqa: F401
    import app.tasks.supplier  # noqa: F401
