"""管理端组合下单链路：收藏商品 → 保存组合 → 代客组合下单"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.user.models import User
from tests.api.routes.test_products import create_category
from tests.utils.utils import random_lower_string


def _create_product_with_param_key(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    *,
    name: str,
    param_key: str,
    param_label: str,
) -> dict:
    """创建只带一个自定义下单参数的可售商品（价格固定 20）"""
    category = create_category(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": name,
            "category_id": category["id"],
            "status": 7,
            "source_type": 2,
            "pricing": {"cost_price": "10.00", "fixed_price": "20.00"},
            "inventory": {"min_quantity": 1, "max_quantity": 5, "stock": 100},
            "fulfillment": {
                "fulfillment_type": 2,
                "can_refund": True,
                "unit": "件",
            },
            "buy_params": [
                {"key": param_key, "label": param_label, "is_required": True}
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _product_stock(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    product_id: str,
) -> int:
    response = client.get(
        f"{settings.API_V1_STR}/products/{product_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    return response.json()["inventory"]["stock"]


def test_admin_combo_order_flow(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """完整链路：商品管理列表 → 收藏 → 保存组合（固定 + 随机数量）→ 代客下单"""
    superuser = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).one()
    prefix = random_lower_string()
    product_a = _create_product_with_param_key(
        client,
        superuser_token_headers,
        name=f"{prefix}-a",
        param_key="account",
        param_label="账号",
    )
    product_b = _create_product_with_param_key(
        client,
        superuser_token_headers,
        name=f"{prefix}-b",
        param_key="qq",
        param_label="QQ",
    )

    # 1. 管理端商品列表可按名称定位商品
    listing = client.get(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        params={"name": prefix},
    )
    assert listing.status_code == 200
    assert listing.json()["count"] == 2

    # 2. 在商品管理列表收藏两个商品
    for product in (product_a, product_b):
        response = client.post(
            f"{settings.API_V1_STR}/product-favorites/me",
            headers=superuser_token_headers,
            json={"product_id": product["id"]},
        )
        assert response.status_code == 200
    favorites = client.get(
        f"{settings.API_V1_STR}/product-favorites/me",
        headers=superuser_token_headers,
    )
    assert favorites.json()["count"] == 2

    # 3. 保存组合：A 固定数量、B 随机数量
    combo = client.post(
        f"{settings.API_V1_STR}/product-combos/me",
        headers=superuser_token_headers,
        json={
            "name": f"{prefix}-组合",
            "items": [
                {"product_id": product_a["id"], "mode": 1, "quantity": 2},
                {
                    "product_id": product_b["id"],
                    "mode": 2,
                    "min_quantity": 2,
                    "max_quantity": 3,
                },
            ],
        },
    )
    assert combo.status_code == 200, combo.text
    combo_items = combo.json()["items"]
    assert combo_items[0]["mode"] == 1
    assert combo_items[0]["quantity"] == 2
    assert combo_items[1]["mode"] == 2

    # 4. 组合下单：数量在随机区间内取一次值；参数统一填写一次，按各商品自己的 key 写入
    random_quantity = combo_items[1]["min_quantity"]
    unified_param_value = "unified-account-01"
    orders = [
        {
            "product_id": product_a["id"],
            "quantity": 2,
            "params": {"account": unified_param_value},
        },
        {
            "product_id": product_b["id"],
            "quantity": random_quantity,
            "params": {"qq": unified_param_value},
        },
    ]

    preview = client.post(
        f"{settings.API_V1_STR}/orders/admin/preview",
        headers=superuser_token_headers,
        json={"orders": orders},
    )
    assert preview.status_code == 200
    assert Decimal(preview.json()["total_amount"]) == Decimal("20") * (
        2 + random_quantity
    )

    created = client.post(
        f"{settings.API_V1_STR}/orders/admin",
        headers=superuser_token_headers,
        json={"orders": orders},
    )
    assert created.status_code == 200
    content = created.json()
    assert content["success_count"] == 2
    assert content["failure_count"] == 0
    assert all(
        item["order"]["user_id"] == str(superuser.id) for item in content["results"]
    )
    # 同一个参数值按各商品自己的参数 key 落库
    assert content["results"][0]["order"]["params"] == {"account": unified_param_value}
    assert content["results"][1]["order"]["params"] == {"qq": unified_param_value}

    # 5. 代客下单同样扣减库存，但不涉及钱包
    assert _product_stock(client, superuser_token_headers, product_a["id"]) == 98
    assert (
        _product_stock(client, superuser_token_headers, product_b["id"])
        == 100 - random_quantity
    )
