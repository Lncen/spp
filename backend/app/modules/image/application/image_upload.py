"""图片模块：上传图片应用服务"""

import uuid

from sqlmodel import Session

from app.modules.image.application.category_manage import (
    sync_category_image_count,
)
from app.modules.image.infrastructure.image_storage import (
    compute_sha256,
    get_upload_path,
    process_image,
    write_storage_file,
)
from app.modules.image.models import Image
from app.modules.image.repositories.image import (
    create_image_record,
    get_image_by_hash,
    update_image_record,
)


def upload_image(
    *,
    session: Session,
    file_bytes: bytes,
    original_filename: str,
    owner_id: uuid.UUID,
    image_ext: str = ".webp",
    category: str | None = None,
) -> Image:
    """处理上传图片：去重 → 校验 → 压缩 → 保存 → 返回记录

    已存在相同 SHA256 的图片时，更新已有记录的元数据（分类、文件名）并返回。
    """
    # 1. 计算哈希，检查是否已存在
    file_hash = compute_sha256(file_bytes)
    existing = get_image_by_hash(session=session, file_hash=file_hash)
    if existing:
        return _update_existing_metadata(
            session=session,
            existing=existing,
            original_filename=original_filename,
            category=category,
        )

    # 2. Pillow 校验并处理图片
    output_bytes, width, height = process_image(
        file_bytes=file_bytes, image_ext=image_ext
    )

    # 3. 写入磁盘
    _, rel_path = get_upload_path(image_ext)
    write_storage_file(rel_path=rel_path, file_bytes=output_bytes)

    # 4. 保存数据库记录
    db_image = Image(
        owner_id=owner_id,
        file_hash=file_hash,
        filename=original_filename,
        file_size=len(output_bytes),
        width=width,
        height=height,
        file_path=rel_path,
        category=category,
    )
    create_image_record(session=session, image=db_image)
    session.commit()
    session.refresh(db_image)
    return db_image


def _update_existing_metadata(
    *,
    session: Session,
    existing: Image,
    original_filename: str,
    category: str | None,
) -> Image:
    """更新去重命中记录的元数据（分类、文件名）"""
    old_category = existing.category
    update_data = {}
    if category is not None and existing.category != category:
        update_data["category"] = category
    if existing.filename != original_filename:
        update_data["filename"] = original_filename
    if update_data:
        existing = update_image_record(
            session=session, db_image=existing, update_data=update_data
        )
        session.commit()
        session.refresh(existing)
        # 分类变更时同步新旧分类的计数
        if old_category != category:
            sync_category_image_count(session=session, category_name=old_category)
            if category is not None:
                sync_category_image_count(session=session, category_name=category)
    return existing
