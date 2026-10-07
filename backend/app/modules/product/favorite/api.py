"""商品模块：商品收藏路由层

收藏是登录用户的自助能力，与 ``/orders/me`` 一致，仅要求登录态，不额外声明权限码。
"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import Session

from app.api.deps import CurrentUser, SessionDep
from app.common.models import Message
from app.modules.product.catalog import load_product_displays
from app.modules.product.favorite.models import ProductFavorite
from app.modules.product.favorite.schemas import (
    ProductFavoriteCreate,
    ProductFavoritePublic,
    ProductFavoritesPublic,
    ProductFavoriteStatusPublic,
)
from app.modules.product.favorite.service import (
    add_favorite,
    is_favorited,
    list_favorites,
    remove_favorite,
)

favorite_router = APIRouter(prefix="/product-favorites", tags=["product-favorites"])


def to_favorites_public(
    session: Session, favorites: list[ProductFavorite]
) -> list[ProductFavoritePublic]:
    """批量组装收藏响应，按商品 ID 批量加载商品与主图，避免 N+1"""
    displays = load_product_displays(
        session=session,
        product_ids={favorite.product_id for favorite in favorites},
    )

    data: list[ProductFavoritePublic] = []
    for favorite in favorites:
        display = displays.get(favorite.product_id)
        if display is None:
            continue
        product = display.product
        data.append(
            ProductFavoritePublic(
                id=favorite.id,
                product_id=product.id,
                product_name=product.name,
                image_url=display.image_url,
                category_id=product.category_id,
                status=product.status,
                is_closed=product.is_closed,
                created_at=favorite.created_at,
            )
        )
    return data


@favorite_router.get("/me", response_model=ProductFavoritesPublic)
def read_my_favorites(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """查看当前用户的商品收藏列表"""
    favorites, count = list_favorites(
        session=session,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return ProductFavoritesPublic(
        data=to_favorites_public(session, favorites),
        count=count,
    )


@favorite_router.post("/me", response_model=ProductFavoritePublic)
def create_my_favorite(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: ProductFavoriteCreate,
) -> Any:
    """收藏商品，重复收藏保持幂等"""
    favorite = add_favorite(
        session=session,
        user_id=current_user.id,
        product_id=body.product_id,
    )
    data = to_favorites_public(session, [favorite])
    if not data:
        # 极端并发下商品被同时删除：收藏记录随商品级联删除，按不存在处理
        raise HTTPException(status_code=404, detail="商品不存在")
    return data[0]


@favorite_router.get("/me/{product_id}", response_model=ProductFavoriteStatusPublic)
def read_my_favorite_status(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    product_id: uuid.UUID,
) -> Any:
    """查看当前用户是否已收藏指定商品"""
    return ProductFavoriteStatusPublic(
        product_id=product_id,
        favorited=is_favorited(
            session=session,
            user_id=current_user.id,
            product_id=product_id,
        ),
    )


@favorite_router.delete("/me/{product_id}", response_model=Message)
def delete_my_favorite(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    product_id: uuid.UUID,
) -> Message:
    """取消收藏，未收藏时保持幂等"""
    remove_favorite(
        session=session,
        user_id=current_user.id,
        product_id=product_id,
    )
    return Message(message="已取消收藏")
