"""图片模块：图片接口层"""

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.common.models import Message
from app.core.config import settings
from app.modules.image.application.category_manage import (
    sync_category_image_count,
    validate_category_name,
)
from app.modules.image.application.image_delete import (
    delete_image as delete_image_service,
)
from app.modules.image.application.image_query import (
    get_accessible_image,
    get_images_page,
)
from app.modules.image.application.image_update import (
    update_image as update_image_service,
)
from app.modules.image.application.image_upload import (
    upload_image as upload_image_service,
)
from app.modules.image.infrastructure.image_storage import build_image_url
from app.modules.image.models import Image
from app.modules.image.schemas import (
    ImagePublic,
    ImageUpdate,
    ImagesPublic,
)

router = APIRouter(prefix="/images", tags=["images"])

# 图片库权限码：模块导入期校验，供「持有权限或资源归属本人」的接口判定
IMAGE_VIEW = require_permission("image:view")
IMAGE_UPDATE = require_permission("image:update")
IMAGE_DELETE = require_permission("image:delete")


@router.get("/", response_model=ImagesPublic)
def read_images(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    category: str | None = Query(
        default=None,
        description="按分类筛选：avatar, product, product_detail",
    ),
) -> Any:
    """获取图片列表

    持有 `image:view` 可查看全部图片；否则仅可查看自己上传的图片与
    系统默认图片（即超管上传的图片）。
    """
    count, images = get_images_page(
        session=session,
        current_user=current_user,
        can_view_all=IMAGE_VIEW.check(
            session=session, current_user=current_user
        ),
        skip=skip,
        limit=limit,
        category=category,
    )
    return ImagesPublic(
        data=[
            ImagePublic.model_validate(
                img, update={"url": build_image_url(img.file_path)}
            )
            for img in images
        ],
        count=count,
    )


@router.get("/{id}", response_model=ImagePublic)
def read_image(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """根据 ID 获取图片元数据（持有 `image:view` 可查看全部，否则仅本人与系统默认图片）"""
    image = get_accessible_image(
        session=session,
        current_user=current_user,
        image_id=id,
        can_view_all=IMAGE_VIEW.check(session=session, current_user=current_user),
    )
    return ImagePublic.model_validate(
        image, update={"url": build_image_url(image.file_path)}
    )


@router.post(
    "/upload",
    dependencies=[Depends(require_permission("image:upload"))],
    response_model=ImagePublic,
)
async def upload_image(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile,
    category: str | None = Query(
        default=None,
        description="图片分类：avatar, product, product_detail",
    ),
) -> Any:
    """上传图片，支持 JPEG/PNG/WebP，自动压缩（需 `image:upload`）"""
    # 验证分类（DB 驱动）
    if category:
        valid, msg = validate_category_name(session=session, name=category)
        if not valid:
            raise HTTPException(status_code=400, detail=msg)

    # 验证扩展名
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="不支持的图片格式，仅允许 JPEG/PNG/WebP"
        )

    # 读取文件内容
    file_bytes = await file.read()

    # 验证大小
    actual_size = len(file_bytes)
    if actual_size > settings.IMAGE_MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制（最大 {settings.IMAGE_MAX_SIZE // 1024 // 1024}MB）",
        )

    # 检查是否为空文件
    if actual_size == 0:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    image = upload_image_service(
        session=session,
        file_bytes=file_bytes,
        original_filename=file.filename or "unknown",
        image_ext=ext,
        owner_id=current_user.id,
        category=category,
    )
    # 同步分类计数
    if category:
        sync_category_image_count(session=session, category_name=category)
    return ImagePublic.model_validate(
        image, update={"url": build_image_url(image.file_path)}
    )


@router.delete("/{id}")
def delete_image(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """删除图片（同时删除磁盘文件；需本人上传或持有 `image:delete`）"""
    image = session.get(Image, id)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    if image.owner_id != current_user.id and not IMAGE_DELETE.check(
        session=session, current_user=current_user
    ):
        raise HTTPException(status_code=403, detail="权限不足")

    delete_image_service(session=session, image=image)
    return Message(message="图片已删除")


@router.patch("/{id}", response_model=ImagePublic)
def update_image(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    data: ImageUpdate,
) -> Any:
    """更新图片分类（需本人上传或持有 `image:update`）"""
    image = session.get(Image, id)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    if image.owner_id != current_user.id and not IMAGE_UPDATE.check(
        session=session, current_user=current_user
    ):
        raise HTTPException(status_code=403, detail="权限不足")

    image = update_image_service(session=session, image=image, data=data)
    return ImagePublic.model_validate(
        image, update={"url": build_image_url(image.file_path)}
    )
