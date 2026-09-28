"""订单模块：API 与业务测试"""

import uuid
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.automation.infrastructure.tasks import (
    automation_task_scan,
    cleanup_completed_orders,
)
from app.modules.level.models import UserLevel
from app.modules.order.application.sync import sync_orders_status
from app.modules.order.domain.constants import OrderStatus
from app.modules.order.models import Order, OrderParam
from app.modules.product.constants import SyncStatus
from app.modules.product.product.models import Product, ProductSupplier
from app.modules.supplier.infrastructure.clients.base import (
    SupplierClientError,
    SupplierClientRejectedError,
    SupplierClientUnknownError,
)
from app.modules.supplier.infrastructure.clients.ylsup import YlsupClient
from app.modules.supplier.schemas.upstream import UpstreamOrder
from app.modules.user.models import User
from app.modules.wallet.models import Wallet
from tests.api.routes.test_products import (
    create_category,
    create_price_template,
    create_product,
)
from tests.api.routes.test_suppliers import create_random_supplier
from tests.utils.user import authentication_token_from_email, create_random_user
from tests.utils.utils import random_lower_string


def _create_wallet_user(client: TestClient, db: Session) -> tuple[dict[str, str], User]:
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


def _permission_ids_by_code(
    *, client: TestClient, headers: dict[str, str]
) -> dict[str, str]:
    """读取权限目录，返回权限码 → 权限 ID 映射"""
    response = client.get(f"{settings.API_V1_STR}/permissions", headers=headers)
    assert response.status_code == 200, response.text
    return {item["code"]: item["id"] for item in response.json()["data"]}


def _create_ready_product(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    **kwargs: Any,
) -> dict:
    """创建可售商品（APPROVED 状态）"""
    return create_product(
        client,
        superuser_token_headers,
        status=7,
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
    fulfillment_type: int = 2,
    can_refund: bool = True,
) -> dict:
    category = create_category(client, superuser_token_headers)
    data = {
        "name": random_lower_string(),
        "category_id": category["id"],
        "status": 7,
        "source_type": 2,
        "pricing": {"cost_price": "10.00", "fixed_price": "20.00"},
        "inventory": {
            "min_quantity": min_quantity,
            "max_quantity": max_quantity,
            "stock": 100,
            "is_batch": is_batch,
            "purchase_step": purchase_step,
        },
        "fulfillment": {
            "fulfillment_type": fulfillment_type,
            "can_refund": can_refund,
            "unit": "件",
        },
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
        "orders": [
            {
                "product_id": product_id,
                "quantity": quantity,
                "params": params if params is not None else {"account": "test-account"},
            }
        ]
    }


def _first_order_result(response: Any) -> dict:
    """从批量下单响应中提取第一张成功订单"""
    result = response.json()["results"][0]
    assert result["success"] is True
    return result["order"]


