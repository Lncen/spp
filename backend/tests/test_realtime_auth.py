"""实时通道握手鉴权测试"""

from datetime import timedelta

from app.core import security
from app.modules.realtime.auth import authenticate_token
from tests.utils.user import create_random_user


def test_authenticate_token_returns_active_user(db):
    user = create_random_user(db)
    assert user.id is not None
    token = security.create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=5),
    )

    result = authenticate_token(token)

    assert result is not None
    assert result.id == user.id


def test_authenticate_token_rejects_invalid_token():
    assert authenticate_token("invalid-token") is None
