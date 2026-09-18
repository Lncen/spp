"""操作审计写入应用服务"""

import uuid
from typing import Any

from sqlmodel import Session

from app.modules.system_log.models import AuditLog
from app.modules.system_log.repositories.audit_log import create_audit_log
from app.modules.user.models import User


def record_audit_log(
    *,
    session: Session,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    changes: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    event_id: uuid.UUID | None = None,
) -> AuditLog:
    """写入一条操作审计记录并提交，供关键管理操作调用
        写入的参数使用中文描述
    """

    actor_identifier = (actor.email or actor.username or "system") if actor is not None else "system"
    audit_log = create_audit_log(
        session=session,
        actor_id=actor.id if actor else None,
        actor_identifier=actor_identifier,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=before or {},
        after=after or {},
        changes=changes or {},
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
        event_id=event_id,
    )
    session.commit()
    session.refresh(audit_log)
    return audit_log
