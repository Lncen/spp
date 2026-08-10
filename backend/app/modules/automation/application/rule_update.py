"""自动化模块：更新自动化规则应用服务"""

import uuid

from sqlalchemy.orm import Session

from app.modules.automation.infrastructure.executors import get_executor
from app.modules.automation.models import AutomationRule
from app.modules.automation.repositories.rule import get_rule_or_404
from app.modules.automation.schemas import AutomationRuleUpdate


def update_automation_rule(
    *,
    session: Session,
    rule_id: uuid.UUID,
    rule_in: AutomationRuleUpdate,
) -> AutomationRule:
    """更新自动化规则，修改动作类型时校验已注册 Executor。"""
    rule = get_rule_or_404(session=session, rule_id=rule_id)
    update_dict = rule_in.model_dump(exclude_unset=True)
    action_type = update_dict.get("action_type")
    if action_type is not None:
        get_executor(action_type)
    for field, value in update_dict.items():
        setattr(rule, field, value)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule
