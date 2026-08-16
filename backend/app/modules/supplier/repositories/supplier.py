"""供应商模块：数据访问层"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.modules.price_template.constants import DEFAULT_DISCOUNT_RATE
from app.modules.product.constants import (
    ProductStatus,
    ProductType,
    RedeemType,
    SourceType,
    SyncStatus,
)
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.supplier.domain.mapping import calc_sync_fixed_price
from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import SupplierCreate
from app.modules.supplier.schemas.upstream import UpstreamProductDetail


def get_supplier_or_404(*, session: Session, supplier_id: uuid.UUID) -> Supplier:
    """按 ID 获取供应商，不存在时抛出 404"""
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return supplier


def list_suppliers(
    *, session: Session, skip: int, limit: int
) -> tuple[list[Supplier], int]:
    """分页查询供应商列表（按创建时间倒序）"""
    count = session.exec(select(func.count()).select_from(Supplier)).one()
    statement = (
        select(Supplier)
        .order_by(col(Supplier.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all()), count


def create_supplier(*, session: Session, supplier_in: SupplierCreate) -> Supplier:
    """创建供应商"""
    db_supplier = Supplier.model_validate(supplier_in)
    session.add(db_supplier)
    session.commit()
    session.refresh(db_supplier)
    return db_supplier


def update_supplier(
    *, session: Session, supplier: Supplier, update_dict: dict[str, Any]
) -> Supplier:
    """更新供应商字段并提交"""
    supplier.sqlmodel_update(update_dict)
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return supplier


def delete_supplier(*, session: Session, supplier: Supplier) -> None:
    """删除供应商"""
    session.delete(supplier)
    session.commit()


def save_supplier_balance(
    *, session: Session, supplier: Supplier, balance: Decimal
) -> None:
    """写回供应商余额"""
    supplier.balance = balance
    session.add(supplier)
    session.commit()


def list_synced_sku_map(
    *, session: Session, supplier_id: uuid.UUID | str
) -> dict[str, uuid.UUID]:
    """查询供应商已同步的 SKU → 本地商品 ID 映射"""
    local_rows = session.exec(
        select(ProductSupplier).where(ProductSupplier.supplier_id == supplier_id)
    ).all()
    return {row.sku_id: row.product_id for row in local_rows if row.sku_id}


def find_matched_supplier_row(
    *, session: Session, supplier_id: uuid.UUID | str, sku_id: str
) -> ProductSupplier | None:
    """按供应商 + 上游 SKU 查询已匹配的货源记录"""
    return session.exec(
        select(ProductSupplier).where(
            ProductSupplier.supplier_id == supplier_id,
            ProductSupplier.sku_id == sku_id,
        )
    ).first()


def update_matched_product(
    *,
    session: Session,
    product_id: uuid.UUID,
    cost_price: Decimal,
    is_closed: bool,
    category_id: uuid.UUID | None,
    upstream_name: str | None = None,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """更新已同步商品的成本价与关闭下单状态，返回 (旧分类 ID, 新分类 ID)"""
    db_product = session.get(Product, product_id)
    if db_product is None:
        raise ValueError("已同步商品缺少商品记录，无法更新")
    db_pricing = session.exec(
        select(ProductPricing).where(ProductPricing.product_id == product_id)
    ).first()
    if db_pricing is None:
        raise ValueError("已同步商品缺少定价配置，无法更新成本价")
    old_category_id = db_product.category_id
    db_pricing.cost_price = cost_price
    db_product.is_closed = is_closed
    # 按商品当前定价模式维护 1.5 倍售价：固定价格模式更新固定售价，
    # 商品系数模式保持系数为默认折扣率，价格模板模式不干预
    if db_pricing.fixed_price is not None:
        db_pricing.fixed_price = calc_sync_fixed_price(cost_price=cost_price)
    elif db_pricing.item_coefficient is not None:
        db_pricing.item_coefficient = DEFAULT_DISCOUNT_RATE
    if category_id is not None and category_id != db_product.category_id:
        db_product.category_id = category_id
    db_product.sync_status = SyncStatus.SUCCESS
    db_product.synced_at = datetime.now(UTC)
    session.add(db_product)
    if upstream_name is not None:
        db_supplier = session.exec(
            select(ProductSupplier).where(ProductSupplier.product_id == product_id)
        ).first()
        if db_supplier is not None:
            db_supplier.upstream_name = upstream_name
            session.add(db_supplier)
    session.add(db_pricing)
    session.commit()
    return old_category_id, db_product.category_id


def create_synced_product(
    *,
    session: Session,
    supplier: Supplier,
    detail: UpstreamProductDetail,
    category_id: uuid.UUID | None,
    product_type: ProductType,
    min_quantity: int,
    max_quantity: int,
    stock: int,
    buy_params: list[dict[str, Any]],
) -> uuid.UUID:
    """创建上游商品对应的完整本地商品记录，返回本地商品 ID"""
    product = Product(
        name=str(detail.name or f"上游商品 {detail.upstream_id}"),
        category_id=category_id,
        image_id=None,
        source_type=SourceType.API_INTEGRATION,
        status=ProductStatus.PENDING_REVIEW,
        is_closed=detail.is_closed,
        sort=0,
        type=product_type,
        sync_status=SyncStatus.SUCCESS,
        synced_at=datetime.now(UTC),
    )
    session.add(product)
    session.flush()
    product_id = product.id

    session.add(
        ProductSupplier(
            product_id=product_id,
            supplier_id=supplier.id,
            sku_id=detail.upstream_id,
            upstream_name=str(detail.name or f"上游商品 {detail.upstream_id}"),
        )
    )
    session.add(
        ProductPricing(
            product_id=product_id,
            cost_price=detail.cost_price,
            fixed_price=calc_sync_fixed_price(cost_price=detail.cost_price),
            loss_price=Decimal("0.00"),
        )
    )
    session.add(
        ProductInventory(
            product_id=product_id,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
            purchase_step=detail.purchase_step,
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
    return product_id


def mark_product_sync_failed(*, session: Session, product_id: uuid.UUID) -> None:
    """标记本地商品的上游同步状态为异常"""
    db_product = session.get(Product, product_id)
    if db_product is None:
        return
    db_product.sync_status = SyncStatus.FAILED
    db_product.synced_at = datetime.now(UTC)
    session.add(db_product)
    session.commit()
