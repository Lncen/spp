"""商品组合模块：API 与业务测试"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.product.combo.models import ProductCombo, ProductComboItem
from app.modules.user.models import User
from tests.api.routes.test_products import create_product
from tests.utils.user import authentication_token_from_email, create_random_user


def _create_user(client: TestClient, db: Session) -> tuple[dict[str, str], User]:
    """创建随机用户并返回其认证头与用户对象"""
    user = create_random_user(db)
    headers = authentication_token_from_email(client=client, email=user.email, db=db)
    return headers, user


def _create_combo_product(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> dict:
    """创建可售商品（APPROVED 状态）"""
    return create_product(
        client,
        superuser_token_headers,
        status=7,
        price_mode="fixed",
    )


def _combo_payload(products: list[dict], quantities: list[int], name: str) -> dict:
    return {
        "name": name,
        "items": [
            {"product_id": product["id"], "quantity": quantity}
            for product, quantity in zip(products, quantities, strict=False)
        ],
    }


def _create_combo(client: TestClient, headers: dict[str, str], payload: dict) -> dict:
    response = client.post(
        f"{settings.API_V1_STR}/product-combos/me",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_and_read_combo(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """保存组合后可查看详情与列表，明细按提交顺序返回"""
    headers, user = _create_user(client, db)
    product_a = _create_combo_product(client, superuser_token_headers)
    product_b = _create_combo_product(client, superuser_token_headers)

    combo = _create_combo(
        client,
        headers,
        _combo_payload([product_a, product_b], [2, 1], "日常组合"),
    )
    assert combo["name"] == "日常组合"
    assert combo["item_count"] == 2
    assert combo["remark"] is None
    items = combo["items"]
    assert [item["sort"] for item in items] == [0, 1]
    assert items[0]["product_id"] == product_a["id"]
    assert items[0]["product_name"] == product_a["name"]
    # 默认固定数量模式
    assert items[0]["mode"] == 1
    assert items[0]["quantity"] == 2
    assert items[0]["min_quantity"] is None
    assert items[0]["max_quantity"] is None
    assert items[1]["quantity"] == 1
    # 只下发用户可见的商品展示字段
    assert "cost_price" not in items[0]
    assert "supplier_id" not in items[0]

    detail = client.get(
        f"{settings.API_V1_STR}/product-combos/me/{combo['id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json() == combo

    listing = client.get(f"{settings.API_V1_STR}/product-combos/me", headers=headers)
    assert listing.status_code == 200
    content = listing.json()
    assert content["count"] == 1
    assert content["data"][0]["id"] == combo["id"]
    assert content["data"][0]["item_count"] == 2
    assert content["data"][0]["name"] == "日常组合"
    assert "items" not in content["data"][0]

    db_combo = db.exec(
        select(ProductCombo).where(ProductCombo.user_id == user.id)
    ).one()
    assert db_combo.name == "日常组合"
    assert (
        len(
            db.exec(
                select(ProductComboItem).where(ProductComboItem.combo_id == db_combo.id)
            ).all()
        )
        == 2
    )


def test_update_combo_partial_and_replace_items(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """更新组合：名称/备注部分更新，明细传入时整体替换"""
    headers, _ = _create_user(client, db)
    product_a = _create_combo_product(client, superuser_token_headers)
    product_b = _create_combo_product(client, superuser_token_headers)
    combo = _create_combo(
        client,
        headers,
        _combo_payload([product_a, product_b], [1, 1], "待修改组合"),
    )
    url = f"{settings.API_V1_STR}/product-combos/me/{combo['id']}"

    # 只改备注：明细保持不变
    response = client.put(url, headers=headers, json={"remark": "给我的账号用"})
    assert response.status_code == 200
    content = response.json()
    assert content["remark"] == "给我的账号用"
    assert content["name"] == "待修改组合"
    assert content["item_count"] == 2

    # 传明细：整体替换并重排 sort
    response = client.put(
        url,
        headers=headers,
        json={
            "name": "改名后的组合",
            "items": [{"product_id": product_b["id"], "quantity": 3}],
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "改名后的组合"
    assert content["remark"] == "给我的账号用"
    assert content["item_count"] == 1
    assert content["items"][0]["product_id"] == product_b["id"]
    assert content["items"][0]["quantity"] == 3
    assert content["items"][0]["sort"] == 0


def test_delete_combo(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """删除组合同时删除明细"""
    headers, _ = _create_user(client, db)
    product = _create_combo_product(client, superuser_token_headers)
    combo = _create_combo(
        client,
        headers,
        _combo_payload([product], [1], "待删除组合"),
    )
    url = f"{settings.API_V1_STR}/product-combos/me/{combo['id']}"

    response = client.delete(url, headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "组合已删除"

    assert client.get(url, headers=headers).status_code == 404
    listing = client.get(f"{settings.API_V1_STR}/product-combos/me", headers=headers)
    assert listing.json() == {"data": [], "count": 0}
    db.expire_all()
    assert (
        db.exec(
            select(ProductComboItem).where(
                ProductComboItem.combo_id == uuid.UUID(combo["id"])
            )
        ).all()
        == []
    )


def test_combo_name_unique_per_user(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """同一用户组合名称唯一，不同用户可重名"""
    headers_a, _ = _create_user(client, db)
    headers_b, _ = _create_user(client, db)
    product = _create_combo_product(client, superuser_token_headers)
    payload = _combo_payload([product], [1], "重名组合")

    _create_combo(client, headers_a, payload)

    response = client.post(
        f"{settings.API_V1_STR}/product-combos/me",
        headers=headers_a,
        json=payload,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "组合名称已存在"

    # 另一个用户使用相同名称不受影响
    other = _create_combo(client, headers_b, payload)
    assert other["name"] == "重名组合"


def test_combo_rejects_duplicate_product(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """同一组合内不允许重复商品"""
    headers, _ = _create_user(client, db)
    product = _create_combo_product(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/product-combos/me",
        headers=headers,
        json=_combo_payload([product, product], [1, 2], "重复商品组合"),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "组合内商品不能重复"


def test_combo_rejects_missing_product(
    client: TestClient,
    db: Session,
) -> None:
    """组合包含不存在的商品时拒绝保存"""
    headers, _ = _create_user(client, db)
    response = client.post(
        f"{settings.API_V1_STR}/product-combos/me",
        headers=headers,
        json={
            "name": "无效组合",
            "items": [{"product_id": str(uuid.uuid4()), "quantity": 1}],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "组合包含不存在的商品"


def test_combo_rejects_empty_or_invalid_items(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """组合明细不能为空，数量必须大于 0"""
    headers, _ = _create_user(client, db)
    product = _create_combo_product(client, superuser_token_headers)

    response = client.post(
        f"{settings.API_V1_STR}/product-combos/me",
        headers=headers,
        json={"name": "空组合", "items": []},
    )
    assert response.status_code == 422

    response = client.post(
        f"{settings.API_V1_STR}/product-combos/me",
        headers=headers,
        json={
            "name": "数量非法组合",
            "items": [{"product_id": product["id"], "quantity": 0}],
        },
    )
    assert response.status_code == 422


def test_combo_random_quantity_mode(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """随机数量模式保存最小/最大数量，固定数量留空"""
    headers, _ = _create_user(client, db)
    product = _create_combo_product(client, superuser_token_headers)
    combo = _create_combo(
        client,
        headers,
        {
            "name": "随机数量组合",
            "items": [
                {
                    "product_id": product["id"],
                    "mode": 2,
                    "min_quantity": 2,
                    "max_quantity": 5,
                }
            ],
        },
    )
    item = combo["items"][0]
    assert item["mode"] == 2
    assert item["quantity"] is None
    assert item["min_quantity"] == 2
    assert item["max_quantity"] == 5

    # 明细替换后仍保留随机数量模式
    response = client.put(
        f"{settings.API_V1_STR}/product-combos/me/{combo['id']}",
        headers=headers,
        json={
            "items": [
                {
                    "product_id": product["id"],
                    "mode": 2,
                    "min_quantity": 3,
                    "max_quantity": 3,
                }
            ]
        },
    )
    assert response.status_code == 200
    updated = response.json()["items"][0]
    assert updated["mode"] == 2
    assert updated["min_quantity"] == 3
    assert updated["max_quantity"] == 3


@pytest.mark.parametrize(
    "item",
    [
        {"mode": 2, "min_quantity": 2},  # 随机数量缺少最大数量
        {"mode": 2, "max_quantity": 5},  # 随机数量缺少最小数量
        {"mode": 2, "min_quantity": 5, "max_quantity": 2},  # 最小大于最大
        {"mode": 2, "quantity": 3, "min_quantity": 1, "max_quantity": 5},
        {"mode": 1},  # 固定数量缺少 quantity
        {"mode": 1, "quantity": 1, "min_quantity": 1, "max_quantity": 2},
    ],
)
def test_combo_item_quantity_mode_validation(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    item: dict,
) -> None:
    """数量模式与数量字段不匹配时拒绝保存"""
    headers, _ = _create_user(client, db)
    product = _create_combo_product(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/product-combos/me",
        headers=headers,
        json={
            "name": f"非法组合-{uuid.uuid4().hex[:8]}",
            "items": [{"product_id": product["id"], **item}],
        },
    )
    assert response.status_code == 422, response.text


def test_combos_are_isolated_between_users(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """组合按用户隔离，不能查看或修改他人组合"""
    headers_a, _ = _create_user(client, db)
    headers_b, _ = _create_user(client, db)
    product = _create_combo_product(client, superuser_token_headers)
    combo = _create_combo(
        client,
        headers_a,
        _combo_payload([product], [1], "私有组合"),
    )
    url = f"{settings.API_V1_STR}/product-combos/me/{combo['id']}"

    listing = client.get(f"{settings.API_V1_STR}/product-combos/me", headers=headers_b)
    assert listing.json() == {"data": [], "count": 0}

    assert client.get(url, headers=headers_b).status_code == 404
    assert (
        client.put(url, headers=headers_b, json={"name": "越权改名"}).status_code == 404
    )
    assert client.delete(url, headers=headers_b).status_code == 404

    # 用户 A 的组合未被影响
    assert client.get(url, headers=headers_a).json()["name"] == "私有组合"


def test_combo_requires_authentication(client: TestClient) -> None:
    """未登录不能访问组合接口"""
    assert client.get(f"{settings.API_V1_STR}/product-combos/me").status_code == 401
    assert (
        client.post(
            f"{settings.API_V1_STR}/product-combos/me",
            json={"name": "x", "items": [{"product_id": str(uuid.uuid4())}]},
        ).status_code
        == 401
    )


def test_combo_item_removed_when_product_deleted(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """商品删除后组合明细级联删除，组合本身保留"""
    headers, _ = _create_user(client, db)
    product = _create_combo_product(client, superuser_token_headers)
    combo = _create_combo(
        client,
        headers,
        _combo_payload([product], [1], "含已删除商品的组合"),
    )

    response = client.delete(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    detail = client.get(
        f"{settings.API_V1_STR}/product-combos/me/{combo['id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["item_count"] == 0
    assert detail.json()["items"] == []
