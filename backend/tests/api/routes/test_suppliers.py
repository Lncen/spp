"""供应商模块：API 测试"""

import uuid
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.product.category.models import ProductCategory
from app.modules.product.constants import (
    ProductStatus,
    ProductType,
    SourceType,
    SyncStatus,
)
from app.modules.product.product.models import (
    Product,
    ProductPricing,
    ProductSupplier,
)
from app.modules.supplier.application.create import (
    create_supplier as create_supplier_service,
)
from app.modules.supplier.application.sync import sync_upstream_product
from app.modules.supplier.infrastructure.clients.base import (
    SupplierClientError,
    SupplierClientUnknownError,
    supplier_client,
)
from app.modules.supplier.infrastructure.clients.ylsup import YlsupClient
from app.modules.supplier.models import Supplier
from app.modules.supplier.repositories.supplier import (
    mark_product_sync_failed,
)
from app.modules.supplier.schemas import PlatformEnum, SupplierCreate
from app.modules.supplier.schemas.upstream import (
    UpstreamBuyParam,
    UpstreamCategory,
    UpstreamProductDetail,
    UpstreamProductSummary,
)
from tests.utils.utils import random_lower_string


class FakeResponse:
    """模拟 httpx.Response，仅提供 json()"""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def create_random_supplier(db: Session) -> Supplier:
    supplier_in = SupplierCreate(
        platform=PlatformEnum.YLSUP,
        name=random_lower_string(),
        base_url="https://example.com",
        app_key=random_lower_string(),
        app_secret=random_lower_string(),
    )
    return create_supplier_service(session=db, supplier_in=supplier_in)


def create_local_product(
    db: Session,
    supplier: Supplier,
    sku_id: str,
    name: str = "本地商品",
) -> Product:
    product = Product(
        name=name,
        source_type=SourceType.LOCAL,
        status=ProductStatus.READY,
        type=ProductType.NORMAL_PRODUCT,
    )
    db.add(product)
    db.flush()
    db.add(
        ProductSupplier(
            product_id=product.id,
            supplier_id=supplier.id,
            sku_id=sku_id,
        )
    )
    db.add(
        ProductPricing(
            product_id=product.id,
            cost_price=Decimal("1.00"),
            fixed_price=Decimal("2.00"),
        )
    )
    db.commit()
    db.refresh(product)
    return product


