"""图片模块：分类管理接口层"""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.common.models import Message
from app.modules.image.application.category_manage import (
    create_category as create_category_service,
    delete_category as delete_category_service,
    get_category as get_category_service,
    get_category_by_name,
    list_categories as list_categories_service,
    list_category_options as list_category_options_service,
    update_category as update_category_service,
)
from app.modules.image.schemas import (
    ImageCategoriesPublic,
    ImageCategoryCreate,
    ImageCategoryPublic,
    ImageCategoryUpdate,
)

category_router = APIRouter(prefix="/image-categories", tags=["image-categories"])


@category_router.get("/", response_model=ImageCategoriesPublic)
def read_categories(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """获取所有图片分类列表（含图片计数）"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")
    categories = list_categories_service(session=session)
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
    return list_category_options_service(session=session)


@category_router.get("/{id}", response_model=ImageCategoryPublic)
def read_category(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """根据 ID 获取分类详情"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")
    category = get_category_service(session=session, category_id=id)
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
    category = create_category_service(session=session, data=data)
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
    category = update_category_service(session=session, category_id=id, data=data)
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
    success, msg = delete_category_service(session=session, category_id=id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return Message(message=msg)
