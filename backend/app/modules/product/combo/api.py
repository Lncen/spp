"""商品模块：用户组合路由层

组合是登录用户的自助能力，与 ``/orders/me`` 一致，仅要求登录态，不额外声明权限码。
组合本身不创建订单：下单时由前端按组合明细拼 ``POST /orders/preview`` 与 ``POST /orders/``。
"""

import uuid
from typing import Any

from fastapi import APIRouter
from sqlmodel import Session

from app.api.deps import CurrentUser, SessionDep
from app.common.models import Message
from app.modules.product.catalog import load_product_displays
from app.modules.product.combo.models import ProductCombo, ProductComboItem
from app.modules.product.combo.schemas import (
    ProductComboCreate,
    ProductComboItemPublic,
    ProductComboListItem,
    ProductComboPublic,
    ProductCombosPublic,
    ProductComboUpdate,
)
from app.modules.product.combo.service import (
    create_combo,
    delete_combo,
    get_combo,
    list_combo_items,
    list_combos,
    update_combo,
)

combo_router = APIRouter(prefix="/product-combos", tags=["product-combos"])


def to_combo_items_public(
    session: Session, items: list[ProductComboItem]
) -> list[ProductComboItemPublic]:
    """组装组合明细响应，仅返回用户可见的商品展示字段"""
    displays = load_product_displays(
        session=session,
        product_ids={item.product_id for item in items},
    )
    data: list[ProductComboItemPublic] = []
    for item in items:
        display = displays.get(item.product_id)
        if display is None:
            continue
        data.append(
            ProductComboItemPublic(
                id=item.id,
                product_id=display.product.id,
                product_name=display.product.name,
                image_url=display.image_url,
                mode=item.mode,
                quantity=item.quantity,
                min_quantity=item.min_quantity,
                max_quantity=item.max_quantity,
                sort=item.sort,
                status=display.product.status,
                is_closed=display.product.is_closed,
            )
        )
    return data


def to_combo_public(*, session: Session, combo: ProductCombo) -> ProductComboPublic:
    """组装组合详情响应（含明细）"""
    items = list_combo_items(session=session, combo_ids=[combo.id]).get(combo.id, [])
    return ProductComboPublic(
        id=combo.id,
        name=combo.name,
        remark=combo.remark,
        item_count=len(items),
        created_at=combo.created_at,
        updated_at=combo.updated_at,
        items=to_combo_items_public(session=session, items=items),
    )


@combo_router.get("/me", response_model=ProductCombosPublic)
def read_my_combos(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """查看当前用户的组合列表"""
    combos, count = list_combos(
        session=session,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    items_map = list_combo_items(
        session=session,
        combo_ids=[combo.id for combo in combos],
    )
    return ProductCombosPublic(
        data=[
            ProductComboListItem(
                id=combo.id,
                name=combo.name,
                remark=combo.remark,
                item_count=len(items_map.get(combo.id, [])),
                created_at=combo.created_at,
                updated_at=combo.updated_at,
            )
            for combo in combos
        ],
        count=count,
    )


@combo_router.post("/me", response_model=ProductComboPublic)
def create_my_combo(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: ProductComboCreate,
) -> Any:
    """保存组合（名称 + 商品明细）"""
    combo = create_combo(
        session=session,
        user_id=current_user.id,
        combo_in=body,
    )
    return to_combo_public(session=session, combo=combo)


@combo_router.get("/me/{combo_id}", response_model=ProductComboPublic)
def read_my_combo(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    combo_id: uuid.UUID,
) -> Any:
    """查看组合详情"""
    combo = get_combo(
        session=session,
        user_id=current_user.id,
        combo_id=combo_id,
    )
    return to_combo_public(session=session, combo=combo)


@combo_router.put("/me/{combo_id}", response_model=ProductComboPublic)
def update_my_combo(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    combo_id: uuid.UUID,
    body: ProductComboUpdate,
) -> Any:
    """更新组合：名称/备注部分更新，明细传入时整体替换"""
    combo = update_combo(
        session=session,
        user_id=current_user.id,
        combo_id=combo_id,
        combo_in=body,
    )
    return to_combo_public(session=session, combo=combo)


@combo_router.delete("/me/{combo_id}", response_model=Message)
def delete_my_combo(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    combo_id: uuid.UUID,
) -> Message:
    """删除组合及其明细"""
    delete_combo(
        session=session,
        user_id=current_user.id,
        combo_id=combo_id,
    )
    return Message(message="组合已删除")
