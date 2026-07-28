"""Celery 应用配置"""

from celery import Celery

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
)


# 定时任务配置
from celery.schedules import crontab  # noqa: E402

celery_app.conf.beat_schedule = {
    # 商品状态同步 —— 每 30 分钟执行一次
    "sync-product-status-every-30-minutes": {
        "task": "app.tasks.product.sync_product_status",
        "schedule": crontab(minute="*/30"),
    },
    # 数据清理 —— 每天凌晨 3:00 执行
    "cleanup-expired-data-daily": {
        "task": "app.tasks.cleanup.cleanup_expired_data",
        "schedule": crontab(hour=3, minute=0),
    },
}


def discover_tasks() -> None:
    """自动发现任务模块（确保模块被导入，Celery 能注册到任务表中）"""
    import app.tasks.product  # noqa: F401
    import app.tasks.cleanup  # noqa: F401
