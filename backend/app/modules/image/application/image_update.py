"""图片模块：更新图片应用服务"""

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.image.application.category_manage import (
    sync_category_image_count,
    validate_category_name,
)
from app.modules.image.models import Image
from app.modules.image.repositories.image import update_image_record
from app.modules.image.schemas import ImageUpdate


def update_image(*, session: Session, image: Image, data: ImageUpdate) -> Image:
    """更新图片分类，分类变更时同步新旧分类计数"""
    old_category = image.category
    update_data = data.model_dump(exclude_unset=True)
    new_category = update_data.get("category")

    if new_category is not None:
        valid, msg = validate_category_name(session=session, name=new_category)
        if not valid:
            raise HTTPException(status_code=400, detail=msg)

    if update_data:
        image = update_image_record(
            session=session, db_image=image, update_data=update_data
        )
        session.commit()
        session.refresh(image)

    if old_category:
        sync_category_image_count(session=session, category_name=old_category)
    if new_category:
        sync_category_image_count(session=session, category_name=new_category)
    return image
