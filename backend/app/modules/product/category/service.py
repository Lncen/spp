"""商品模块：商品分类业务逻辑层"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.modules.image.models import Image
from app.modules.product.category.models import ProductCategory
from app.modules.product.category.schemas import (
    ProductCategoryCreate,
    ProductCategoryUpdate,
)
from app.modules.product.product.models import Product


def _check_category_name_unique(
    *,
    session: Session,
    name: str,
    parent_id: uuid.UUID | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """同一父级下分类名称唯一"""
    db_category = session.exec(
        select(ProductCategory).where(
            ProductCategory.name == name,
            ProductCategory.parent_id == parent_id,
        )
    ).first()
    if db_category and (exclude_id is None or db_category.id != exclude_id):
        raise HTTPException(status_code=400, detail="同级分类名称已存在")


def _validate_category_parent(
    *,
    session: Session,
    category_id: uuid.UUID | None,
    parent_id: uuid.UUID | None,
) -> None:
    """校验上级分类存在且不会形成循环"""
    if parent_id is None:
        return
    if parent_id == category_id:
        raise HTTPException(status_code=400, detail="分类不能将自身设为上级分类")
    parent = session.get(ProductCategory, parent_id)
    if not parent:
        raise HTTPException(status_code=400, detail="上级分类不存在")
    current = parent
    while current.parent_id is not None:
        current = session.get(ProductCategory, current.parent_id)
        if current is None:
            break
        if current.id == category_id:
            raise HTTPException(
                status_code=400,
                detail="不能将分类移动到自己的下级分类下",
            )


def _validate_category_icon(*, session: Session, icon_id: uuid.UUID | None) -> None:
    """校验分类图标存在"""
    if icon_id is not None and session.get(Image, icon_id) is None:
        raise HTTPException(status_code=400, detail="分类图标不存在")


def sync_category_product_count(
    *, session: Session, category_id: uuid.UUID | None
) -> None:
    """同步分类下的有效商品数量缓存"""
    if category_id is None:
        return
    count = session.exec(
        select(func.count())
        .select_from(Product)
        .where(
            Product.category_id == category_id,
            Product.is_active.is_(True),
        )
    ).one()
    db_category = session.get(ProductCategory, category_id)
    if db_category:
        db_category.product_count = count
        session.add(db_category)
        session.commit()


def get_category(*, session: Session, category_id: uuid.UUID) -> ProductCategory:
    """根据 ID 获取商品分类"""
    db_category = session.get(ProductCategory, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="分类不存在")
    return db_category


def list_categories(*, session: Session) -> list[ProductCategory]:
    """获取商品分类列表，按 sort 升序"""
    statement = select(ProductCategory).order_by(
        col(ProductCategory.sort).asc(),
        col(ProductCategory.created_at).asc(),
    )
    return session.exec(statement).all()


def create_category(
    *,
    session: Session,
    category_in: ProductCategoryCreate,
) -> ProductCategory:
    """创建商品分类"""
    _check_category_name_unique(
        session=session,
        name=category_in.name,
        parent_id=category_in.parent_id,
    )
    _validate_category_parent(
        session=session,
        category_id=None,
        parent_id=category_in.parent_id,
    )
    _validate_category_icon(session=session, icon_id=category_in.icon_id)
    db_category = ProductCategory.model_validate(category_in)
    session.add(db_category)
    session.commit()
    session.refresh(db_category)
    return db_category


def update_category(
    *,
    session: Session,
    category_id: uuid.UUID,
    category_in: ProductCategoryUpdate,
) -> ProductCategory:
    """更新商品分类"""
    db_category = get_category(session=session, category_id=category_id)
    update_dict = category_in.model_dump(exclude_unset=True)

    if "name" in update_dict or "parent_id" in update_dict:
        _check_category_name_unique(
            session=session,
            name=update_dict.get("name", db_category.name),
            parent_id=update_dict.get("parent_id", db_category.parent_id),
            exclude_id=category_id,
        )
    if "parent_id" in update_dict:
        _validate_category_parent(
            session=session,
            category_id=category_id,
            parent_id=update_dict["parent_id"],
        )
    if "icon_id" in update_dict:
        _validate_category_icon(session=session, icon_id=update_dict["icon_id"])

    db_category.sqlmodel_update(update_dict)
    session.add(db_category)
    session.commit()
    session.refresh(db_category)
    sync_category_product_count(session=session, category_id=category_id)
    return db_category


def delete_category(*, session: Session, category_id: uuid.UUID) -> None:
    """删除商品分类，有子分类或商品时拒绝"""
    get_category(session=session, category_id=category_id)
    child_count = session.exec(
        select(func.count())
        .select_from(ProductCategory)
        .where(ProductCategory.parent_id == category_id)
    ).one()
    if child_count:
        raise HTTPException(status_code=400, detail="请先删除子分类")
    product_count = session.exec(
        select(func.count())
        .select_from(Product)
        .where(Product.category_id == category_id)
    ).one()
    if product_count:
        raise HTTPException(status_code=400, detail="请先删除分类下的商品")
    db_category = session.get(ProductCategory, category_id)
    session.delete(db_category)
    session.commit()
