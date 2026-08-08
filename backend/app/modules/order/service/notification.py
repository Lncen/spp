"""订单履约异常通知（通知渠道待接入）"""

import logging

from app.modules.order.models import Order

logger = logging.getLogger(__name__)


def notify_order_exception(*, db_order: Order) -> None:
    """履约失败达上限后通知管理员核对处理

    当前仅记录日志占位，后续在此接入具体通知渠道
    （如邮件 send_email / Webhook / 钉钉等），收件人配置为管理员。
    """
    # TODO: 接入通知渠道，通知管理员处理异常订单
    logger.warning(
        "订单 %s 履约失败已达上限，已标记异常，等待管理员核对处理",
        db_order.order_no,
    )
