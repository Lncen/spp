"""用户等级权限测试：普通用户只能查看自己的等级"""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.level.models import UserLevel


def test_normal_user_cannot_read_levels(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    """普通用户禁止获取全部等级列表"""
    response = client.get(
        f"{settings.API_V1_STR}/levels/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_normal_user_cannot_read_level_detail(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    """普通用户禁止获取等级详情"""
    response = client.get(
        f"{settings.API_V1_STR}/levels/1",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_superuser_reads_levels(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """超管可获取全部等级列表"""
    response = client.get(
        f"{settings.API_V1_STR}/levels/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["count"] >= 1


def test_user_me_includes_own_level_name(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict[str, str],
) -> None:
    """当前用户接口返回自己的等级名称（创建时已分配默认等级）"""
    default_level = db.exec(
        select(UserLevel).where(UserLevel.is_default == True)  # noqa: E712
    ).first()

    response = client.get(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "level_name" in data
    assert data["level_name"] == (default_level.name if default_level else None)


def test_created_user_gets_default_level(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """管理端创建用户时自动分配默认等级"""
    default_level = db.exec(
        select(UserLevel).where(UserLevel.is_default == True)  # noqa: E712
    ).first()
    assert default_level is not None

    email = f"default_level_{uuid.uuid4()}@example.com"
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        headers=superuser_token_headers,
        json={
            "email": email,
            "password": "testpass1234",
        },
    )
    assert response.status_code == 200
    assert response.json()["level_id"] == str(default_level.id)
