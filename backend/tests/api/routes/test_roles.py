"""角色与权限接口测试"""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.modules.user.application.user_query import get_user_by_email
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


def _permission_ids_by_code(
    *, client: TestClient, headers: dict[str, str]
) -> dict[str, str]:
    """读取权限目录，返回权限码 → 权限 ID 映射"""
    response = client.get(f"{API}/permissions", headers=headers)
    assert response.status_code == 200, response.text
    return {item["code"]: item["id"] for item in response.json()["data"]}


def _create_role(
    *,
    client: TestClient,
    headers: dict[str, str],
    code: str,
    name: str,
) -> str:
    """创建角色并返回角色 ID"""
    response = client.post(
        f"{API}/roles", headers=headers, json={"code": code, "name": name}
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _user_id_by_email(*, db: Session, email: str) -> uuid.UUID:
    """按邮箱查询测试用户 ID"""
    user = get_user_by_email(session=db, email=email)
    assert user is not None
    return user.id


def test_permission_catalog_requires_login(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """权限目录必须登录后访问，且包含角色模块权限码"""
    assert client.get(f"{API}/permissions").status_code == 401

    response = client.get(f"{API}/permissions/tree", headers=superuser_token_headers)
    assert response.status_code == 200, response.text
    codes = {
        permission["code"]
        for category in response.json()["data"]
        for permission in category["permissions"]
    }
    assert {"role:view", "role:assign_permission", "role:assign_user"} <= codes

    actions = {
        permission["action"]
        for category in response.json()["data"]
        for permission in category["permissions"]
    }
    assert actions <= {"view", "create", "update", "manage"}

    categories = client.get(
        f"{API}/permission-categories", headers=superuser_token_headers
    )
    assert categories.status_code == 200, categories.text
    first_category = categories.json()["data"][0]
    assert first_category["name"] == "角色管理"
    assert "code" not in first_category

    filtered = client.get(
        f"{API}/permissions",
        headers=superuser_token_headers,
        params={"action": "manage"},
    )
    assert filtered.status_code == 200, filtered.text
    assert {item["code"] for item in filtered.json()["data"]} == {
        "role:assign_user",
        "role:assign_permission",
        "role:delete",
    }


def test_role_assignment_grants_and_revokes_permission(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """分配角色后权限立即生效，移除角色后权限立即失效"""
    permission_ids = _permission_ids_by_code(
        client=client, headers=superuser_token_headers
    )
    role_id = _create_role(
        client=client,
        headers=superuser_token_headers,
        code=f"viewer_{random_lower_string()}",
        name="只读角色",
    )
    response = client.put(
        f"{API}/roles/{role_id}/permissions",
        headers=superuser_token_headers,
        json={"permission_ids": [permission_ids["role:view"]]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["permission_codes"] == ["role:view"]

    email = random_email()
    user_headers = authentication_token_from_email(client=client, email=email, db=db)
    user_id = _user_id_by_email(db=db, email=email)

    assert client.get(f"{API}/roles", headers=user_headers).status_code == 403
    me = client.get(f"{API}/users/me/permissions", headers=user_headers)
    assert me.json() == {"is_superuser": False, "permission_codes": []}

    response = client.post(
        f"{API}/users/{user_id}/roles",
        headers=superuser_token_headers,
        json={"role_id": role_id},
    )
    assert response.status_code == 200, response.text
    assert client.get(f"{API}/roles", headers=user_headers).status_code == 200
    me = client.get(f"{API}/users/me/permissions", headers=user_headers)
    assert "role:view" in me.json()["permission_codes"]

    response = client.delete(
        f"{API}/users/{user_id}/roles/{role_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, response.text
    assert client.get(f"{API}/roles", headers=user_headers).status_code == 403


def test_non_superuser_cannot_grant_permission_beyond_own_scope(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """非超管只能授予自己已持有的权限码"""
    permission_ids = _permission_ids_by_code(
        client=client, headers=superuser_token_headers
    )
    manager_role_id = _create_role(
        client=client,
        headers=superuser_token_headers,
        code=f"manager_{random_lower_string()}",
        name="角色管理员",
    )
    response = client.put(
        f"{API}/roles/{manager_role_id}/permissions",
        headers=superuser_token_headers,
        json={
            "permission_ids": [
                permission_ids["role:view"],
                permission_ids["role:create"],
                permission_ids["role:assign_permission"],
            ]
        },
    )
    assert response.status_code == 200, response.text

    email = random_email()
    manager_headers = authentication_token_from_email(client=client, email=email, db=db)
    manager_id = _user_id_by_email(db=db, email=email)
    response = client.post(
        f"{API}/users/{manager_id}/roles",
        headers=superuser_token_headers,
        json={"role_id": manager_role_id},
    )
    assert response.status_code == 200, response.text

    target_role_id = _create_role(
        client=client,
        headers=manager_headers,
        code=f"target_{random_lower_string()}",
        name="目标角色",
    )
    response = client.put(
        f"{API}/roles/{target_role_id}/permissions",
        headers=manager_headers,
        json={"permission_ids": [permission_ids["role:view"]]},
    )
    assert response.status_code == 200, response.text

    response = client.put(
        f"{API}/roles/{target_role_id}/permissions",
        headers=manager_headers,
        json={"permission_ids": [permission_ids["role:update"]]},
    )
    assert response.status_code == 403


def test_system_role_cannot_be_deactivated(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """系统内置角色不可停用"""
    response = client.get(
        f"{API}/roles",
        headers=superuser_token_headers,
        params={"keyword": "admin"},
    )
    assert response.status_code == 200, response.text
    admin_role = next(
        item for item in response.json()["data"] if item["code"] == "admin"
    )
    assert admin_role["is_system"] is True

    response = client.patch(
        f"{API}/roles/{admin_role['id']}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    assert response.status_code == 400

    response = client.delete(
        f"{API}/roles/{admin_role['id']}", headers=superuser_token_headers
    )
    assert response.status_code == 400


def test_create_role_generates_code_when_omitted(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """创建角色不传角色码时由服务端生成"""
    response = client.post(
        f"{API}/roles",
        headers=superuser_token_headers,
        json={"name": "自动编码角色"},
    )
    assert response.status_code == 200, response.text
    created = response.json()
    assert created["code"].startswith("role_")
    assert created["is_system"] is False

    response = client.delete(
        f"{API}/roles/{created['id']}", headers=superuser_token_headers
    )
    assert response.status_code == 200, response.text


def test_delete_role_clears_permission_and_user_assignment(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """删除角色后权限与用户分配一并清理，用户权限立即失效"""
    permission_ids = _permission_ids_by_code(
        client=client, headers=superuser_token_headers
    )
    role_id = _create_role(
        client=client,
        headers=superuser_token_headers,
        code=f"removable_{random_lower_string()}",
        name="待删除角色",
    )
    response = client.put(
        f"{API}/roles/{role_id}/permissions",
        headers=superuser_token_headers,
        json={"permission_ids": [permission_ids["role:view"]]},
    )
    assert response.status_code == 200, response.text

    email = random_email()
    user_headers = authentication_token_from_email(client=client, email=email, db=db)
    user_id = _user_id_by_email(db=db, email=email)
    response = client.post(
        f"{API}/users/{user_id}/roles",
        headers=superuser_token_headers,
        json={"role_id": role_id},
    )
    assert response.status_code == 200, response.text
    assert client.get(f"{API}/roles", headers=user_headers).status_code == 200

    response = client.delete(f"{API}/roles/{role_id}", headers=superuser_token_headers)
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "角色已删除"

    # 角色与用户分配都已清理，用户权限立即失效
    assert (
        client.get(
            f"{API}/roles/{role_id}", headers=superuser_token_headers
        ).status_code
        == 404
    )
    assert client.get(f"{API}/roles", headers=user_headers).status_code == 403
    roles = client.get(f"{API}/users/{user_id}/roles", headers=superuser_token_headers)
    assert roles.status_code == 200, roles.text
    assert roles.json()["count"] == 0

    # 重复删除幂等：第二次返回 404
    assert (
        client.delete(
            f"{API}/roles/{role_id}", headers=superuser_token_headers
        ).status_code
        == 404
    )
