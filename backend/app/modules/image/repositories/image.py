"""图片模块：图片数据访问"""

import uuid
from typing import Any

from sqlmodel import Session, col, func, select

from app.modules.image.models import Image
from app.modules.user.models import User


def count_images(
    *,
    session: Session,
    owner_ids: list[uuid.UUID] | None = None,
    category: str | None = None,
) -> int:
    """统计图片数量；owner_ids 为 None 时不限归属"""
    statement = select(func.count()).select_from(Image)
    if owner_ids is not None:
        statement = statement.where(Image.owner_id.in_(owner_ids))
    if category:
        statement = statement.where(Image.category == category)
    return session.exec(statement).one()


def list_images(
    *,
    session: Session,
    owner_ids: list[uuid.UUID] | None = None,
    skip: int = 0,
    limit: int = 100,
    category: str | None = None,
) -> list[Image]:
    """按创建时间倒序分页查询图片；owner_ids 为 None 时不限归属"""
    statement = select(Image)
    if owner_ids is not None:
        statement = statement.where(Image.owner_id.in_(owner_ids))
    if category:
        statement = statement.where(Image.category == category)
    statement = (
        statement.order_by(col(Image.created_at).desc()).offset(skip).limit(limit)
    )
    return list(session.exec(statement).all())


def get_image_by_id(*, session: Session, image_id: uuid.UUID) -> Image | None:
    """按 ID 获取图片"""
    return session.get(Image, image_id)


def get_image_by_hash(*, session: Session, file_hash: str) -> Image | None:
    """按文件哈希获取图片（去重用）"""
    return session.exec(
        select(Image).where(Image.file_hash == file_hash)
    ).first()


def get_superuser_ids(*, session: Session) -> list[uuid.UUID]:
    """获取所有超管用户 ID（系统默认图片归属）"""
    return list(
        session.exec(select(User.id).where(User.is_superuser == True)).all()
    )


def create_image_record(*, session: Session, image: Image) -> Image:
    """新增图片记录（不提交，由应用层控制事务）"""
    session.add(image)
    session.flush()
    return image


def update_image_record(
    *, session: Session, db_image: Image, update_data: dict[str, Any]
) -> Image:
    """更新图片字段（不提交，由应用层控制事务）"""
    db_image.sqlmodel_update(update_data)
    session.add(db_image)
    session.flush()
    return db_image


def delete_image_record(*, session: Session, db_image: Image) -> None:
    """删除图片记录（不提交，由应用层控制事务）"""
    session.delete(db_image)
    session.flush()


def count_images_by_category(*, session: Session, category_name: str) -> int:
    """统计指定分类下的图片数量（仅统计激活图片）"""
    return session.exec(
        select(func.count())
        .select_from(Image)
        .where(
            Image.category == category_name,
            Image.is_active == True,
        )
    ).one()
