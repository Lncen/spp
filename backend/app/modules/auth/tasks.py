"""认证模块：定时任务"""

import logging
from datetime import UTC, datetime

from celery import shared_task  # type: ignore[import-untyped]
from sqlmodel import Session, delete

from app.core.db import engine
from app.modules.auth.models import RefreshToken

logger = logging.getLogger(__name__)


@shared_task  # type: ignore[untyped-decorator]
def cleanup_expired_refresh_tokens() -> dict[str, int]:
    """清理已过期或已撤销的刷新令牌，防止表无限增长"""
    now = datetime.now(UTC)
    with Session(engine) as session:
        expired = session.exec(
            delete(RefreshToken).where(
                RefreshToken.expires_at <= now  # type: ignore[arg-type]
            )
        )
        revoked = session.exec(
            delete(RefreshToken).where(
                RefreshToken.revoked_at.is_not(None)  # type: ignore[union-attr]
            )
        )
        session.commit()
    return {"deleted": (expired.rowcount or 0) + (revoked.rowcount or 0)}
