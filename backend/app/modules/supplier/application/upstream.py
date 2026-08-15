"""供应商模块：上游商品查询与同步任务应用服务"""

import uuid
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.automation.infrastructure.tasks.supplier_sync import (
    dispatch_upstream_products_sync,
)
from app.modules.supplier.infrastructure.clients.base import supplier_client
from app.modules.supplier.repositories.supplier import (
    get_supplier_or_404,
    list_synced_sku_map,
)
from app.modules.supplier.schemas.upstream import UpstreamCategory


def list_upstream_products(
    *,
    session: Session,
    supplier_id: uuid.UUID,
    category_id: str | None = None,
) -> list[dict[str, Any]]:
    """获取上游商品列表，并标记是否已同步到本地"""
    supplier = get_supplier_or_404(session=session, supplier_id=supplier_id)
    with supplier_client(session=session, supplier_id=supplier.id) as client:
        items = client.query_products_list(
            page=1,
            page_size=100,
            category_id=category_id,
        )

    local_by_sku = list_synced_sku_map(
        session=session,
        supplier_id=supplier.id,
    )
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
    supplier_id: uuid.UUID,
) -> list[dict[str, str]]:
    """获取上游商品分类列表"""
    supplier = get_supplier_or_404(session=session, supplier_id=supplier_id)
    with supplier_client(session=session, supplier_id=supplier.id) as client:
        categories: list[UpstreamCategory] = client.get_categories()

    return [
        {
            "id": item.id,
            "name": item.name,
            "parent_id": str(item.parent_id or "0"),
        }
        for item in categories
    ]


def create_upstream_products_sync(
    *,
    session: Session,
    supplier_id: uuid.UUID,
    product_ids: list[str],
    category_id: uuid.UUID | None,
) -> str:
    """校验供应商并创建异步同步任务，返回任务 ID"""
    supplier = get_supplier_or_404(session=session, supplier_id=supplier_id)
    if not product_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个商品")
    return dispatch_upstream_products_sync(
        supplier_id=str(supplier.id),
        product_ids=product_ids,
        category_id=str(category_id) if category_id else None,
    )
