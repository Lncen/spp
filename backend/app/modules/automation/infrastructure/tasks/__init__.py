"""自动化模块：Celery 定时任务（按职责拆分子模块）

保持旧导入路径 app.modules.automation.infrastructure.tasks 可用。
"""

from app.modules.automation.infrastructure.tasks.cleanup import (
    cleanup_automation_task_archives,
)
from app.modules.automation.infrastructure.tasks.expired_data import (
    cleanup_expired_data,
)
from app.modules.automation.infrastructure.tasks.order_status import (
    sync_order_status_periodic,
)
from app.modules.automation.infrastructure.tasks.scan import (
    automation_task_scan,
)

__all__ = [
    "automation_task_scan",
    "cleanup_automation_task_archives",
    "cleanup_expired_data",
    "sync_order_status_periodic",
]
