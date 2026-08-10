"""自动化模块：删除自动化规则应用服务"""

import uuid

from sqlalchemy.orm import Session

from app.modules.automation.repositories.rule import get_rule_or_404


def delete_automation_rule(*, session: Session, rule_id: uuid.UUID) -> None:
    """删除自动化规则。"""
    rule = get_rule_or_404(session=session, rule_id=rule_id)
    session.delete(rule)
    session.commit()
