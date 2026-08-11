"""通知中心：通知规则注册表与内置规则

规则为代码级配置（dataclass），通过 register_rule 显式注册；
注册动作由 register_builtin_rules() 触发，不在 __init__.py 中产生副作用。
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from jinja2 import Template

from app.modules.notification.domain.constants import RecipientRole


@dataclass(frozen=True)
class RecipientsSpec:
    """接收人配置：二选一（role 优先于 user_ids 时显式互斥由调用方保证）"""

    role: str | None = None
    user_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class NotificationRule:
    """通知规则：事件类型 -> 模板 + 接收人 + 渠道"""

    event_type: str
    title_template: str
    content_template: str
    channels: tuple[str, ...]
    recipients: RecipientsSpec
    email_template: str | None = None
    enabled: bool = True


RULES: dict[str, NotificationRule] = {}


def register_rule(rule: NotificationRule) -> NotificationRule:
    """注册一条通知规则（按事件类型唯一）"""
    RULES[rule.event_type] = rule
    return rule


def get_rules_for_event(event_type: str) -> list[NotificationRule]:
    """按事件类型获取已启用规则"""
    rule = RULES.get(event_type)
    return [rule] if rule and rule.enabled else []


def render_notification_template(template: str, payload: dict[str, Any]) -> str:
    """用事件载荷渲染通知标题/内容模板"""
    return Template(template).render(**payload)


def register_builtin_rules() -> None:
    """注册内置通知规则（幂等），由应用层显式调用"""
    if "order.fulfillment_failed" in RULES:
        return
    register_rule(
        NotificationRule(
            event_type="order.fulfillment_failed",
            title_template="订单履约异常：{{ order_no }}",
            content_template="订单 {{ order_no }} 履约异常，需管理员人工核对处理。",
            channels=("in_app", "email"),
            recipients=RecipientsSpec(role=RecipientRole.SUPERUSER),
            email_template="notification_order_failed.html",
        )
    )
