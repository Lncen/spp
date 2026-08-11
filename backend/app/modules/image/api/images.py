"""图片模块：图片接口层"""

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile

from app.api.deps import CurrentUser, SessionDep
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
from app.modules.image.models import Image
from app.modules.image.schemas import (
    ImagePublic,
    ImageUpdate,
    ImagesPublic,
)

router = APIRouter(prefix="/images", tags=["images"])


def _build_image_url(image: Image) -> str:
    """构建图片可访问 URL

    若配置了 STATIC_URL_BASE（如 CDN 域名）则使用之，否则用相对路径。
    相对路径在生产环境由反向代理（Nginx/Traefik）直接提供服务。
    """
    if settings.STATIC_URL_BASE:
        base = settings.STATIC_URL_BASE.rstrip("/")
        return f"{base}/uploads/{image.file_path}"
    return f"/uploads/{image.file_path}"


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

    超管可查看全部图片；普通用户可查看自己上传的图片与系统默认图片
    （即超管上传的图片）。
    """
    count, images = get_images_page(
        session=session,
        current_user=current_user,
        skip=skip,
        limit=limit,
        category=category,
    )
    return ImagesPublic(
        data=[
            ImagePublic.model_validate(img, update={"url": _build_image_url(img)})
            for img in images
        ],
        count=count,
    )


@router.get("/{id}", response_model=ImagePublic)
def read_image(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """根据 ID 获取图片元数据（普通用户可查看自己上传的或系统默认图片）"""
    image = get_accessible_image(
        session=session, current_user=current_user, image_id=id
    )
    return ImagePublic.model_validate(image, update={"url": _build_image_url(image)})


@router.post("/upload", response_model=ImagePublic)
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
    """上传图片，支持 JPEG/PNG/WebP，自动压缩（仅超级管理员）"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")

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
    return ImagePublic.model_validate(image, update={"url": _build_image_url(image)})


@router.delete("/{id}")
def delete_image(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """删除图片（同时删除磁盘文件）"""
    image = session.get(Image, id)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    if not current_user.is_superuser and (image.owner_id != current_user.id):
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
    """更新图片分类"""
    image = session.get(Image, id)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    if not current_user.is_superuser and (image.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="权限不足")

    image = update_image_service(session=session, image=image, data=data)
    return ImagePublic.model_validate(image, update={"url": _build_image_url(image)})
