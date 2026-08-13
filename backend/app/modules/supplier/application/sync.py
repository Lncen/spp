"""供应商模块：上游商品同步应用服务"""

import uuid
from typing import Any

from sqlmodel import Session

from app.modules.product.category.models import ProductCategory
from app.modules.product.category.service import sync_category_product_count
from app.modules.product.constants import ProductType
from app.modules.supplier.domain.mapping import (
    build_buy_params,
    normalize_quantity_limits,
)
from app.modules.supplier.models import Supplier
from app.modules.supplier.repositories.supplier import (
    create_synced_product,
    find_matched_supplier_row,
    update_matched_product,
)
from app.modules.supplier.schemas.upstream import UpstreamProductDetail


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

    matched = find_matched_supplier_row(
        session=session,
        supplier_id=supplier.id,
        sku_id=upstream_id,
    )
    if matched:
        old_category_id, new_category_id = update_matched_product(
            session=session,
            product_id=matched.product_id,
            cost_price=cost_price,
            category_id=category_id,
            upstream_name=str(detail.name or f"上游商品 {detail.upstream_id}"),
        )
        if category_id is not None and old_category_id != category_id:
            if old_category_id is not None:
                sync_category_product_count(
                    session=session,
                    category_id=old_category_id,
                )
            sync_category_product_count(session=session, category_id=category_id)
        return "updated", matched.product_id

    min_quantity, max_quantity = normalize_quantity_limits(
        min_quantity=detail.min_quantity,
        max_quantity=detail.max_quantity,
    )
    stock = max(detail.stock, -1)
    product_type = (
        ProductType.CARD if detail.is_card_code else ProductType.NORMAL_PRODUCT
    )
    buy_params = build_buy_params(detail.buy_params)

    product_id = create_synced_product(
        session=session,
        supplier=supplier,
        detail=detail,
        category_id=category_id,
        product_type=product_type,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
        stock=stock,
        buy_params=buy_params,
    )
    if category_id is not None:
        sync_category_product_count(session=session, category_id=category_id)
    return "created", product_id
