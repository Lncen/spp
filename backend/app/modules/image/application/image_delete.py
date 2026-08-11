"""图片模块：删除图片应用服务"""

from sqlmodel import Session

from app.modules.image.application.category_manage import (
    sync_category_image_count,
)
from app.modules.image.infrastructure.image_storage import delete_storage_file
from app.modules.image.models import Image
from app.modules.image.repositories.image import delete_image_record


def delete_image(*, session: Session, image: Image) -> None:
    """删除图片（同时删除磁盘文件并同步分类计数）"""
    category_name = image.category
    delete_storage_file(image.file_path)
    delete_image_record(session=session, db_image=image)
    session.commit()
    if category_name:
        sync_category_image_count(session=session, category_name=category_name)
