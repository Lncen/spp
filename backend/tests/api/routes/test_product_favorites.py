"""商品收藏模块：API 与业务测试"""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.product.favorite.models import ProductFavorite
from app.modules.user.models import User
from tests.api.routes.test_products import create_product
from tests.utils.user import authentication_token_from_email, create_random_user


def _create_user(client: TestClient, db: Session) -> tuple[dict[str, str], User]:
    """创建随机用户并返回其认证头与用户对象"""
    user = create_random_user(db)
    headers = authentication_token_from_email(client=client, email=user.email, db=db)
    return headers, user


def _create_favorite_product(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> dict:
    """创建可售商品（APPROVED 状态）"""
    return create_product(
        client,
        superuser_token_headers,
        status=7,
        price_mode="fixed",
    )


def _add_favorite(
    client: TestClient,
    headers: dict[str, str],
    product_id: str,
) -> dict:
    response = client.post(
        f"{settings.API_V1_STR}/product-favorites/me",
        headers=headers,
        json={"product_id": product_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _list_favorites(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.get(
        f"{settings.API_V1_STR}/product-favorites/me",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_favorite_add_list_and_idempotent(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """收藏商品后可查看，重复收藏保持幂等且只保留一条记录"""
    headers, user = _create_user(client, db)
    product = _create_favorite_product(client, superuser_token_headers)

    first = _add_favorite(client, headers, product["id"])
    assert first["product_id"] == product["id"]
    assert first["product_name"] == product["name"]
    assert first["is_closed"] is False

    second = _add_favorite(client, headers, product["id"])
    assert second["id"] == first["id"]

    content = _list_favorites(client, headers)
    assert content["count"] == 1
    assert len(content["data"]) == 1
    assert content["data"][0]["product_id"] == product["id"]

    favorites = db.exec(
        select(ProductFavorite).where(ProductFavorite.user_id == user.id)
    ).all()
    assert len(favorites) == 1


def test_favorite_status_and_remove(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """收藏状态可查询，取消收藏幂等"""
    headers, _ = _create_user(client, db)
    product = _create_favorite_product(client, superuser_token_headers)
    status_url = f"{settings.API_V1_STR}/product-favorites/me/{product['id']}"

    response = client.get(status_url, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"product_id": product["id"], "favorited": False}

    _add_favorite(client, headers, product["id"])
    response = client.get(status_url, headers=headers)
    assert response.json()["favorited"] is True

    response = client.delete(status_url, headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "已取消收藏"

    response = client.get(status_url, headers=headers)
    assert response.json()["favorited"] is False

    # 未收藏时再次取消仍为幂等成功
    response = client.delete(status_url, headers=headers)
    assert response.status_code == 200


def test_favorites_are_isolated_between_users(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """收藏按用户隔离，不能看到或影响他人收藏"""
    headers_a, _ = _create_user(client, db)
    headers_b, _ = _create_user(client, db)
    product = _create_favorite_product(client, superuser_token_headers)

    _add_favorite(client, headers_a, product["id"])

    assert _list_favorites(client, headers_b) == {"data": [], "count": 0}
    status_url = f"{settings.API_V1_STR}/product-favorites/me/{product['id']}"
    response = client.get(status_url, headers=headers_b)
    assert response.json()["favorited"] is False

    # 用户 B 取消收藏不影响用户 A
    response = client.delete(status_url, headers=headers_b)
    assert response.status_code == 200
    assert _list_favorites(client, headers_a)["count"] == 1


def test_favorite_rejects_missing_product(
    client: TestClient,
    db: Session,
) -> None:
    """收藏不存在的商品返回 404"""
    headers, _ = _create_user(client, db)
    response = client.post(
        f"{settings.API_V1_STR}/product-favorites/me",
        headers=headers,
        json={"product_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "商品不存在"


def test_favorite_requires_authentication(client: TestClient) -> None:
    """未登录不能访问收藏接口"""
    response = client.get(f"{settings.API_V1_STR}/product-favorites/me")
    assert response.status_code == 401

    response = client.post(
        f"{settings.API_V1_STR}/product-favorites/me",
        json={"product_id": str(uuid.uuid4())},
    )
    assert response.status_code == 401


def test_favorite_removed_when_product_deleted(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """商品删除后其收藏记录级联删除"""
    headers, user = _create_user(client, db)
    product = _create_favorite_product(client, superuser_token_headers)
    _add_favorite(client, headers, product["id"])

    response = client.delete(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    db.expire_all()
    remaining = db.exec(
        select(ProductFavorite).where(ProductFavorite.user_id == user.id)
    ).all()
    assert remaining == []
    assert _list_favorites(client, headers) == {"data": [], "count": 0}
