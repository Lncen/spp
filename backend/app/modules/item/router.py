"""物品模块：路由层。函数名保持不变以保证 OpenAPI operationId 兼容性"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.common.models import Message
from app.core.config import settings
from app.modules.image.models import Image
from app.modules.item.models import Item
from app.modules.item.schemas import ItemCreate, ItemPublic, ItemsPublic, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


def _resolve_image_url(session: SessionDep, image_id: uuid.UUID | None) -> str | None:
    """根据 image_id 解析完整图片 URL"""
    if not image_id:
        return None
    image = session.get(Image, image_id)
    if not image:
        return None
    if settings.STATIC_URL_BASE:
        base = settings.STATIC_URL_BASE.rstrip("/")
        return f"{base}/{image.file_path}"
    return f"/uploads/{image.file_path}"


def _items_to_public(items: list[Item], session: SessionDep) -> list[ItemPublic]:
    """将 Item 列表转换为 ItemPublic（含 image_url）"""
    result = []
    for item in items:
        image_url = _resolve_image_url(session, item.image_id)
        result.append(ItemPublic.model_validate(item, update={"image_url": image_url}))
    return result


def _item_to_public(item: Item, session: SessionDep) -> ItemPublic:
    """将单个 Item 转换为 ItemPublic（含 image_url）"""
    image_url = _resolve_image_url(session, item.image_id)
    return ItemPublic.model_validate(item, update={"image_url": image_url})


@router.get("/", response_model=ItemsPublic)
def read_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """获取物品列表"""
    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Item)
        count = session.exec(count_statement).one()
        statement = (
            select(Item).order_by(col(Item.created_at).desc()).offset(skip).limit(limit)
        )
        items = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Item)
            .where(Item.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Item)
            .where(Item.owner_id == current_user.id)
            .order_by(col(Item.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        items = session.exec(statement).all()

    return ItemsPublic(
        data=_items_to_public(items, session),
        count=count,
    )


@router.get("/{id}", response_model=ItemPublic)
def read_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """根据 ID 获取物品"""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="权限不足")
    return _item_to_public(item, session)


@router.post("/", response_model=ItemPublic)
def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    """创建新物品"""
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return _item_to_public(item, session)


@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """更新物品（支持设置/取消配图）"""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="权限不足")

    update_dict = item_in.model_dump(exclude_unset=True)

    # 如果 image_id 被设置，校验图片存在且属于当前用户
    if "image_id" in update_dict:
        new_image_id = update_dict["image_id"]
        if new_image_id is not None:
            image = session.get(Image, new_image_id)
            if not image:
                raise HTTPException(status_code=404, detail="图片不存在")
            if not current_user.is_superuser and (image.owner_id != current_user.id):
                raise HTTPException(status_code=403, detail="无权使用该图片")

    item.sqlmodel_update(update_dict)
    session.add(item)
    session.commit()
    session.refresh(item)
    return _item_to_public(item, session)


@router.delete("/{id}")
def delete_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """删除物品"""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="权限不足")
    session.delete(item)
    session.commit()
    return Message(message="物品已删除")
