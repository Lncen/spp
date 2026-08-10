"""用户模块：删除用户应用服务"""

import uuid

from sqlmodel import Session

from app.modules.user.models import User
from app.modules.user.repositories.user import (
    delete_user_account,
    delete_user_record,
)


def delete_user(*, session: Session, user: User, user_id: uuid.UUID) -> None:
    """删除用户及其关联 items（仅超级管理员）"""
    delete_user_record(session=session, user=user, user_id=user_id)
    session.commit()


def delete_current_user(*, session: Session, current_user: User) -> None:
    """删除当前用户账号"""
    delete_user_account(session=session, user=current_user)
    session.commit()
