"""商品模块：商品收藏业务逻辑层"""

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.modules.product.favorite.models import ProductFavorite
from app.modules.product.product.models import Product


def get_favorite(
    *, session: Session, user_id: uuid.UUID, product_id: uuid.UUID
) -> ProductFavorite | None:
    """查询用户对指定商品的收藏记录"""
    return session.exec(
        select(ProductFavorite).where(
            ProductFavorite.user_id == user_id,
            ProductFavorite.product_id == product_id,
        )
    ).first()


def is_favorited(
    *, session: Session, user_id: uuid.UUID, product_id: uuid.UUID
) -> bool:
    """判断用户是否已收藏指定商品"""
    return (
        get_favorite(session=session, user_id=user_id, product_id=product_id)
        is not None
    )


def add_favorite(
    *, session: Session, user_id: uuid.UUID, product_id: uuid.UUID
) -> ProductFavorite:
    """收藏商品，重复收藏与并发提交都保持幂等"""
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    db_favorite = ProductFavorite(user_id=user_id, product_id=product_id)
    session.add(db_favorite)
    try:
        session.commit()
    except IntegrityError:
        # 并发下唯一约束兜底：回滚后复用已存在的收藏记录
        session.rollback()
        existing = get_favorite(session=session, user_id=user_id, product_id=product_id)
        if existing is None:
            raise
        return existing
    session.refresh(db_favorite)
    return db_favorite


def remove_favorite(
    *, session: Session, user_id: uuid.UUID, product_id: uuid.UUID
) -> None:
    """取消收藏，未收藏时保持幂等"""
    db_favorite = get_favorite(session=session, user_id=user_id, product_id=product_id)
    if db_favorite is None:
        return
    session.delete(db_favorite)
    session.commit()


def list_favorites(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int,
    limit: int,
) -> tuple[list[ProductFavorite], int]:
    """分页查询用户收藏，按收藏时间倒序"""
    conditions = [ProductFavorite.user_id == user_id]
    count = session.exec(
        select(func.count()).select_from(ProductFavorite).where(*conditions)
    ).one()
    statement = (
        select(ProductFavorite)
        .where(*conditions)
        .order_by(col(ProductFavorite.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all()), count
