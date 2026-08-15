"""Celery 应用配置"""

from celery import Celery  # type: ignore[import-untyped]

from app.core.config import settings
from app.modules.automation.infrastructure.beat_schedule import init_tasks

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


celery_app.conf.beat_schedule = init_tasks

# shared_task 返回的是 celery.local 线程本地代理：FastAPI 同步接口在线程池线程中执行，
# 若不显式设默认应用，`.delay()` 会绑定到新建的默认 AMQP broker（连接被拒），
# 导致入队失败。set_default() 将本应用设为全局默认，所有线程统一走配置的 Redis broker。
celery_app.set_default()


def discover_tasks() -> None:
    """自动发现任务模块（确保模块被导入，Celery 能注册到任务表中）"""
    import app.modules.automation.infrastructure.event_listeners  # noqa: F401
    import app.modules.automation.infrastructure.tasks  # noqa: F401
    import app.modules.automation.infrastructure.tasks.auth_cleanup  # noqa: F401
    import app.modules.automation.infrastructure.tasks.cleanup  # noqa: F401
    import app.modules.automation.infrastructure.tasks.expired_data  # noqa: F401
    import app.modules.automation.infrastructure.tasks.notification_cleanup  # noqa: F401
    import app.modules.automation.infrastructure.tasks.notification_delivery  # noqa: F401
    import app.modules.automation.infrastructure.tasks.order_cleanup  # noqa: F401
    import app.modules.automation.infrastructure.tasks.order_status  # noqa: F401
    import app.modules.automation.infrastructure.tasks.product_sync  # noqa: F401
    import app.modules.automation.infrastructure.tasks.scan  # noqa: F401
    import app.modules.automation.infrastructure.tasks.supplier_sync  # noqa: F401
    import app.modules.automation.infrastructure.tasks.wallet_cleanup  # noqa: F401
    import app.modules.notification.infrastructure.event_listeners  # noqa: F401
