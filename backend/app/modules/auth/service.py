"""认证模块：业务逻辑层"""

from sqlmodel import Session, select

from app.core.security import verify_password
from app.modules.user.models import User

# 用于防时序攻击的虚拟哈希（Argon2 格式）
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, login: str, password: str) -> User | None:
    """验证用户凭据，支持用户名或邮箱登录，返回用户对象或 None"""
    statement = select(User).where(
        (User.email == login) | (User.username == login)
    )
    db_user = session.exec(statement).first()
    if not db_user:
        # 即使邮箱不存在也执行密码验证，防止时序攻击
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user
