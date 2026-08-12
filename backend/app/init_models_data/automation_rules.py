"""自动化规则初始数据"""

import logging
import uuid

from sqlmodel import Session, select

from app.core.config import settings
from app.modules.automation.models import AutomationRule

logger = logging.getLogger(__name__)

# 订单履约规则的固定 UUID（确保幂等性）
ORDER_PAID_RULE_UUID = uuid.UUID("b0000000-0000-0000-0000-000000000001")

# 默认自动化规则：max_retry 对齐订单履约失败上限，连续失败后订单转人工确认
AUTOMATION_RULES = [
    # 订单支付 -> 提交供应商订单
    {
        "id": ORDER_PAID_RULE_UUID,
        "name": "订单支付 → 提交供应商订单",
        "description": "订单创建成功（已付款）后自动向上游提交履约订单",
        "event_type": "order.paid",
        "action_type": "submit_supplier_order",
        "config": {
            "task_options": {
                "priority": 0,
                "max_retry": settings.ORDER_FULFILL_FAIL_LIMIT,
            }
        },
        "priority": 0,
        "is_active": True,
    },
]


def seed_automation_rules(*, session: Session) -> None:
    """播种默认自动化规则，幂等安全（已存在则跳过）"""
    added_count = 0
    for data in AUTOMATION_RULES:
        existing = session.exec(
            select(AutomationRule).where(
                AutomationRule.event_type == data["event_type"],
                AutomationRule.action_type == data["action_type"],
            )
        ).first()
        if existing:
            logger.info(
                "自动化规则 '%s → %s' 已存在，跳过。",
                data["event_type"],
                data["action_type"],
            )
            continue
        session.add(
            AutomationRule(
                id=data["id"],
                name=data["name"],
                description=data.get("description"),
                event_type=data["event_type"],
                action_type=data["action_type"],
                config=data["config"],
                priority=data.get("priority", 0),
                is_active=data["is_active"],
            )
        )
        added_count += 1
    if added_count:
        session.commit()
        logger.info("成功播种 %d 条自动化规则！", added_count)
