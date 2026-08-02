"""订单模块：API 与业务测试"""

from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.level.models import UserLevel
from app.modules.user.models import User
from app.modules.wallet.models import Wallet
from tests.api.routes.test_products import (
    create_category,
    create_price_template,
    create_product,
)
from tests.utils.user import authentication_token_from_email, create_random_user
from tests.utils.utils import random_lower_string


def _create_wallet_user(
    client: TestClient, db: Session
) -> tuple[dict[str, str], User]:
    """创建随机用户并返回其认证头和用户对象"""
    user = create_random_user(db)
    headers = authentication_token_from_email(client=client, email=user.email, db=db)
    return headers, user


def _fund_wallet(
    client: TestClient,
    headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    amount: str = "100.00",
) -> None:
    response = client.get(f"{settings.API_V1_STR}/wallets/me", headers=headers)
    assert response.status_code == 200
    wallet_id = response.json()["id"]
    response = client.post(
        f"{settings.API_V1_STR}/wallets/{wallet_id}/adjust",
        headers=superuser_token_headers,
        json={"amount": amount, "remark": "测试入账"},
    )
    assert response.status_code == 200


def _create_ready_product(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    **kwargs: Any,
) -> dict:
    """创建可售商品（READY 状态）"""
    return create_product(
        client,
        superuser_token_headers,
        status=3,
        **kwargs,
    )


def _create_custom_inventory_product(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    *,
    min_quantity: int = 1,
    max_quantity: int = 5,
    is_batch: bool = True,
    purchase_step: int = 1,
) -> dict:
    category = create_category(client, superuser_token_headers)
    data = {
        "name": random_lower_string(),
        "category_id": category["id"],
        "status": 3,
        "source_type": 2,
        "pricing": {"cost_price": "10.00", "fixed_price": "20.00"},
        "inventory": {
            "min_quantity": min_quantity,
            "max_quantity": max_quantity,
            "stock": 100,
            "is_batch": is_batch,
            "purchase_step": purchase_step,
        },
        "fulfillment": {"fulfillment_type": 2, "can_refund": True, "unit": "件"},
        "buy_params": [{"key": "account", "label": "账号", "is_required": True}],
    }
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    return response.json()


def _order_payload(
    product_id: str,
    quantity: int = 1,
    params: dict[str, Any] | None = None,
) -> dict:
    return {
        "items": [
            {
                "product_id": product_id,
                "quantity": quantity,
                "params": params if params is not None else {"account": "test-account"},
            }
        ]
    }


def _wallet_balance(client: TestClient, headers: dict[str, str]) -> Decimal:
    response = client.get(f"{settings.API_V1_STR}/wallets/me", headers=headers)
    assert response.status_code == 200
    return Decimal(response.json()["balance"])


