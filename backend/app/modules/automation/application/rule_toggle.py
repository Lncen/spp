"""自动化模块：启用/停用自动化规则应用服务"""

import uuid

from sqlalchemy.orm import Session

from app.modules.automation.models import AutomationRule
from app.modules.automation.repositories.rule import get_rule_or_404


def toggle_automation_rule(
    *,
    session: Session,
    rule_id: uuid.UUID,
) -> AutomationRule:
    """启用或停用自动化规则。"""
    rule = get_rule_or_404(session=session, rule_id=rule_id)
    rule.toggle_active()
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule
