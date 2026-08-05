"""供应商模块：业务逻辑层"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from app.modules.product.category.models import ProductCategory
from app.modules.product.category.service import sync_category_product_count
from app.modules.product.constants import (
    InputType,
    ProductStatus,
    ProductType,
    RedeemType,
    SourceType,
)
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import SupplierCreate
from app.modules.supplier.service.clients.base import ClientMeta, SupplierClientBase
from app.modules.supplier.service.dto import (
    UpstreamBuyParam,
    UpstreamCategory,
    UpstreamProductDetail,
    UpstreamProductSummary,
)


def create_supplier(*, session: Session, supplier_in: SupplierCreate) -> Supplier:
    """创建供应商"""
    db_supplier = Supplier.model_validate(supplier_in)
    session.add(db_supplier)
    session.commit()
    session.refresh(db_supplier)
    return db_supplier


@contextmanager
def supplier_client(
    *, session: Session, supplier_id: uuid.UUID | str
) -> Iterator[SupplierClientBase]:
    """根据供应商ID获取客户端，作为上下文管理器使用，退出时自动关闭"""
    sup = session.get(Supplier, supplier_id)
    if not sup:
        raise ValueError(f"供应商不存在 (ID: {supplier_id})")

    client = ClientMeta.get_client(sup, session=session)
    try:
        yield client
    finally:
        client.close()


def list_upstream_products(
    *,
    session: Session,
    supplier_id: uuid.UUID | str,
    category_id: str | None = None,
) -> list[dict[str, Any]]:
    """获取上游商品列表，并标记是否已同步到本地"""
    with supplier_client(session=session, supplier_id=supplier_id) as client:
        items: list[UpstreamProductSummary] = client.query_products_list(
            page=1,
            page_size=100,
            category_id=category_id,
        )

    local_rows = session.exec(
        select(ProductSupplier).where(ProductSupplier.supplier_id == supplier_id)
    ).all()
    local_by_sku = {
        row.sku_id: row.product_id for row in local_rows if row.sku_id
    }

    result: list[dict[str, Any]] = []
    for item in items:
        upstream_id = item.upstream_id
        result.append(
            {
                "upstream_id": upstream_id,
                "name": item.name,
                "cost_price": item.cost_price,
                "synced": upstream_id in local_by_sku,
                "local_product_id": local_by_sku.get(upstream_id),
            }
        )
    return result


def list_upstream_categories(
    *,
    session: Session,
    supplier_id: uuid.UUID | str,
) -> list[dict[str, str]]:
    """获取上游商品分类列表"""
    with supplier_client(session=session, supplier_id=supplier_id) as client:
        categories: list[UpstreamCategory] = client.get_categories()

    return [
        {
            "id": item.id,
            "name": item.name,
            "parent_id": str(item.parent_id or "0"),
        }
        for item in categories
    ]


def _build_buy_params(params: list[UpstreamBuyParam]) -> list[dict[str, Any]]:
    """将上游购买参数契约转为本地 ProductBuyParam 字段字典"""
    result: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for param in params:
        key = param.key
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        input_type = (
            InputType.LINK_EXTRACT if param.input_type == 61 else InputType.TEXT
        )
        result.append(
            {
                "key": key,
                "label": param.label,
                "value": param.value,
                "description": param.description,
                "input_type": input_type,
                "type_config": param.type_config,
                "default_value": param.default_value,
                "use_default": param.use_default,
                "is_required": True,
                "is_hidden": False,
                "is_edit": True,
                "validate_min": param.validate_min,
                "validate_max": param.validate_max,
            }
        )
    return result


def sync_upstream_product(
    *,
    session: Session,
    supplier: Supplier,
    detail: UpstreamProductDetail,
    category_id: uuid.UUID | None = None,
) -> tuple[str, Any]:
    """同步单个上游商品到本地：匹配时只更新成本价，未匹配时创建完整商品"""
    upstream_id = detail.upstream_id
    cost_price = detail.cost_price
    if category_id is not None and session.get(ProductCategory, category_id) is None:
        raise ValueError("本地分类不存在")
    db_supplier = session.exec(
        select(ProductSupplier).where(
            ProductSupplier.supplier_id == supplier.id,
            ProductSupplier.sku_id == upstream_id,
        )
    ).first()

    if db_supplier:
        db_product = session.get(Product, db_supplier.product_id)
        if db_product is None:
            raise ValueError("已同步商品缺少商品记录，无法更新")
        db_pricing = session.exec(
            select(ProductPricing).where(
                ProductPricing.product_id == db_supplier.product_id
            )
        ).first()
        if db_pricing is None:
            raise ValueError("已同步商品缺少定价配置，无法更新成本价")
        old_category_id = db_product.category_id
        db_pricing.cost_price = cost_price
        if category_id is not None and category_id != db_product.category_id:
            db_product.category_id = category_id
            session.add(db_product)
        session.add(db_pricing)
        session.commit()
        if category_id is not None and old_category_id != category_id:
            if old_category_id is not None:
                sync_category_product_count(
                    session=session, category_id=old_category_id
                )
            sync_category_product_count(session=session, category_id=category_id)
        return "updated", db_supplier.product_id

    min_quantity = max(detail.min_quantity, 1)
    max_quantity = max(detail.max_quantity, 1)
    purchase_step = detail.purchase_step
    if max_quantity < min_quantity:
        max_quantity = min_quantity
    stock = max(detail.stock, -1)
    product_type = (
        ProductType.CARD if detail.is_card_code else ProductType.NORMAL_PRODUCT
    )
    buy_params = _build_buy_params(detail.buy_params)

    product = Product(
        name=str(detail.name or f"上游商品 {upstream_id}"),
        category_id=category_id,
        image_id=None,
        source_type=SourceType.API_INTEGRATION,
        status=ProductStatus.PENDING_REVIEW,
        is_closed=detail.is_closed,
        sort=0,
        type=product_type,
    )
    session.add(product)
    session.flush()
    product_id = product.id

    session.add(
        ProductSupplier(
            product_id=product_id,
            supplier_id=supplier.id,
            sku_id=upstream_id,
        )
    )
    session.add(
        ProductPricing(
            product_id=product_id,
            cost_price=cost_price,
            fixed_price=cost_price,
            loss_price=Decimal("0.00"),
        )
    )
    session.add(
        ProductInventory(
            product_id=product_id,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
            purchase_step=purchase_step,
            is_repeatable=detail.is_repeatable,
            is_batch=detail.is_batch,
            stock=stock,
        )
    )
    session.add(
        ProductFulfillment(
            product_id=product_id,
            fulfillment_type=RedeemType.AUTO_API,
            description=detail.description,
            unit=detail.unit,
            can_refund=detail.can_refund,
            params_template=buy_params,
        )
    )
    for param in buy_params:
        session.add(ProductBuyParam(product_id=product_id, **param))

    session.commit()
    if category_id is not None:
        sync_category_product_count(session=session, category_id=category_id)
    return "created", product_id