def _product_stock(
    client: TestClient,
    product_id: str,
    superuser_token_headers: dict[str, str],
) -> int:
    response = client.get(
        f"{settings.API_V1_STR}/products/{product_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    return response.json()["inventory"]["stock"]


def _order_transactions(client: TestClient, headers: dict[str, str]) -> list[dict]:
    response = client.get(
        f"{settings.API_V1_STR}/wallets/me/transactions", headers=headers
    )
    assert response.status_code == 200
    return [
        item
        for item in response.json()["data"]
        if item["tx_type"] in ("consume", "refund")
    ]


def test_create_order_fixed_price(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 200
    content = response.json()
    assert content["status"] == 1
    assert Decimal(content["total_amount"]) == Decimal("20.00")
    assert content["items"][0]["product_id"] == product["id"]
    assert Decimal(content["items"][0]["unit_price"]) == Decimal("20.00")
    assert Decimal(content["items"][0]["subtotal"]) == Decimal("20.00")

    assert _wallet_balance(client, headers) == Decimal("80.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 99

    transactions = _order_transactions(client, headers)
    consume = next(item for item in transactions if item["tx_type"] == "consume")
    assert Decimal(consume["amount"]) == Decimal("-20.00")
    assert consume["ref_type"] == "order"
    assert consume["ref_id"] == content["id"]


def test_create_order_coefficient_price_includes_loss(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(
        client,
        superuser_token_headers,
        price_mode="coefficient",
        loss_price="2.00",
    )

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert Decimal(item["unit_price"]) == Decimal("18.00")
    assert Decimal(item["subtotal"]) == Decimal("18.00")
    assert Decimal(item["base_price"]) == Decimal("12.00")
    assert Decimal(item["cost_price"]) == Decimal("10.00")
    assert Decimal(item["loss_price"]) == Decimal("2.00")
    assert Decimal(response.json()["total_amount"]) == Decimal("18.00")


def test_create_order_template_price_with_user_level(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, user = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    level = db.exec(select(UserLevel).where(UserLevel.level == 1)).one()
    user.level_id = level.id
    db.add(user)
    db.commit()

    template = create_price_template(client, superuser_token_headers)
    product = _create_ready_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
    )

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 200
    assert Decimal(response.json()["total_amount"]) == Decimal("9.00")
    assert Decimal(response.json()["items"][0]["unit_price"]) == Decimal("9.00")


def test_create_order_rejects_disabled_can_order(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, user = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")

    response = client.patch(
        f"{settings.API_V1_STR}/users/{user.id}",
        headers=superuser_token_headers,
        json={"can_order": False},
    )
    assert response.status_code == 200
    assert response.json()["can_order"] is False

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "暂无下单权限"


def test_create_order_requires_wallet(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "钱包不存在"


def test_create_order_rejects_disabled_wallet(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, user = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    wallet = db.exec(select(Wallet).where(Wallet.user_id == user.id)).one()
    wallet.is_active = False
    db.add(wallet)
    db.commit()

    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")
    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "钱包已禁用"


def test_create_order_rejects_insufficient_balance(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers, "5.00")
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "余额不足"
    assert _wallet_balance(client, headers) == Decimal("5.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 100
    assert _order_transactions(client, headers) == []


def test_create_order_rejects_closed_product(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(
        client,
        superuser_token_headers,
        price_mode="fixed",
        is_closed=True,
    )

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "商品已关闭下单"


def test_create_order_rejects_unsellable_status(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = create_product(
        client,
        superuser_token_headers,
        status=1,
        price_mode="fixed",
    )

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "商品当前不可购买"


def test_create_order_rejects_quantity_rule_violations(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_custom_inventory_product(
        client,
        superuser_token_headers,
        min_quantity=2,
        max_quantity=5,
        purchase_step=2,
    )
    cases = [
        (1, "购买数量不能小于最小购买数量 2"),
        (3, "购买数量必须是 2 的整数倍"),
        (6, "购买数量不能大于最大购买数量 5"),
    ]
    for quantity, detail in cases:
        response = client.post(
            f"{settings.API_V1_STR}/orders/",
            headers=headers,
            json=_order_payload(product["id"], quantity=quantity),
        )
        assert response.status_code == 400
        assert response.json()["detail"] == detail

    batch_product = _create_custom_inventory_product(
        client,
        superuser_token_headers,
        is_batch=False,
    )
    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(batch_product["id"], quantity=2),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "该商品不支持批量购买"


def test_create_order_requires_buy_param(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json={"items": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "缺少必填下单参数: 账号"


def test_create_order_rejects_repeat_purchase(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")

    first = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert first.status_code == 200

    second = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "该商品每人限购一次"


def test_cancel_order_refunds_and_restores_stock(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order_id = order_response.json()["id"]
    assert _wallet_balance(client, headers) == Decimal("80.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 99

    response = client.post(
        f"{settings.API_V1_STR}/orders/me/{order_id}/cancel",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["status"] == 4
    assert content["canceled_at"] is not None
    assert _wallet_balance(client, headers) == Decimal("100.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 100

    transactions = _order_transactions(client, headers)
    assert {item["tx_type"] for item in transactions} == {"consume", "refund"}
    refund = next(item for item in transactions if item["tx_type"] == "refund")
    assert Decimal(refund["amount"]) == Decimal("20.00")
    assert refund["ref_type"] == "order"
    assert refund["ref_id"] == order_id


def test_fulfill_manual_order_and_refund(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(
        client,
        superuser_token_headers,
        price_mode="fixed",
        fulfillment_type=2,
    )
    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    ).json()

    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 200
    content = fulfill.json()
    assert content["status"] == 2
    assert content["processing_at"] is not None

    refund = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/refund",
        headers=superuser_token_headers,
    )
    assert refund.status_code == 200
    content = refund.json()
    assert content["status"] == 5
    assert content["refunded_at"] is not None
    assert _wallet_balance(client, headers) == Decimal("100.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 100


def test_refund_completed_order_keeps_stock_deducted(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(
        client,
        superuser_token_headers,
        price_mode="fixed",
        fulfillment_type=1,
    )
    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    ).json()

    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 200
    assert fulfill.json()["status"] == 3

    refund = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/refund",
        headers=superuser_token_headers,
    )
    assert refund.status_code == 200
    assert refund.json()["status"] == 5
    assert _wallet_balance(client, headers) == Decimal("100.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 99


def test_refund_rejects_non_refundable_product(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(
        client,
        superuser_token_headers,
        price_mode="fixed",
        can_refund=False,
    )
    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    ).json()
    client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/fulfill",
        headers=superuser_token_headers,
    )

    response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/refund",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "订单包含不支持退款的商品"


def test_cancel_order_after_fulfill_rejected(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(
        client,
        superuser_token_headers,
        price_mode="fixed",
        fulfillment_type=2,
    )
    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    ).json()
    client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/fulfill",
        headers=superuser_token_headers,
    )

    response = client.post(
        f"{settings.API_V1_STR}/orders/me/{order['id']}/cancel",
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "当前状态不可取消"


def test_order_list_routes_permissions(
    client: TestClient,
    db: Session,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/orders/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403

    headers, _ = _create_wallet_user(client, db)
    response = client.get(f"{settings.API_V1_STR}/orders/me", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"data": [], "count": 0}

    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")
    client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )

    response = client.get(
        f"{settings.API_V1_STR}/orders/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["count"] >= 1


def test_user_cannot_read_others_order(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers_a, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers_a, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")
    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers_a,
        json=_order_payload(product["id"]),
    ).json()

    headers_b, _ = _create_wallet_user(client, db)
    response = client.get(
        f"{settings.API_V1_STR}/orders/me/{order['id']}",
        headers=headers_b,
    )
    assert response.status_code == 404
