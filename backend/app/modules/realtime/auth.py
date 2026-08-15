"""Socket.IO 握手鉴权：复用现有 JWT 校验逻辑"""

import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.modules.auth.schemas import TokenPayload
from app.modules.user.models import User


def authenticate_token(token: str) -> User | None:
    """校验 access token 并返回有效用户；无效/禁用返回 None"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[security.ALGORITHM],
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        return None
    if token_data.sub is None:
        return None
    with Session(engine) as session:
        user = session.get(User, token_data.sub)
    if user is None or not user.is_active:
        return None
    return user
