"""自动化模块：订单状态同步 Celery 定时任务"""

from celery import shared_task
from sqlmodel import Session, select

from app.core.db import engine
from app.modules.order.application.sync import sync_orders_status
from app.modules.order.domain.constants import SYNCABLE_ORDER_STATUSES
from app.modules.order.models import Order
from app.modules.product.constants import RedeemType


@shared_task(
    ignore_result=False,
    name="app.modules.order.tasks.sync_order_status_periodic",
)
def sync_order_status_periodic() -> dict:
    """定时批量同步上游订单状态（仅处理可同步状态的 API 履约订单）"""
    stats = {"checked": 0, "updated": 0, "unchanged": 0, "errors": []}
    try:
        with Session(engine) as session:
            orders = session.exec(
                select(Order).where(
                    Order.fulfillment_type == RedeemType.AUTO_API,
                    Order.supplier_order_id.is_not(None),
                    Order.status.in_(tuple(SYNCABLE_ORDER_STATUSES)),
                )
            ).all()
            stats["checked"] = len(orders)
            # 退单申请已改由 automation 事件驱动
            # （order.after_sale_applied → apply_supplier_refund 执行器），此处只同步状态

            # 同步订单状态
            before = {order.id: order.status for order in orders}
            updated = sync_orders_status(
                session=session,
                db_orders=list(orders),
            )
            stats["updated"] = sum(
                1 for order in updated if before.get(order.id) != order.status
            )
            stats["unchanged"] = len(updated) - stats["updated"]
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(str(exc))
    return stats
