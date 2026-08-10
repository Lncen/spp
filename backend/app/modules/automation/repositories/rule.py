"""自动化模块：自动化规则数据访问层"""

import uuid
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.modules.automation.models import AutomationRule


def create_rule(
    *,
    session: Session,
    event_type: str,
    action_type: str,
    config: dict[str, Any],
    is_active: bool,
) -> AutomationRule:
    """创建规则记录（不提交，由调用方控制事务）。"""
    rule = AutomationRule(
        event_type=event_type,
        action_type=action_type,
        config=config,
        is_active=is_active,
    )
    session.add(rule)
    return rule


def get_rule_or_404(*, session: Session, rule_id: uuid.UUID) -> AutomationRule:
    """按 ID 获取规则，不存在时抛出 404。"""
    rule = session.get(AutomationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="自动化规则不存在")
    return rule


def count_rules(*, session: Session) -> int:
    """统计规则总数。"""
    return session.exec(select(func.count()).select_from(AutomationRule)).one()


def list_rules(*, session: Session, skip: int, limit: int) -> list[AutomationRule]:
    """分页查询规则，最新创建在前。"""
    return session.exec(
        select(AutomationRule)
        .order_by(AutomationRule.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()


def list_enabled_rules_by_event(
    *,
    session: Session,
    event_type: str,
) -> list[AutomationRule]:
    """查询指定事件类型下已启用的规则。"""
    return session.exec(
        select(AutomationRule).where(
            AutomationRule.event_type == event_type,
            AutomationRule.is_active == True,  # noqa: E712
        )
    ).all()
