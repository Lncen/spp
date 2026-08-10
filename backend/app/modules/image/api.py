"""图片模块：路由层"""

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.common.models import Message
from app.core.config import settings
from app.modules.image.models import Image
from app.modules.image.schemas import (
    ImageCategoriesPublic,
    ImageCategoryCreate,
    ImageCategoryPublic,
    ImageCategoryUpdate,
    ImagePublic,
    ImageUpdate,
    ImagesPublic,
)
from app.modules.image.service import (
    create_category,
    delete_category,
    get_category,
    get_category_by_name,
    list_categories,
    list_category_options,
    process_and_save_image,
    sync_category_image_count,
    update_category,
    validate_category_name,
)

router = APIRouter(prefix="/images", tags=["images"])
category_router = APIRouter(prefix="/image-categories", tags=["image-categories"])


# ===================== 图片 API =====================


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
    category: str | None = Query(default=None, description="按分类筛选：avatar, product, product_detail"),
) -> Any:
    """获取当前用户的图片列表"""
    base_filter = []
    if category:
        base_filter.append(Image.category == category)

    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Image).where(*base_filter)
        count = session.exec(count_statement).one()
        statement = (
            select(Image)
            .where(*base_filter)
            .order_by(col(Image.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        images = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Image)
            .where(Image.owner_id == current_user.id, *base_filter)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Image)
            .where(Image.owner_id == current_user.id, *base_filter)
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
    *,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile,
    category: str | None = Query(default=None, description="图片分类：avatar, product, product_detail"),
) -> Any:
    """上传图片，支持 JPEG/PNG/WebP，自动压缩为缩略图"""
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

    category_name = image.category

    # 删除磁盘文件
    file_path = Path(settings.UPLOAD_DIR) / image.file_path
    if file_path.exists():
        file_path.unlink()

    session.delete(image)
    session.commit()
    # 同步分类计数
    if category_name:
        sync_category_image_count(session=session, category_name=category_name)
    return Message(message="图片已删除")

@router.patch("/{id}", response_model=ImagePublic)
def update_image(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    data: ImageUpdate,
) -> Any:
    image = session.get(Image, id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not current_user.is_superuser and (image.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Permission denied")

    old_category = image.category
    new_category = data.category

    if new_category is not None:
        valid, msg = validate_category_name(session=session, name=new_category)
        if not valid:
            raise HTTPException(status_code=400, detail=msg)

    image.category = new_category
    session.add(image)
    session.commit()
    session.refresh(image)

    if old_category:
        sync_category_image_count(session=session, category_name=old_category)
    if new_category:
        sync_category_image_count(session=session, category_name=new_category)

    return ImagePublic.model_validate(image, update={"url": _build_image_url(image)})



# ===================== 分类管理 API =====================


@category_router.get("/", response_model=ImageCategoriesPublic)
def read_categories(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """获取所有图片分类列表（含图片计数）"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")
    categories = list_categories(session=session)
    return ImageCategoriesPublic(
        data=[ImageCategoryPublic.model_validate(c) for c in categories],
        count=len(categories),
    )


@category_router.get("/options", response_model=list[str])
def read_category_options(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """获取分类选项名称列表"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")
    return list_category_options(session=session)


@category_router.get("/{id}", response_model=ImageCategoryPublic)
def read_category(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """根据 ID 获取分类详情"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")
    category = get_category(session=session, category_id=id)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    return ImageCategoryPublic.model_validate(category)


@category_router.post("/", response_model=ImageCategoryPublic, status_code=201)
def create_new_category(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    data: ImageCategoryCreate,
) -> Any:
    """创建图片分类（管理员）"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")
    # 检查 name 是否已存在
    existing = get_category_by_name(session=session, name=data.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"分类 '{data.name}' 已存在")
    category = create_category(session=session, data=data)
    return ImageCategoryPublic.model_validate(category)


@category_router.patch("/{id}", response_model=ImageCategoryPublic)
def update_existing_category(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    data: ImageCategoryUpdate,
) -> Any:
    """更新图片分类（管理员）"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")
    category = update_category(session=session, category_id=id, data=data)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    return ImageCategoryPublic.model_validate(category)


@category_router.delete("/{id}")
def delete_existing_category(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Message:
    """删除图片分类（管理员），有图片引用时拒绝删除"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")
    success, msg = delete_category(session=session, category_id=id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return Message(message=msg)
