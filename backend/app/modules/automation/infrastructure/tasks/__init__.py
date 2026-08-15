"""自动化模块：Celery 定时任务（按职责拆分子模块）

全项目 Celery 任务统一收敛到本目录；通过包 __init__.py 统一导出，
保持 app.modules.automation.infrastructure.tasks 导入路径可用。
"""

from app.modules.automation.infrastructure.tasks.auth_cleanup import (
    cleanup_expired_refresh_tokens,
)
from app.modules.automation.infrastructure.tasks.cleanup import (
    cleanup_automation_task_archives,
)
from app.modules.automation.infrastructure.tasks.expired_data import (
    cleanup_expired_data,
)
from app.modules.automation.infrastructure.tasks.notification_cleanup import (
    cleanup_notification_records,
)
from app.modules.automation.infrastructure.tasks.notification_delivery import (
    deliver_notification,
    enqueue_delivery,
    requeue_stale_notification_deliveries,
)
from app.modules.automation.infrastructure.tasks.order_cleanup import (
    cleanup_completed_orders,
)
from app.modules.automation.infrastructure.tasks.order_status import (
    sync_order_status_periodic,
)
from app.modules.automation.infrastructure.tasks.product_sync import (
    sync_product_status,
)
from app.modules.automation.infrastructure.tasks.scan import (
    automation_task_scan,
)
from app.modules.automation.infrastructure.tasks.supplier_sync import (
    dispatch_upstream_products_sync,
    sync_upstream_products,
)
from app.modules.automation.infrastructure.tasks.wallet_cleanup import (
    cleanup_wallet_transactions,
)

__all__ = [
    "automation_task_scan",
    "cleanup_automation_task_archives",
    "cleanup_completed_orders",
    "cleanup_expired_data",
    "cleanup_expired_refresh_tokens",
    "cleanup_notification_records",
    "cleanup_wallet_transactions",
    "deliver_notification",
    "dispatch_upstream_products_sync",
    "enqueue_delivery",
    "requeue_stale_notification_deliveries",
    "sync_order_status_periodic",
    "sync_product_status",
    "sync_upstream_products",
]
