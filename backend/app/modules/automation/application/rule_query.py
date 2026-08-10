"""自动化模块：自动化规则查询应用服务"""

import uuid

from sqlalchemy.orm import Session

from app.modules.automation.models import AutomationRule
from app.modules.automation.repositories.rule import (
    count_rules,
    get_rule_or_404,
    list_rules,
)
from app.modules.automation.schemas import (
    AutomationRulePublic,
    AutomationRulesPublic,
)

__all__ = [
    "get_automation_rule_public",
    "list_automation_rules",
    "to_automation_rule_public",
]


def list_automation_rules(
    *,
    session: Session,
    skip: int,
    limit: int,
) -> AutomationRulesPublic:
    """分页获取自动化规则列表。"""
    count = count_rules(session=session)
    rules = list_rules(session=session, skip=skip, limit=limit)
    return AutomationRulesPublic(
        data=[to_automation_rule_public(rule) for rule in rules],
        count=count,
    )


def get_automation_rule_public(
    *,
    session: Session,
    rule_id: uuid.UUID,
) -> AutomationRulePublic:
    """按 ID 获取自动化规则公开响应。"""
    return to_automation_rule_public(
        get_rule_or_404(session=session, rule_id=rule_id)
    )


def to_automation_rule_public(rule: AutomationRule) -> AutomationRulePublic:
    """将 AutomationRule 转为公开响应模型。"""
    return AutomationRulePublic.model_validate(rule)
