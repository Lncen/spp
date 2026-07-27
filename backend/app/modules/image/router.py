"""图片模块：路由层"""

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.common.models import Message
from app.core.config import settings
from app.modules.image.models import Image
from app.modules.image.schemas import ImagePublic, ImagesPublic
from app.modules.image.service import process_and_save_image

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
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """获取当前用户的图片列表"""
    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Image)
        count = session.exec(count_statement).one()
        statement = (
            select(Image)
            .order_by(col(Image.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        images = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Image)
            .where(Image.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Image)
            .where(Image.owner_id == current_user.id)
            .order_by(col(Image.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        images = session.exec(statement).all()

    return ImagesPublic(
        data=[
            ImagePublic.model_validate(img, update={"url": _build_image_url(img)})
            for img in images
        ],
        count=count,
    )


@router.get("/{id}", response_model=ImagePublic)
def read_image(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """根据 ID 获取图片元数据"""
    image = session.get(Image, id)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    if not current_user.is_superuser and (image.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="权限不足")
    return ImagePublic.model_validate(image, update={"url": _build_image_url(image)})


@router.post("/upload", response_model=ImagePublic)
async def upload_image(
    *, session: SessionDep, current_user: CurrentUser, file: UploadFile
) -> Any:
    """上传图片，支持 JPEG/PNG/WebP，自动压缩为 WebP 缩略图"""
    # 验证扩展名
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的图片格式，仅允许 JPEG/PNG/WebP")

    # 读取文件内容
    file_bytes = await file.read()

    # 验证大小
    actual_size = len(file_bytes)
    if actual_size > settings.IMAGE_MAX_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制（最大 {settings.IMAGE_MAX_SIZE // 1024 // 1024}MB）")

    # 检查是否为空文件
    if actual_size == 0:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    image = process_and_save_image(
        session=session,
        file_bytes=file_bytes,
        original_filename=file.filename or "unknown",
        image_ext=ext,
        owner_id=current_user.id,
    )
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

    # 删除磁盘文件
    file_path = Path(settings.UPLOAD_DIR) / image.file_path
    if file_path.exists():
        file_path.unlink()

    session.delete(image)
    session.commit()
    return Message(message="图片已删除")
