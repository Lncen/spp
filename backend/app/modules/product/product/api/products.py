"""商品模块：商品路由层。函数名保持不变以保证 OpenAPI operationId 兼容性"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, require_permission
from app.common.models import Message
from app.modules.product.constants import (
    ProductStatus,
    ProductType,
    SourceType,
)
from app.modules.product.product.application.create import (
    create_product as create_product_service,
)
from app.modules.product.product.application.delete import (
    delete_product as delete_product_service,
)
from app.modules.product.product.application.query import (
    get_product as get_product_service,
)
from app.modules.product.product.application.query import (
    list_products,
    to_products_public,
)
from app.modules.product.product.application.update import (
    update_product as update_product_service,
)
from app.modules.product.product.schemas import (
    ProductCreate,
    ProductPublic,
    ProductsPublic,
    ProductUpdate,
)

product_router = APIRouter(prefix="/products", tags=["products"])


@product_router.get(
    "/",
    dependencies=[Depends(require_permission("product:view"))],
    response_model=ProductsPublic,
)
def read_products(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    category_id: uuid.UUID | None = None,
    status: ProductStatus | None = None,
    source_type: SourceType | None = None,
    product_type: ProductType | None = None,
    is_closed: bool | None = None,
    name: str | None = None,
) -> Any:
    """分页查询商品"""
    return list_products(
        session=session,
        skip=skip,
        limit=limit,
        category_id=category_id,
        status=status,
        source_type=source_type,
        product_type=product_type,
        is_closed=is_closed,
        name=name,
    )


@product_router.post(
    "/",
    dependencies=[Depends(require_permission("product:create"))],
    response_model=ProductPublic,
)
def create_product(*, session: SessionDep, product_in: ProductCreate) -> Any:
    """创建商品及其关联配置"""
    product = create_product_service(session=session, product_in=product_in)
    return to_products_public(session, [product])[0]


@product_router.get(
    "/{product_id}",
    dependencies=[Depends(require_permission("product:view"))],
    response_model=ProductPublic,
)
def read_product(session: SessionDep, product_id: uuid.UUID) -> Any:
    """根据 ID 获取商品"""
    return get_product_service(session=session, product_id=product_id)


@product_router.put(
    "/{product_id}",
    dependencies=[Depends(require_permission("product:update"))],
    response_model=ProductPublic,
)
def update_product(
    *,
    session: SessionDep,
    product_id: uuid.UUID,
    product_in: ProductUpdate,
) -> Any:
    """更新商品及其关联配置"""
    product = update_product_service(
        session=session,
        product_id=product_id,
        product_in=product_in,
    )
    return to_products_public(session, [product])[0]


@product_router.delete(
    "/{product_id}",
    dependencies=[Depends(require_permission("product:delete"))],
    response_model=Message,
)
def delete_product(session: SessionDep, product_id: uuid.UUID) -> Message:
    """删除商品及其关联配置"""
    delete_product_service(session=session, product_id=product_id)
    return Message(message="商品已删除")