def test_read_supplier_balance(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)
    monkeypatch.setattr(
        YlsupClient,
        "get",
        lambda self, path, **kwargs: FakeResponse(
            {"code": 0, "data": {"name": "py66", "balance": 64.31946365}}
        ),
    )
    response = client.get(
        f"{settings.API_V1_STR}/suppliers/{supplier.id}/balance",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert Decimal(response.json()["balance"]) == Decimal("64.3194636")
    db.refresh(supplier)
    assert supplier.balance == Decimal("64.3194636")


def test_successful_access_updates_connection_status(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)
    assert supplier.connection_status == "unknown"

    with supplier_client(session=db, supplier_id=supplier.id) as client:
        monkeypatch.setattr(
            client._client,
            "request",
            lambda _method, _path, **_kwargs: httpx.Response(
                200,
                json={"code": 0, "data": {"name": "py66", "balance": 64.31946365}},
            ),
        )
        assert client.query_balance() == Decimal("64.31946365")

    db.refresh(supplier)
    assert supplier.connection_status == "online"


def test_query_balance_parses_upstream_payload(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)
    client = YlsupClient(supplier)
    monkeypatch.setattr(
        client,
        "get",
        lambda path: FakeResponse(
            {"code": 0, "data": {"name": "py66", "balance": 64.31946365}}
        ),
    )
    try:
        assert client.query_balance() == Decimal("64.31946365")
    finally:
        client.close()


def test_query_balance_missing_balance_raises(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)
    client = YlsupClient(supplier)
    monkeypatch.setattr(
        client,
        "get",
        lambda path: FakeResponse({"code": 0, "data": {}}),
    )
    try:
        with pytest.raises(SupplierClientError):
            client.query_balance()
    finally:
        client.close()


def test_read_supplier_balance_requires_superuser(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    supplier = create_random_supplier(db)
    response = client.get(
        f"{settings.API_V1_STR}/suppliers/{supplier.id}/balance",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "权限不足"


def test_read_supplier_balance_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/suppliers/{uuid.uuid4()}/balance",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "供应商不存在"


def test_read_supplier_balance_upstream_error(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)

    def raise_upstream_error(_self: object) -> Decimal:
        raise SupplierClientError("上游 API 错误")

    monkeypatch.setattr(YlsupClient, "query_balance", raise_upstream_error)
    response = client.get(
        f"{settings.API_V1_STR}/suppliers/{supplier.id}/balance",
        headers=superuser_token_headers,
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "上游 API 错误"


def test_ylsup_client_parses_upstream_payloads(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)
    client = YlsupClient(supplier)
    calls: list[tuple[str, dict]] = []

    def fake_get(path: str, **kwargs: object) -> FakeResponse:
        calls.append(("get", kwargs))
        if path.endswith("/Goods/CategoryList"):
            return FakeResponse(
                {
                    "code": 0,
                    "data": [
                        {
                            "id": 2,
                            "parent_id": 0,
                            "name": "DY 运营",
                            "parent_infos": [
                                {"id": 195, "parent_id": 2, "name": "直播间"}
                            ],
                        }
                    ],
                }
            )
        return FakeResponse({"code": 0, "data": {"id": 838, "price": 0.01296}})

    def fake_post(path: str, **kwargs: object) -> FakeResponse:
        calls.append(("post", kwargs))
        if path.endswith("/Goods/List"):
            return FakeResponse(
                {"code": 0, "data": [{"id": 58, "name": "VIP444444444"}]}
            )
        if path.endswith("/Goods/Show"):
            return FakeResponse({"code": 0, "data": {"id": 838, "price": 0.01296}})
        if path.endswith("/Order/Show"):
            return FakeResponse(
                {
                    "code": 0,
                    "data": [
                        {"id": 3, "status": 5},
                        {"id": 4, "status": 6},
                    ],
                }
            )
        if path.endswith("/Order/StatusHandle"):
            return FakeResponse({"code": 0, "data": {"id": 202539}})
        return FakeResponse({"code": 0, "data": {"order_id": "10086"}})

    monkeypatch.setattr(client, "get", fake_get)
    monkeypatch.setattr(client, "post", fake_post)
    try:
        assert client.get_categories() == [
            UpstreamCategory(id="2", name="DY 运营", parent_id="0"),
            UpstreamCategory(id="195", name="直播间", parent_id="2"),
        ]
        assert client.query_products_list(category_id="6") == [
            UpstreamProductSummary(
                upstream_id="58",
                name="VIP444444444",
                cost_price=None,
            )
        ]
        assert client.query_product_detail("838") == UpstreamProductDetail(
            upstream_id="838",
            cost_price=Decimal("0.01296"),
            is_closed=True,
        )
        assert client.create_order(
            product_id="1",
            quantity=1,
            Parameter_1="11",
        ) == {"order_id": "10086"}
        orders = client.query_order([3, 4])
        assert [order.upstream_id for order in orders] == ["3", "4"]
        assert [order.status for order in orders] == [5, 6]
        assert client.cancel_order("202539") == {"id": 202539}
    finally:
        client.close()

    assert calls[0] == ("get", {})
    assert calls[1] == (
        "post",
        {
            "json": {
                "page": 1,
                "page_size": 20,
                "goods_category_id": "6",
            }
        },
    )
    assert calls[2] == ("post", {"json": {"goods_id": "838"}})
    assert calls[3][1]["json"] == {
        "goods_id": "1",
        "buy_number": 1,
        "buy_params": {"Parameter_1": "11"},
    }
    assert calls[4][1]["json"] == {"ids": [3, 4]}
    assert calls[5][1]["json"] == {"id": "202539", "status": 5}


def test_ylsup_client_create_order_missing_data_is_unknown(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """下单响应缺 data 时视为结果未知（上游可能已下单），不得按明确失败重试"""
    supplier = create_random_supplier(db)
    client = YlsupClient(supplier)
    monkeypatch.setattr(
        client,
        "post",
        lambda path, **kwargs: FakeResponse({"code": 0}),
    )
    try:
        with pytest.raises(SupplierClientUnknownError):
            client.create_order(product_id="1", quantity=1)
    finally:
        client.close()


def test_read_upstream_products_marks_synced(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)
    local_product = create_local_product(db, supplier, "58")
    monkeypatch.setattr(
        YlsupClient,
        "query_products_list",
        lambda self, **kwargs: [
            UpstreamProductSummary(upstream_id="58", name="VIP444444444"),
            UpstreamProductSummary(upstream_id="59", name="新商品"),
        ],
    )
    response = client.get(
        f"{settings.API_V1_STR}/suppliers/{supplier.id}/upstream-products",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["data"][0] == {
        "upstream_id": "58",
        "name": "VIP444444444",
        "cost_price": None,
        "synced": True,
        "local_product_id": str(local_product.id),
    }
    assert payload["data"][1]["synced"] is False
    assert payload["data"][1]["local_product_id"] is None


def test_read_upstream_categories(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)
    monkeypatch.setattr(
        YlsupClient,
        "get_categories",
        lambda self: [
            UpstreamCategory(id="101", name="自营", parent_id="0"),
            UpstreamCategory(id="102", name="卡密", parent_id="0"),
        ],
    )
    response = client.get(
        f"{settings.API_V1_STR}/suppliers/{supplier.id}/upstream-categories",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"] == [
        {"id": "101", "name": "自营", "parent_id": "0"},
        {"id": "102", "name": "卡密", "parent_id": "0"},
    ]


def test_read_upstream_products_passes_category_id(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)
    calls: list[dict] = []

    def fake_query_products_list(_self, **kwargs: object) -> list:
        calls.append(kwargs)
        return []

    monkeypatch.setattr(YlsupClient, "query_products_list", fake_query_products_list)
    response = client.get(
        f"{settings.API_V1_STR}/suppliers/{supplier.id}/upstream-products",
        params={"category_id": "6"},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert calls == [{"page": 1, "page_size": 100, "category_id": "6"}]


def test_sync_upstream_product_creates_and_updates(
    db: Session,
) -> None:
    supplier = create_random_supplier(db)
    category = ProductCategory(name="测试分类")
    db.add(category)
    db.commit()
    db.refresh(category)
    second_category = ProductCategory(name="测试分类二")
    db.add(second_category)
    db.commit()
    db.refresh(second_category)
    detail = UpstreamProductDetail(
        upstream_id="838",
        name="VIP快速)",
        cost_price=Decimal("0.01296"),
        stock=-1,
        min_quantity=10,
        max_quantity=1_000_000,
        is_repeatable=True,
        is_batch=True,
        is_card_code=False,
        is_closed=False,
        unit="1",
        buy_params=[
            UpstreamBuyParam(
                key="url",
                label="作品纯链接",
                value="",
                description="点击右侧提取",
                input_type=61,
                type_config=[],
                validate_min=0,
                validate_max=0,
                default_value="",
                use_default=False,
            )
        ],
    )

    action, product_id = sync_upstream_product(
        session=db,
        supplier=supplier,
        detail=detail,
        category_id=category.id,
    )
    assert action == "created"
    product = db.get(Product, product_id)
    assert product is not None
    assert product.name == "VIP快速)"
    assert product.source_type == SourceType.API_INTEGRATION
    assert product.status == ProductStatus.PENDING_REVIEW
    assert product.type == ProductType.NORMAL_PRODUCT
    assert product.category_id == category.id
    db.refresh(category)
    assert category.product_count == 1

    pricing = db.exec(
        select(ProductPricing).where(ProductPricing.product_id == product.id)
    ).one()
    assert pricing.cost_price == Decimal("0.01296")
    assert pricing.fixed_price == Decimal("0.01296")

    row = db.exec(
        select(ProductSupplier).where(
            ProductSupplier.supplier_id == supplier.id,
            ProductSupplier.sku_id == "838",
        )
    ).one()
    assert row.product_id == product.id

    action, updated_id = sync_upstream_product(
        session=db,
        supplier=supplier,
        detail=detail.model_copy(update={"cost_price": Decimal("0.02")}),
        category_id=second_category.id,
    )
    assert action == "updated"
    assert updated_id == product.id
    db.refresh(pricing)
    assert pricing.cost_price == Decimal("0.02")
    db.refresh(product)
    assert product.category_id == second_category.id
    db.refresh(category)
    db.refresh(second_category)
    assert category.product_count == 0
    assert second_category.product_count == 1

    action, updated_id = sync_upstream_product(
        session=db,
        supplier=supplier,
        detail=detail.model_copy(update={"cost_price": Decimal("0.03")}),
    )
    assert action == "updated"
    assert updated_id == product.id
    db.refresh(product)
    assert product.category_id == second_category.id


def test_create_upstream_products_sync_returns_task_id(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)
    category = ProductCategory(name="测试分类")
    db.add(category)
    db.commit()
    db.refresh(category)
    sent_kwargs: dict = {}

    class FakeTask:
        id = "fake-task-id"

    def fake_send_task(_name: str, **kwargs: object) -> FakeTask:
        sent_kwargs.update(kwargs)
        return FakeTask()

    monkeypatch.setattr(
        "app.modules.automation.infrastructure.tasks.supplier_sync.celery_app.send_task",
        fake_send_task,
    )
    response = client.post(
        f"{settings.API_V1_STR}/suppliers/{supplier.id}/upstream-products/sync",
        headers=superuser_token_headers,
        json={
            "product_ids": ["58", "59"],
            "category_id": str(category.id),
        },
    )
    assert response.status_code == 200
    assert response.json()["task_id"] == "fake-task-id"
    assert sent_kwargs["kwargs"]["category_id"] == str(category.id)


def test_read_upstream_products_sync_status(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)

    class FakeResult:
        state = "SUCCESS"
        result = {"status": "success", "created": ["1"], "updated": [], "failed": []}

    monkeypatch.setattr(
        "app.modules.automation.infrastructure.celery.AsyncResult",
        lambda task_id, app: FakeResult(),
    )
    response = client.get(
        f"{settings.API_V1_STR}/suppliers/{supplier.id}"
        "/upstream-products/sync/fake-task-id",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"
    assert response.json()["success"] is True
    assert response.json()["result"]["created"] == ["1"]


def test_read_upstream_products_sync_status_pending(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supplier = create_random_supplier(db)

    class FakeResult:
        state = "STARTED"

    monkeypatch.setattr(
        "app.modules.automation.infrastructure.celery.AsyncResult",
        lambda task_id, app: FakeResult(),
    )
    response = client.get(
        f"{settings.API_V1_STR}/suppliers/{supplier.id}"
        "/upstream-products/sync/fake-task-id",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "STARTED"
    assert response.json()["success"] is None
    assert response.json()["result"] is None


def test_sync_product_saves_upstream_sync_fields(
    db: Session,
) -> None:
    """上游同步成功后保存同步状态、同步时间与上游商品名称"""
    supplier = create_random_supplier(db)
    detail = UpstreamProductDetail(
        upstream_id="838",
        name="VIP快速)",
        cost_price=Decimal("0.01296"),
    )

    action, product_id = sync_upstream_product(
        session=db,
        supplier=supplier,
        detail=detail,
    )
    assert action == "created"
    product = db.get(Product, product_id)
    assert product is not None
    assert product.sync_status == SyncStatus.SUCCESS
    assert product.synced_at is not None
    row = db.exec(
        select(ProductSupplier).where(
            ProductSupplier.supplier_id == supplier.id,
            ProductSupplier.sku_id == "838",
        )
    ).one()
    assert row.upstream_name == "VIP快速)"

    action, _ = sync_upstream_product(
        session=db,
        supplier=supplier,
        detail=detail.model_copy(update={"name": "上游改名"}),
    )
    assert action == "updated"
    db.refresh(row)
    assert row.upstream_name == "上游改名"
    db.refresh(product)
    assert product.sync_status == SyncStatus.SUCCESS
    assert product.synced_at is not None


def test_mark_product_sync_failed(db: Session) -> None:
    """标记本地商品上游同步异常"""
    supplier = create_random_supplier(db)
    local_product = create_local_product(db, supplier, "58")

    mark_product_sync_failed(session=db, product_id=local_product.id)
    db.refresh(local_product)
    assert local_product.sync_status == SyncStatus.FAILED
    assert local_product.synced_at is not None
