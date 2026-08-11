"""图片模块：分类数据访问"""

import uuid

from sqlmodel import Session, select

from app.modules.image.models import ImageCategory
from app.modules.image.schemas import ImageCategoryCreate


def get_category_by_id(
    *, session: Session, category_id: uuid.UUID
) -> ImageCategory | None:
    """按 ID 获取分类"""
    return session.get(ImageCategory, category_id)


def get_category_by_name(
    *, session: Session, name: str
) -> ImageCategory | None:
    """按 name 获取分类"""
    return session.exec(
        select(ImageCategory).where(ImageCategory.name == name)
    ).first()


def list_categories(
    *, session: Session, only_active: bool = False
) -> list[ImageCategory]:
    """获取分类列表，按 sort_order 升序排列"""
    query = select(ImageCategory)
    if only_active:
        query = query.where(ImageCategory.is_active == True)
    query = query.order_by(ImageCategory.sort_order, ImageCategory.name)
    return list(session.exec(query).all())


def list_category_options(*, session: Session) -> list[str]:
    """获取激活分类的名称列表"""
    categories = session.exec(
        select(ImageCategory)
        .where(ImageCategory.is_active == True)
        .order_by(ImageCategory.sort_order, ImageCategory.name)
    ).all()
    return [c.name for c in categories]


def create_category_record(
    *, session: Session, data: ImageCategoryCreate
) -> ImageCategory:
    """新增分类记录（不提交，由应用层控制事务）"""
    category = ImageCategory(
        name=data.name,
        description=data.description,
        sort_order=data.sort_order,
        icon=data.icon,
        image_count=0,
    )
    session.add(category)
    session.flush()
    return category


def update_category_record(
    *, session: Session, category: ImageCategory, update_data: dict
) -> ImageCategory:
    """更新分类字段（不提交，由应用层控制事务）"""
    category.sqlmodel_update(update_data)
    session.add(category)
    session.flush()
    return category


def delete_category_record(
    *, session: Session, category: ImageCategory
) -> None:
    """删除分类记录（不提交，由应用层控制事务）"""
    session.delete(category)
    session.flush()
