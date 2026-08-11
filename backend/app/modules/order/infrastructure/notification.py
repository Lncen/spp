"""订单模块：履约异常通知（发布业务事件，由统一通知中心处理）"""

import logging

from app.core.event_bus import publish as publish_event
from app.modules.order.models import Order

logger = logging.getLogger(__name__)


def notify_order_exception(*, db_order: Order) -> None:
    """订单履约异常：发布事件，由 notification 模块按规则生成管理员通知"""
    publish_event(
        event_type="order.fulfillment_failed",
        payload={
            "order_id": str(db_order.id),
            "order_no": db_order.order_no,
            "remark": db_order.remark or "",
        },
    )
    logger.warning(
        "订单 %s 履约异常，已发布通知事件",
        db_order.order_no,
    )
