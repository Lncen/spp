"""认证模块：业务逻辑层"""

import hashlib
import logging
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis as AsyncRedis
from sqlmodel import Session, select

from app.core.config import settings
from app.core.redis import get_redis, run_redis_sync
from app.core.security import verify_password
from app.modules.auth.models import RefreshToken
from app.modules.setting.application.setting_query import get_setting
from app.modules.user.models import User

logger = logging.getLogger(__name__)

# 用于防时序攻击的虚拟哈希（Argon2 格式）
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"

LOGIN_FAIL_KEY_PREFIX = "login:fail:"
DEFAULT_LOGIN_FAIL_LIMIT = 5
DEFAULT_LOGIN_LOCKOUT_MINUTES = 15


def _login_fail_key(login: str) -> str:
    """登录失败计数键：按登录名统一小写，避免大小写变体绕过限制"""
    return f"{LOGIN_FAIL_KEY_PREFIX}{login.strip().lower()}"


def _login_policy(*, session: Session) -> tuple[int, int]:
    """读取动态登录限流配置，配置非法时回落默认值"""
    fail_limit = get_setting(session=session, key="login_fail_limit")
    lockout_minutes = get_setting(session=session, key="login_lockout_minutes")
    try:
        return int(fail_limit), int(lockout_minutes)
    except (TypeError, ValueError):
        return DEFAULT_LOGIN_FAIL_LIMIT, DEFAULT_LOGIN_LOCKOUT_MINUTES


def _run_login_redis(command: Callable[[AsyncRedis], Any]) -> Any | None:
    """执行 Redis 命令；Redis 不可用时降级返回 None，不阻断登录"""
    try:
        return run_redis_sync(command(get_redis()))
    except Exception:
        logger.warning("登录限流 Redis 操作失败，本次降级放行", exc_info=True)
        return None


def is_login_locked(*, session: Session, login: str) -> bool:
    """检查账号是否因登录失败次数达到上限而被锁定"""
    fail_limit, _ = _login_policy(session=session)
    count = _run_login_redis(lambda r: r.get(_login_fail_key(login)))
    return count is not None and int(count) >= fail_limit


def record_login_failure(*, session: Session, login: str) -> None:
    """记录一次登录失败；首次失败或达到上限时重置锁定计时"""
    fail_limit, lockout_minutes = _login_policy(session=session)
    key = _login_fail_key(login)
    count = _run_login_redis(lambda r: r.incr(key))
    if count is None:
        return
    if count == 1 or count >= fail_limit:
        _run_login_redis(lambda r: r.expire(key, lockout_minutes * 60))


def clear_login_failures(login: str) -> None:
    """登录成功后清除该账号的失败计数"""
    _run_login_redis(lambda r: r.delete(_login_fail_key(login)))


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


def _hash_refresh_token(token: str) -> str:
    """刷新令牌哈希：仅存 SHA-256 摘要，防止存储泄露后被直接冒用"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_refresh_token(*, session: Session, user: User) -> str:
    """为用户签发刷新令牌，返回明文"""
    token = secrets.token_urlsafe(48)
    session.add(
        RefreshToken(
            token_hash=_hash_refresh_token(token),
            user_id=user.id,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    session.commit()
    return token


def rotate_refresh_token(*, session: Session, token: str) -> tuple[str, User] | None:
    """校验刷新令牌并旋转：旧令牌立即作废，返回新令牌与用户"""
    now = datetime.now(UTC)
    row = session.exec(
        select(RefreshToken).where(
            RefreshToken.token_hash == _hash_refresh_token(token),
            RefreshToken.revoked_at.is_(None),  # type: ignore[union-attr]
            RefreshToken.expires_at > now,
        )
    ).first()
    if row is None:
        return None
    user = session.get(User, row.user_id)
    if user is None or not user.is_active:
        return None
    new_token = secrets.token_urlsafe(48)
    session.add(
        RefreshToken(
            token_hash=_hash_refresh_token(new_token),
            user_id=user.id,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    row.revoked_at = now
    session.commit()
    return new_token, user


def revoke_refresh_token(*, session: Session, token: str) -> None:
    """撤销刷新令牌（登出），幂等"""
    row = session.exec(
        select(RefreshToken).where(
            RefreshToken.token_hash == _hash_refresh_token(token)
        )
    ).first()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        session.add(row)
        session.commit()
