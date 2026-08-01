"""商品模块：商品分类路由层"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import select

from app.api.deps import SessionDep, get_current_active_superuser
from app.common.models import Message
from app.core.config import settings
from app.modules.image.models import Image
from app.modules.product.category.models import ProductCategory
from app.modules.product.category.schemas import (
    ProductCategoriesPublic,
    ProductCategoryCreate,
    ProductCategoryPublic,
    ProductCategoryTreePublic,
    ProductCategoryUpdate,
)
from app.modules.product.category.service import (
    create_category as create_category_service,
)
from app.modules.product.category.service import (
    delete_category as delete_category_service,
)
from app.modules.product.category.service import (
    get_category as get_category_service,
)
from app.modules.product.category.service import list_categories
from app.modules.product.category.service import (
    update_category as update_category_service,
)

category_router = APIRouter(
    prefix="/product-categories",
    tags=["product-categories"],
)


def _build_image_url(image: Image) -> str:
    """构建图片访问 URL"""
    if settings.STATIC_URL_BASE:
        base = settings.STATIC_URL_BASE.rstrip("/")
        return f"{base}/uploads/{image.file_path}"
    return f"/uploads/{image.file_path}"


def _category_to_public(
    category: ProductCategory, icon_url: str | None
) -> ProductCategoryPublic:
    """将 ProductCategory 转换为 ProductCategoryPublic"""
    return ProductCategoryPublic(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        icon_id=category.icon_id,
        icon_url=icon_url,
        product_count=category.product_count,
        sort=category.sort,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def _categories_to_public(
    session: SessionDep, categories: list[ProductCategory]
) -> list[ProductCategoryPublic]:
    """批量将分类转换为响应模型，并解析分类图标 URL"""
    icon_ids = {category.icon_id for category in categories if category.icon_id}
    images: dict[uuid.UUID, Image] = {}
    if icon_ids:
        rows = session.exec(select(Image).where(Image.id.in_(icon_ids))).all()
        images = {image.id: image for image in rows}
    return [
        _category_to_public(
            category,
            _build_image_url(images[category.icon_id])
            if category.icon_id in images
            else None,
        )
        for category in categories
    ]


def _categories_to_tree(
    categories: list[ProductCategoryPublic],
) -> list[ProductCategoryTreePublic]:
    """按 parent_id 组装商品分类树，保持列表排序"""
    nodes = [
        ProductCategoryTreePublic.model_validate(category.model_dump())
        for category in categories
    ]
    nodes_by_id = {node.id: node for node in nodes}
    roots: list[ProductCategoryTreePublic] = []
    for node in nodes:
        parent = nodes_by_id.get(node.parent_id) if node.parent_id else None
        if parent:
            parent.children.append(node)
        else:
            roots.append(node)
    return roots


@category_router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProductCategoriesPublic,
)
def read_product_categories(session: SessionDep) -> Any:
    """获取商品分类列表（仅超管）"""
    categories = list_categories(session=session)
    return ProductCategoriesPublic(
        data=_categories_to_tree(_categories_to_public(session, categories)),
        count=len(categories),
    )


@category_router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProductCategoryPublic,
)
def create_product_category(
    *, session: SessionDep, category_in: ProductCategoryCreate
) -> Any:
    """创建商品分类（仅超管）"""
    category = create_category_service(session=session, category_in=category_in)
    return _categories_to_public(session, [category])[0]


@category_router.get(
    "/{category_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProductCategoryPublic,
)
def read_product_category(session: SessionDep, category_id: uuid.UUID) -> Any:
    """根据 ID 获取商品分类（仅超管）"""
    category = get_category_service(session=session, category_id=category_id)
    return _categories_to_public(session, [category])[0]


@category_router.put(
    "/{category_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProductCategoryPublic,
)
def update_product_category(
    *,
    session: SessionDep,
    category_id: uuid.UUID,
    category_in: ProductCategoryUpdate,
) -> Any:
    """更新商品分类（仅超管）"""
    category = update_category_service(
        session=session,
        category_id=category_id,
        category_in=category_in,
    )
    return _categories_to_public(session, [category])[0]


@category_router.delete(
    "/{category_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_product_category(session: SessionDep, category_id: uuid.UUID) -> Message:
    """删除商品分类（仅超管，有子分类或商品时拒绝）"""
    delete_category_service(session=session, category_id=category_id)
    return Message(message="商品分类已删除")