def _first_order_failure(response: Any) -> dict:
    """从批量下单响应中提取第一张失败订单结果"""
    result = response.json()["results"][0]
    assert result["success"] is False
    return result


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
    order = _first_order_result(response)
    assert order["status"] == 1
    assert Decimal(order["total_amount"]) == Decimal("20.00")
    assert order["product_id"] == product["id"]
    assert Decimal(order["unit_price"]) == Decimal("20.00")
    assert Decimal(order["subtotal"]) == Decimal("20.00")
    # 创建订单时开始数量与当前数量等于订单数量
    assert order["start_quantity"] == order["quantity"] == 1
    assert order["current_quantity"] == order["quantity"] == 1

    assert _wallet_balance(client, headers) == Decimal("80.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 99

    transactions = _order_transactions(client, headers)
    consume = next(item for item in transactions if item["tx_type"] == "consume")
    assert Decimal(consume["amount"]) == Decimal("-20.00")
    assert consume["ref_type"] == "order"
    assert consume["ref_id"] == order["id"]


def test_create_order_records_supplier_name(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """创建订单时在订单表记录供应商名称快照"""
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    supplier = create_random_supplier(db)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")
    response = client.put(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
        json={"supplier": {"supplier_id": str(supplier.id), "sku_id": "SKU-001"}},
    )
    assert response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 200
    order = _first_order_result(response)
    assert order["supplier_name"] == supplier.name

    db_order = db.exec(select(Order).where(Order.id == order["id"])).one()
    assert db_order.supplier_name == supplier.name


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
    order = _first_order_result(response)
    assert Decimal(order["unit_price"]) == Decimal("18.00")
    assert Decimal(order["subtotal"]) == Decimal("18.00")
    assert Decimal(order["base_price"]) == Decimal("12.00")
    assert Decimal(order["cost_price"]) == Decimal("10.00")
    assert Decimal(order["loss_price"]) == Decimal("2.00")
    assert Decimal(order["total_amount"]) == Decimal("18.00")


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
    order = _first_order_result(response)
    assert Decimal(order["total_amount"]) == Decimal("9.00")
    assert Decimal(order["unit_price"]) == Decimal("9.00")


def test_create_order_rejects_user_without_order_permission(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """直授拒绝 order:create 后，用户无法创建订单"""
    headers, user = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")

    permission_ids = _permission_ids_by_code(
        client=client, headers=superuser_token_headers
    )
    response = client.put(
        f"{settings.API_V1_STR}/users/{user.id}/permissions/deny",
        headers=superuser_token_headers,
        json={"permission_ids": [permission_ids["order:create"]]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["deny_codes"] == ["order:create"]

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
    assert response.status_code == 200
    assert _first_order_failure(response)["detail"] == "钱包不存在"


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
    assert response.status_code == 200
    assert _first_order_failure(response)["detail"] == "钱包已禁用"


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
    assert response.status_code == 200
    assert _first_order_failure(response)["detail"] == "余额不足"
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
    assert response.status_code == 200
    assert _first_order_failure(response)["detail"] == "商品已关闭下单"


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
    assert response.status_code == 200
    assert _first_order_failure(response)["detail"] == "商品当前不可购买"


def test_create_order_rejects_sync_failed_product(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """商品上游同步异常时拒绝下单，即使商品仍处于可售状态"""
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(
        client,
        superuser_token_headers,
        price_mode="fixed",
    )
    db_product = db.get(Product, uuid.UUID(product["id"]))
    assert db_product is not None
    db_product.sync_status = SyncStatus.FAILED
    db.add(db_product)
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert response.status_code == 200
    assert _first_order_failure(response)["detail"] == "商品同步异常，暂不可下单"


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
        assert response.status_code == 200
        assert _first_order_failure(response)["detail"] == detail

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
    assert response.status_code == 200
    assert _first_order_failure(response)["detail"] == "该商品不支持批量购买"


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
        json={"orders": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert response.status_code == 200
    assert _first_order_failure(response)["detail"] == "缺少必填下单参数: 账号"


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
    assert second.status_code == 200
    assert _first_order_failure(second)["detail"] == "该商品相同参数订单未完成，禁止重复下单"


def test_create_order_allows_same_product_different_params(
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
        json=_order_payload(product["id"], params={"account": "account-a"}),
    )
    assert first.status_code == 200
    second = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"], params={"account": "account-b"}),
    )
    assert second.status_code == 200
    assert _first_order_result(second)["status"] == 1


def test_create_order_rejects_repeat_same_params_different_quantity(
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
        json=_order_payload(product["id"], quantity=1),
    )
    assert first.status_code == 200
    second = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"], quantity=2),
    )
    assert second.status_code == 200
    assert _first_order_failure(second)["detail"] == "该商品相同参数订单未完成，禁止重复下单"


def test_create_order_rejects_reorder_while_after_sale_pending(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )
    monkeypatch.setattr(
        YlsupClient,
        "create_order",
        lambda self, **kwargs: "10086",
    )
    monkeypatch.setattr(
        YlsupClient,
        "query_order",
        lambda self, order_ids: [
            UpstreamOrder(upstream_id="10086", status=3)
        ],
    )

    first = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert first.status_code == 200
    order_id = _first_order_result(first)["id"]
    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{order_id}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 200
    cancel = client.post(
        f"{settings.API_V1_STR}/orders/me/{order_id}/cancel",
        headers=headers,
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == 10

    second = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert second.status_code == 200
    content = second.json()
    assert content["success_count"] == 0
    assert content["failure_count"] == 1
    result = content["results"][0]
    assert result["success"] is False
    assert result["detail"] == "该商品相同参数订单未完成，禁止重复下单"


def test_cancel_order_locally_refunds_unfulfilled_order(
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
    order_id = _first_order_result(order_response)["id"]
    assert _wallet_balance(client, headers) == Decimal("80.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 99

    response = client.post(
        f"{settings.API_V1_STR}/orders/me/{order_id}/cancel",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["status"] == 8
    assert content["canceled_at"] is not None
    assert content["refunded_at"] is not None
    assert Decimal(content["refunded_amount"]) == Decimal("20.00")
    assert _wallet_balance(client, headers) == Decimal("100.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 100

    transactions = _order_transactions(client, headers)
    assert {item["tx_type"] for item in transactions} == {"consume", "refund"}


def test_cancel_unfulfilled_api_order_locally_refunds(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )
    monkeypatch.setattr(
        YlsupClient,
        "create_order",
        lambda self, **kwargs: "10086",
    )

    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order_id = _first_order_result(order_response)["id"]
    assert _wallet_balance(client, headers) == Decimal("80.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 99

    cancel = client.post(
        f"{settings.API_V1_STR}/orders/me/{order_id}/cancel",
        headers=headers,
    )
    assert cancel.status_code == 200
    content = cancel.json()
    assert content["status"] == 8
    assert content["refunded_at"] is not None
    assert _wallet_balance(client, headers) == Decimal("100.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 100


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
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)

    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 200
    content = fulfill.json()
    assert content["status"] == 3
    assert content["processing_at"] is not None

    # 手动退款仅已完成订单可用，先置为已完成
    status_response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/status",
        headers=superuser_token_headers,
        json={"status": 6},
    )
    assert status_response.status_code == 200

    refund = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/refund",
        headers=superuser_token_headers,
        json={"amount": "20.00"},
    )
    assert refund.status_code == 200
    content = refund.json()
    assert content["status"] == 8
    assert content["refunded_at"] is not None
    assert Decimal(content["refunded_amount"]) == Decimal("20.00")
    assert _wallet_balance(client, headers) == Decimal("100.00")
    # 已完成订单手动退款不回补库存
    assert _product_stock(client, product["id"], superuser_token_headers) == 99


def test_admin_refund_rejects_amount_above_total(
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
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)
    client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/fulfill",
        headers=superuser_token_headers,
    )
    # 手动退款仅已完成订单可用，先置为已完成
    status_response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/status",
        headers=superuser_token_headers,
        json={"status": 6},
    )
    assert status_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/refund",
        headers=superuser_token_headers,
        json={"amount": "20.01"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "退款金额不能超过订单金额"
    assert _wallet_balance(client, headers) == Decimal("80.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 99

    detail = client.get(
        f"{settings.API_V1_STR}/orders/{order['id']}",
        headers=superuser_token_headers,
    )
    assert detail.json()["status"] == 6


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
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)

    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 200
    assert fulfill.json()["status"] == 6

    refund = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/refund",
        headers=superuser_token_headers,
        json={"amount": "20.00"},
    )
    assert refund.status_code == 200
    assert refund.json()["status"] == 8
    assert _wallet_balance(client, headers) == Decimal("100.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 99


def test_admin_refund_ignores_can_refund(
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
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)
    client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/fulfill",
        headers=superuser_token_headers,
    )
    # 手动退款仅已完成订单可用，先置为已完成
    status_response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/status",
        headers=superuser_token_headers,
        json={"status": 6},
    )
    assert status_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/refund",
        headers=superuser_token_headers,
        json={"amount": "20.00"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == 8
    assert _wallet_balance(client, headers) == Decimal("100.00")
    # 已完成订单手动退款不回补库存
    assert _product_stock(client, product["id"], superuser_token_headers) == 99


def test_user_cancel_rejects_non_refundable_api_product(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(
        client,
        db,
        superuser_token_headers,
        can_refund=False,
    )
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)

    response = client.post(
        f"{settings.API_V1_STR}/orders/me/{order['id']}/cancel",
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "该订单不支持向供应商申请退单"
    assert _wallet_balance(client, headers) == Decimal("80.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 99


def test_cancel_manual_order_refunds_regardless_of_can_refund(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """can_refund 仅约束 API 商品的供应商退单，本地/手动商品退单直接本地退款"""
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(
        client,
        superuser_token_headers,
        price_mode="fixed",
        fulfillment_type=2,
        can_refund=False,
    )
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)
    assert _wallet_balance(client, headers) == Decimal("80.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 99

    response = client.post(
        f"{settings.API_V1_STR}/orders/me/{order['id']}/cancel",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["status"] == 8
    assert content["refunded_at"] is not None
    assert _wallet_balance(client, headers) == Decimal("100.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 100


def test_admin_cancel_rejects_non_refundable_api_product(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(
        client,
        db,
        superuser_token_headers,
        can_refund=False,
    )
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)

    response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/cancel",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "该订单不支持向供应商申请退单"


def test_cancel_exception_order_locally_refunds(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """异常订单可申请退单，非 API 商品直接本地退款并回补库存"""
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(
        client,
        superuser_token_headers,
        price_mode="fixed",
        fulfillment_type=2,
    )
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)

    status_response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/status",
        headers=superuser_token_headers,
        json={"status": 9},
    )
    assert status_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/orders/me/{order['id']}/cancel",
        headers=headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["status"] == 8
    assert content["refunded_at"] is not None
    assert _wallet_balance(client, headers) == Decimal("100.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 100


def test_admin_update_order_status(
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
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)

    response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/status",
        headers=superuser_token_headers,
        json={"status": 3},
    )
    assert response.status_code == 200
    assert response.json()["status"] == 3
    assert response.json()["processing_at"] is not None

    response = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/status",
        headers=superuser_token_headers,
        json={"status": 9},
    )
    assert response.status_code == 200
    assert response.json()["status"] == 9

    for disallowed in (8, 10):
        response = client.post(
            f"{settings.API_V1_STR}/orders/{order['id']}/status",
            headers=superuser_token_headers,
            json={"status": disallowed},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "当前状态不允许手动设置"


def test_cancel_order_after_manual_fulfill_locally_refunds(
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
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)
    client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/fulfill",
        headers=superuser_token_headers,
    )

    response = client.post(
        f"{settings.API_V1_STR}/orders/me/{order['id']}/cancel",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == 8
    assert response.json()["refunded_at"] is not None
    assert Decimal(response.json()["refunded_amount"]) == Decimal("20.00")
    assert _wallet_balance(client, headers) == Decimal("100.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 100


def test_api_refund_application_auto_refunds_on_upstream_refunded(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )
    monkeypatch.setattr(
        YlsupClient,
        "create_order",
        lambda self, **kwargs: "10086",
    )
    monkeypatch.setattr(
        YlsupClient,
        "query_order",
        lambda self, order_ids: [
            UpstreamOrder(upstream_id="10086", status=3)
        ],
    )
    monkeypatch.setattr(
        YlsupClient,
        "cancel_order",
        lambda self, order_id: {"id": order_id},
    )

    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"], quantity=2),
    )
    assert order_response.status_code == 200
    order_id = _first_order_result(order_response)["id"]
    assert _wallet_balance(client, headers) == Decimal("60.00")

    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{order_id}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 200

    cancel = client.post(
        f"{settings.API_V1_STR}/orders/me/{order_id}/cancel",
        headers=headers,
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == 10

    # automation 步骤：cancel 已发布 order.after_sale_applied 事件并生成退单申请任务，
    # 任务池执行后调用上游退单申请，成功后状态转为退单中
    stats = automation_task_scan()
    assert stats["claimed"] >= 1
    db.expire_all()
    db_order = db.get(Order, uuid.UUID(order_id))
    assert db_order.status == 5

    # 上游退单完成，自动按公式退款入账
    monkeypatch.setattr(
        YlsupClient,
        "query_order",
        lambda self, order_ids: [
            UpstreamOrder(
                upstream_id="10086", status=8, start_num=2, current_num=2
            )
        ],
    )
    sync = client.post(
        f"{settings.API_V1_STR}/orders/{order_id}/sync-status",
        headers=superuser_token_headers,
    )
    assert sync.status_code == 200
    content = sync.json()
    assert content["status"] == 8
    assert content["refunded_at"] is not None
    assert Decimal(content["refunded_amount"]) == Decimal("40.00")
    assert content["start_quantity"] == 2
    assert content["current_quantity"] == 2
    assert _wallet_balance(client, headers) == Decimal("100.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 100


def test_api_refund_application_rejected_keeps_applying_after_sale(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """上游明确拒绝退单申请（业务性拒绝）时任务直接失败终态，订单保持申请售后中"""
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )
    monkeypatch.setattr(
        YlsupClient,
        "create_order",
        lambda self, **kwargs: "10086",
    )
    monkeypatch.setattr(
        YlsupClient,
        "query_order",
        lambda self, order_ids: [
            UpstreamOrder(upstream_id="10086", status=3)
        ],
    )

    def _reject_cancel(_self: object, _order_id: str) -> dict[str, Any]:
        raise SupplierClientRejectedError("当前订单状态不允许退款")

    monkeypatch.setattr(YlsupClient, "cancel_order", _reject_cancel)

    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order_id = _first_order_result(order_response)["id"]
    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{order_id}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 200

    cancel = client.post(
        f"{settings.API_V1_STR}/orders/me/{order_id}/cancel",
        headers=headers,
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == 10

    # 任务池执行：上游业务性拒绝 -> 任务直接失败终态（不重试），订单保持申请售后中
    stats = automation_task_scan()
    assert stats["failed"] >= 1
    assert stats["retried"] == 0
    db.expire_all()
    db_order = db.get(Order, uuid.UUID(order_id))
    assert db_order.status == 10


def test_sync_updates_quantities_and_refund_by_formula(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )
    monkeypatch.setattr(
        YlsupClient,
        "create_order",
        lambda self, **kwargs: "10086",
    )
    monkeypatch.setattr(
        YlsupClient,
        "query_order",
        lambda self, order_ids: [
            UpstreamOrder(upstream_id="10086", status=3)
        ],
    )

    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"], quantity=2),
    )
    assert order_response.status_code == 200
    order_id = _first_order_result(order_response)["id"]
    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{order_id}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 200

    db_order = db.get(Order, uuid.UUID(order_id))
    upstream = UpstreamOrder(
        upstream_id="10086",
        status=8,
        start_num=2,
        current_num=3,
    )
    monkeypatch.setattr(
        YlsupClient,
        "query_order",
        lambda self, order_ids: [upstream],
    )
    updated = sync_orders_status(session=db, db_orders=[db_order])
    assert updated[0].status == 8
    assert updated[0].start_quantity == 2
    assert updated[0].current_quantity == 3
    # 退款 = (2 - (3 - 2)) × 20 = 20，余额 60 + 20 = 80
    assert _wallet_balance(client, headers) == Decimal("80.00")
    assert _product_stock(client, product["id"], superuser_token_headers) == 100


def _create_api_product_with_supplier(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    *,
    can_refund: bool = True,
) -> tuple[dict, object]:
    supplier = create_random_supplier(db)
    product = _create_custom_inventory_product(
        client,
        superuser_token_headers,
        fulfillment_type=3,
        can_refund=can_refund,
    )
    db.add(
        ProductSupplier(
            product_id=uuid.UUID(product["id"]),
            supplier_id=supplier.id,
            sku_id="SKU-API",
        )
    )
    db.commit()
    return product, supplier


def test_fulfill_api_order_syncs_upstream_status(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, supplier = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )
    monkeypatch.setattr(
        YlsupClient,
        "create_order",
        lambda self, **kwargs: "10086",
    )
    monkeypatch.setattr(
        YlsupClient,
        "query_order",
        lambda self, order_ids: [
            UpstreamOrder(upstream_id="10086", status=3)
        ],
    )

    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order.status_code == 200
    assert _first_order_result(order)["status"] == 1

    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{_first_order_result(order)['id']}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 200
    assert fulfill.json()["status"] == 3
    assert fulfill.json()["supplier_order_id"] == "10086"
    assert fulfill.json()["supplier_id"] == str(supplier.id)
    assert fulfill.json()["sku_id"] == "SKU-API"

    monkeypatch.setattr(
        YlsupClient,
        "query_order",
        lambda self, order_ids: [
            UpstreamOrder(upstream_id="10086", status=6)
        ],
    )
    sync = client.post(
        f"{settings.API_V1_STR}/orders/{_first_order_result(order)['id']}/sync-status",
        headers=superuser_token_headers,
    )
    assert sync.status_code == 200
    assert sync.json()["status"] == 6
    assert sync.json()["completed_at"] is not None


def test_fulfill_api_order_parses_dict_order_id(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """上游下单响应 data 为 dict 时提取订单号（如 ylsup 返回 {'id': 3928053}）"""
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )
    monkeypatch.setattr(
        YlsupClient,
        "create_order",
        lambda self, **kwargs: {"id": 3928053},
    )

    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order.status_code == 200

    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{_first_order_result(order)['id']}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 200
    assert fulfill.json()["supplier_order_id"] == "3928053"


def test_fulfill_api_order_definite_failure_rolls_back_claim(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(client, db, superuser_token_headers)

    def raise_upstream_error(_self: object, **kwargs: object) -> dict:
        del kwargs
        raise SupplierClientError("上游下单失败")

    monkeypatch.setattr(YlsupClient, "create_order", raise_upstream_error)
    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order.status_code == 200

    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{_first_order_result(order)['id']}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 502
    assert fulfill.json()["detail"] == "供应商履约失败: 上游下单失败"

    detail = client.get(
        f"{settings.API_V1_STR}/orders/{_first_order_result(order)['id']}",
        headers=superuser_token_headers,
    )
    assert detail.json()["status"] == 1  # 明确失败回滚为已付款，等待下一轮重试
    assert detail.json()["fulfill_failed_count"] == 1
    assert _wallet_balance(client, headers) == Decimal("80.00")  # 失败不退款
    assert _product_stock(client, product["id"], superuser_token_headers) == 99


def test_fulfill_api_order_unknown_outcome_marks_exception(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(client, db, superuser_token_headers)

    def raise_unknown_error(_self: object, **kwargs: object) -> dict:
        del kwargs
        raise SupplierClientUnknownError("供应商 API 超时")

    monkeypatch.setattr(YlsupClient, "create_order", raise_unknown_error)
    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order.status_code == 200

    fulfill = client.post(
        f"{settings.API_V1_STR}/orders/{_first_order_result(order)['id']}/fulfill",
        headers=superuser_token_headers,
    )
    assert fulfill.status_code == 502
    assert "供应商履约结果未知，订单已转人工确认" in fulfill.json()["detail"]

    detail = client.get(
        f"{settings.API_V1_STR}/orders/{_first_order_result(order)['id']}",
        headers=superuser_token_headers,
    )
    assert detail.json()["status"] == 9  # 结果未知转人工确认
    assert detail.json()["fulfill_failed_count"] == 0


def test_fulfill_exception_order_definite_failure_keeps_exception(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """异常订单人工重新履约仍明确失败时保持异常，不回退为已付款"""
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(client, db, superuser_token_headers)

    def raise_unknown_error(_self: object, **kwargs: object) -> dict:
        del kwargs
        raise SupplierClientUnknownError("供应商 API 超时")

    monkeypatch.setattr(YlsupClient, "create_order", raise_unknown_error)
    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order.status_code == 200
    order_id = _first_order_result(order)["id"]

    first_try = client.post(
        f"{settings.API_V1_STR}/orders/{order_id}/fulfill",
        headers=superuser_token_headers,
    )
    assert first_try.status_code == 502

    detail = client.get(
        f"{settings.API_V1_STR}/orders/{order_id}",
        headers=superuser_token_headers,
    )
    assert detail.json()["status"] == 9
    assert detail.json()["fulfill_failed_count"] == 0

    def raise_upstream_error(_self: object, **kwargs: object) -> dict:
        del kwargs
        raise SupplierClientError("上游下单失败")

    monkeypatch.setattr(YlsupClient, "create_order", raise_upstream_error)
    second_try = client.post(
        f"{settings.API_V1_STR}/orders/{order_id}/fulfill",
        headers=superuser_token_headers,
    )
    assert second_try.status_code == 502
    assert second_try.json()["detail"] == "供应商履约失败: 上游下单失败"

    detail = client.get(
        f"{settings.API_V1_STR}/orders/{order_id}",
        headers=superuser_token_headers,
    )
    assert detail.json()["status"] == 9  # 人工已介入，失败后不回退为已付款
    assert detail.json()["fulfill_failed_count"] == 1
    assert "履约连续失败 1 次" in detail.json()["remark"]


def test_record_supplier_order_id_restores_pending(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product, _ = _create_api_product_with_supplier(client, db, superuser_token_headers)

    order = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order.status_code == 200

    record = client.post(
        f"{settings.API_V1_STR}/orders/{_first_order_result(order)['id']}/supplier-order-id",
        headers=superuser_token_headers,
        json={"supplier_order_id": "10086"},
    )
    assert record.status_code == 200
    assert record.json()["supplier_order_id"] == "10086"
    assert record.json()["status"] == 2  # PENDING，状态同步任务可继续处理


def _admin_order_payload(products: list[dict], quantities: list[int]) -> dict:
    return {
        "orders": [
            {
                "product_id": product["id"],
                "quantity": quantity,
                "params": {"account": f"admin-account-{index}"},
                "remark": f"管理员测试单-{index}",
            }
            for index, (product, quantity) in enumerate(
                zip(products, quantities, strict=False), start=1
            )
        ]
    }


def test_admin_create_order_success_skips_wallet_and_balance(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    superuser = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).one()
    product, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )

    response = client.post(
        f"{settings.API_V1_STR}/orders/admin",
        headers=superuser_token_headers,
        json=_admin_order_payload([product], [2]),
    )
    assert response.status_code == 200
    content = response.json()
    assert content["total"] == 1
    assert content["success_count"] == 1
    assert content["failure_count"] == 0

    result = content["results"][0]
    assert result["index"] == 1
    assert result["success"] is True
    assert result["detail"] is None
    order = result["order"]
    assert order["status"] == 1
    assert order["paid_at"] is not None
    assert order["user_id"] == str(superuser.id)
    assert order["username"] == superuser.username
    assert order["remark"] == "管理员测试单-1"
    assert Decimal(order["total_amount"]) == Decimal("40.00")
    assert order["product_id"] == product["id"]
    assert order["quantity"] == 2
    assert order["params"] == {"account": "admin-account-1"}
    assert _product_stock(client, product["id"], superuser_token_headers) == 98
    assert "供应商" not in response.text


def test_admin_create_order_rejects_repeat_purchase(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    product, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )

    first = client.post(
        f"{settings.API_V1_STR}/orders/admin",
        headers=superuser_token_headers,
        json=_admin_order_payload([product], [1]),
    )
    assert first.status_code == 200
    assert first.json()["success_count"] == 1

    second = client.post(
        f"{settings.API_V1_STR}/orders/admin",
        headers=superuser_token_headers,
        json=_admin_order_payload([product], [1]),
    )
    assert second.status_code == 200
    content = second.json()
    assert content["success_count"] == 0
    assert content["failure_count"] == 1
    result = content["results"][0]
    assert result["success"] is False
    assert result["order"] is None
    assert result["detail"] == "该商品相同参数订单未完成，禁止重复下单"
    assert _product_stock(client, product["id"], superuser_token_headers) == 99


def test_admin_create_order_allows_same_product_different_params(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    product, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )

    first = client.post(
        f"{settings.API_V1_STR}/orders/admin",
        headers=superuser_token_headers,
        json=_admin_order_payload([product], [1]),
    )
    assert first.status_code == 200
    assert first.json()["success_count"] == 1

    payload = _admin_order_payload([product], [1])
    payload["orders"][0]["params"] = {"account": "admin-account-other"}
    second = client.post(
        f"{settings.API_V1_STR}/orders/admin",
        headers=superuser_token_headers,
        json=payload,
    )
    assert second.status_code == 200
    assert second.json()["success_count"] == 1


@pytest.mark.parametrize(
    ("disable_field", "disable_value"),
    [("is_active", False), ("status", "inactive")],
)
def test_admin_create_order_rejects_unavailable_supplier(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    disable_field: str,
    disable_value: object,
) -> None:
    supplier = create_random_supplier(db)
    product = _create_custom_inventory_product(
        client,
        superuser_token_headers,
        fulfillment_type=3,
    )
    db.add(
        ProductSupplier(
            product_id=uuid.UUID(product["id"]),
            supplier_id=supplier.id,
            sku_id="SKU-API",
        )
    )
    setattr(supplier, disable_field, disable_value)
    db.add(supplier)
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/orders/admin",
        headers=superuser_token_headers,
        json=_admin_order_payload([product], [1]),
    )
    assert response.status_code == 200
    content = response.json()
    assert content["success_count"] == 0
    assert content["failure_count"] == 1
    result = content["results"][0]
    assert result["success"] is False
    assert result["order"] is None
    assert result["detail"] == "商品暂不可下单，请稍后重试"
    assert "供应商" not in response.text
    assert _product_stock(client, product["id"], superuser_token_headers) == 100


def test_admin_create_orders_partial_success(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    product_a, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )
    product_b, supplier_b = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )
    supplier_b.is_active = False
    db.add(supplier_b)
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/orders/admin",
        headers=superuser_token_headers,
        json=_admin_order_payload([product_a, product_b, product_a], [1, 1, 1]),
    )
    assert response.status_code == 200
    content = response.json()
    assert content["total"] == 3
    assert content["success_count"] == 2
    assert content["failure_count"] == 1
    results = content["results"]
    assert [result["success"] for result in results] == [True, False, True]
    assert results[0]["index"] == 1
    assert results[1]["index"] == 2
    assert results[2]["index"] == 3
    assert results[0]["order"] is not None
    assert results[1]["order"] is None
    assert results[2]["order"] is not None
    assert results[1]["detail"] == "商品暂不可下单，请稍后重试"
    assert "供应商" not in response.text
    assert _product_stock(client, product_a["id"], superuser_token_headers) == 98
    assert _product_stock(client, product_b["id"], superuser_token_headers) == 100


def test_admin_create_orders_requires_superuser(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/orders/admin",
        headers=normal_user_token_headers,
        json={"orders": []},
    )
    assert response.status_code == 403


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
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers_a,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)

    headers_b, _ = _create_wallet_user(client, db)
    response = client.get(
        f"{settings.API_V1_STR}/orders/me/{order['id']}",
        headers=headers_b,
    )
    assert response.status_code == 404


def test_admin_order_list_filters_by_user_and_includes_username(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers_a, user_a = _create_wallet_user(client, db)
    headers_b, user_b = _create_wallet_user(client, db)
    _fund_wallet(client, headers_a, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers_a,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)

    response = client.get(
        f"{settings.API_V1_STR}/orders/?user_id={user_a.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 1
    item = content["data"][0]
    assert item["params"] == order["params"]
    assert content["data"][0]["username"] == user_a.username
    assert item["start_quantity"] == order["start_quantity"]
    assert item["current_quantity"] == order["current_quantity"]
    assert item.keys() == {
        "id",
        "username",
        "status",
        "total_amount",
        "product_name",
        "quantity",
        "start_quantity",
        "current_quantity",
        "params",
        "created_at",
    }

    response_b = client.get(
        f"{settings.API_V1_STR}/orders/?user_id={user_b.id}",
        headers=superuser_token_headers,
    )
    assert response_b.status_code == 200
    assert response_b.json() == {"data": [], "count": 0}


def test_admin_order_list_filters_by_keyword(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, user = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")

    value_a = f"param-query-{uuid.uuid4().hex}"
    value_b = f"param-query-{uuid.uuid4().hex}"
    first = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"], params={"account": value_a}),
    )
    assert first.status_code == 200
    second = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"], params={"account": value_b}),
    )
    assert second.status_code == 200
    order_a = _first_order_result(first)

    response = client.get(
        f"{settings.API_V1_STR}/orders/?keyword={value_a}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 1
    assert content["data"][0]["params"] == {"account": value_a}

    response_b = client.get(
        f"{settings.API_V1_STR}/orders/?keyword={value_b}",
        headers=superuser_token_headers,
    )
    assert response_b.status_code == 200
    content_b = response_b.json()
    assert content_b["count"] == 1
    assert content_b["data"][0]["params"] == {"account": value_b}

    # 按订单号精确匹配
    response_no = client.get(
        f"{settings.API_V1_STR}/orders/?keyword={order_a['order_no']}",
        headers=superuser_token_headers,
    )
    assert response_no.status_code == 200
    content_no = response_no.json()
    assert content_no["count"] == 1
    assert content_no["data"][0]["id"] == order_a["id"]

    # 按订单 ID 精确匹配
    response_id = client.get(
        f"{settings.API_V1_STR}/orders/?keyword={order_a['id']}",
        headers=superuser_token_headers,
    )
    assert response_id.status_code == 200
    content_id = response_id.json()
    assert content_id["count"] == 1
    assert content_id["data"][0]["id"] == order_a["id"]

    # 按用户名精确匹配
    response_user = client.get(
        f"{settings.API_V1_STR}/orders/?keyword={quote(user.username)}",
        headers=superuser_token_headers,
    )
    assert response_user.status_code == 200
    content_user = response_user.json()
    assert content_user["count"] == 2
    assert all(
        item["username"] == user.username for item in content_user["data"]
    )


def test_admin_create_order_syncs_order_params_for_query(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    product, _ = _create_api_product_with_supplier(
        client, db, superuser_token_headers
    )
    value = f"admin-param-{uuid.uuid4().hex}"
    response = client.post(
        f"{settings.API_V1_STR}/orders/admin",
        headers=superuser_token_headers,
        json={
            "orders": [
                {
                    "product_id": product["id"],
                    "quantity": 1,
                    "params": {"account": value},
                }
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["success_count"] == 1

    query = client.get(
        f"{settings.API_V1_STR}/orders/?keyword={value}",
        headers=superuser_token_headers,
    )
    assert query.status_code == 200
    content = query.json()
    assert content["count"] >= 1
    assert all(item["params"].get("account") == value for item in content["data"])


def test_admin_order_detail_includes_username(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, user = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(client, superuser_token_headers, price_mode="fixed")
    order_response = client.post(
        f"{settings.API_V1_STR}/orders/",
        headers=headers,
        json=_order_payload(product["id"]),
    )
    assert order_response.status_code == 200
    order = _first_order_result(order_response)

    response = client.get(
        f"{settings.API_V1_STR}/orders/{order['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    detail = response.json()
    assert detail["username"] == user.username
    assert detail["id"] == order["id"]
    assert detail["unit_price"] == order["unit_price"]
    assert detail["currency"] == order["currency"]

    cancel = client.post(
        f"{settings.API_V1_STR}/orders/{order['id']}/cancel",
        headers=superuser_token_headers,
    )
    assert cancel.status_code == 200
    assert cancel.json()["username"] == user.username


def test_cleanup_completed_orders_purges_terminal_orders(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """定期清理只删除超过保留期的终态订单，保留钱包流水与非终态/未过期订单"""
    from datetime import UTC, datetime, timedelta

    headers, _ = _create_wallet_user(client, db)
    _fund_wallet(client, headers, superuser_token_headers)
    product = _create_ready_product(
        client, superuser_token_headers, price_mode="fixed"
    )

    order_index = 0

    def _create_order() -> Order:
        nonlocal order_index
        order_index += 1
        resp = client.post(
            f"{settings.API_V1_STR}/orders/",
            headers=headers,
            json=_order_payload(
                product["id"],
                params={"account": f"cleanup-{order_index}"},
            ),
        )
        assert resp.status_code == 200
        return db.get(Order, uuid.UUID(_first_order_result(resp)["id"]))

    now = datetime.now(UTC)
    old = _create_order()
    old.status = OrderStatus.COMPLETED
    old.updated_at = now - timedelta(days=30)
    refunded = _create_order()
    refunded.status = OrderStatus.REFUNDED
    refunded.updated_at = now - timedelta(days=30)
    recent = _create_order()
    recent.status = OrderStatus.COMPLETED
    recent.updated_at = now
    active = _create_order()
    active.status = OrderStatus.PROCESSING
    active.updated_at = now - timedelta(days=30)
    old_id, refunded_id, recent_id, active_id = (
        old.id,
        refunded.id,
        recent.id,
        active.id,
    )
    db.add_all([old, refunded, recent, active])
    db.commit()

    stats = cleanup_completed_orders()
    assert stats["errors"] == []
    assert stats["purged"] == 2
    for order_id in (old_id, refunded_id):
        assert db.exec(
            select(Order.id).where(Order.id == order_id)
        ).first() is None
    for order_id in (recent_id, active_id):
        assert db.exec(
            select(Order.id).where(Order.id == order_id)
        ).first() is not None
    # 订单参数随订单物理删除
    for order_id in (old_id, refunded_id):
        remaining = db.exec(
            select(OrderParam).where(OrderParam.order_id == order_id)
        ).all()
        assert remaining == []
    # 钱包流水保留（4 张订单对应 4 笔消费）
    assert len(_order_transactions(client, headers)) == 4
