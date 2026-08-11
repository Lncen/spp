"""图片模块：图片查询应用服务"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.image.domain import can_access_image
from app.modules.image.models import Image
from app.modules.image.repositories.image import (
    count_images,
    get_image_by_id,
    get_superuser_ids,
    list_images,
)
from app.modules.user.models import User


def get_images_page(
    *,
    session: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    category: str | None = None,
) -> tuple[int, list[Image]]:
    """分页查询图片列表，返回 (总数, 列表)

    超管可见全部图片；普通用户可见自己上传的与系统默认（超管上传）图片。
    """
    if current_user.is_superuser:
        owner_ids = None
    else:
        owner_ids = [current_user.id, *get_superuser_ids(session=session)]
    count = count_images(
        session=session, owner_ids=owner_ids, category=category
    )
    images = list_images(
        session=session,
        owner_ids=owner_ids,
        skip=skip,
        limit=limit,
        category=category,
    )
    return count, images


def get_accessible_image(
    *, session: Session, current_user: User, image_id: uuid.UUID
) -> Image:
    """按 ID 获取图片并做可见性校验，不可见时抛出 403"""
    image = get_image_by_id(session=session, image_id=image_id)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    owner_is_superuser = image.owner.is_superuser if image.owner else False
    if not can_access_image(
        image_owner_id=image.owner_id,
        owner_is_superuser=owner_is_superuser,
        user_id=current_user.id,
        user_is_superuser=current_user.is_superuser,
    ):
        raise HTTPException(status_code=403, detail="权限不足")
    return image
