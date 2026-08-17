"""自动化模块：创建自动化规则应用服务"""

from sqlalchemy.orm import Session

from app.modules.automation.domain.validation import validate_rule_config
from app.modules.automation.infrastructure.executors import get_executor
from app.modules.automation.models import AutomationRule
from app.modules.automation.repositories.rule import (
    create_rule as create_rule_record,
)
from app.modules.automation.schemas import AutomationRuleCreate


def create_automation_rule(
    *,
    session: Session,
    rule_in: AutomationRuleCreate,
) -> AutomationRule:
    """创建自动化规则，动作类型必须已注册 Executor，否则抛出 ValueError。"""
    validate_rule_config(rule_in.config)
    get_executor(rule_in.action_type)
    rule = create_rule_record(
        session=session,
        name=rule_in.name,
        description=rule_in.description,
        event_type=rule_in.event_type,
        action_type=rule_in.action_type,
        config=rule_in.config,
        priority=rule_in.priority,
        is_active=rule_in.is_active,
    )
    session.commit()
    session.refresh(rule)
    return rule
