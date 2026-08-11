"""图片模块：分类管理应用服务"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.image.models import ImageCategory
from app.modules.image.repositories.category import (
    create_category_record,
    delete_category_record,
    get_category_by_id,
    get_category_by_name as get_category_by_name_record,
    list_categories as list_categories_record,
    list_category_options as list_category_options_record,
    update_category_record,
)
from app.modules.image.repositories.image import count_images_by_category
from app.modules.image.schemas import ImageCategoryCreate, ImageCategoryUpdate


def create_category(*, session: Session, data: ImageCategoryCreate) -> ImageCategory:
    """创建图片分类"""
    category = create_category_record(session=session, data=data)
    session.commit()
    session.refresh(category)
    return category


def update_category(
    *, session: Session, category_id: uuid.UUID, data: ImageCategoryUpdate
) -> ImageCategory | None:
    """更新图片分类，返回更新后的对象；不存在返回 None"""
    category = get_category_by_id(session=session, category_id=category_id)
    if not category:
        return None
    update_data = data.model_dump(exclude_unset=True)
    category = update_category_record(
        session=session, category=category, update_data=update_data
    )
    session.commit()
    session.refresh(category)
    return category


def delete_category(*, session: Session, category_id: uuid.UUID) -> tuple[bool, str]:
    """删除图片分类。若分类下有图片引用则拒绝删除。
    返回 (success: bool, message: str)
    """
    category = get_category_by_id(session=session, category_id=category_id)
    if not category:
        return False, "分类不存在"

    image_count = count_images_by_category(
        session=session, category_name=category.name
    )
    if image_count > 0:
        return False, f"该分类下有 {image_count} 张图片，无法删除"

    delete_category_record(session=session, category=category)
    session.commit()
    return True, "分类已删除"


def get_category(*, session: Session, category_id: uuid.UUID) -> ImageCategory | None:
    """根据 ID 获取分类"""
    return get_category_by_id(session=session, category_id=category_id)


def get_category_by_name(*, session: Session, name: str) -> ImageCategory | None:
    """根据 name 获取分类"""
    return get_category_by_name_record(session=session, name=name)


def list_categories(
    *, session: Session, only_active: bool = False
) -> list[ImageCategory]:
    """获取分类列表，按 sort_order 升序排列"""
    return list_categories_record(session=session, only_active=only_active)


def list_category_options(*, session: Session) -> list[str]:
    """获取激活分类的名称列表"""
    return list_category_options_record(session=session)


def sync_category_image_count(
    *, session: Session, category_name: str | None = None
) -> None:
    """同步指定分类（或所有分类）的 image_count 缓存值"""
    if category_name:
        category = get_category_by_name_record(session=session, name=category_name)
        categories = [category] if category else []
    else:
        categories = list_categories_record(session=session)

    for cat in categories:
        cat.image_count = count_images_by_category(
            session=session, category_name=cat.name
        )
        session.add(cat)

    if categories:
        session.commit()


def validate_category_name(*, session: Session, name: str) -> tuple[bool, str]:
    """验证分类名称是否可用（存在且激活）
    返回 (is_valid: bool, message: str)
    """
    if not name:
        return False, "分类名称不能为空"
    category = get_category_by_name_record(session=session, name=name)
    if not category:
        return False, f"分类 '{name}' 不存在"
    if not category.is_active:
        return False, f"分类 '{name}' 已禁用"
    return True, ""
