"""图片模块：分类管理接口层"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, require_permission
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


@category_router.get(
    "/",
    dependencies=[Depends(require_permission("image_category:view"))],
    response_model=ImageCategoriesPublic,
)
def read_categories(session: SessionDep) -> Any:
    """获取所有图片分类列表（含图片计数）"""
    categories = list_categories_service(session=session)
    return ImageCategoriesPublic(
        data=[ImageCategoryPublic.model_validate(c) for c in categories],
        count=len(categories),
    )


@category_router.get(
    "/options",
    dependencies=[Depends(require_permission("image_category:view"))],
    response_model=list[str],
)
def read_category_options(session: SessionDep) -> Any:
    """获取分类选项名称列表"""
    return list_category_options_service(session=session)


@category_router.get(
    "/{id}",
    dependencies=[Depends(require_permission("image_category:view"))],
    response_model=ImageCategoryPublic,
)
def read_category(session: SessionDep, id: uuid.UUID) -> Any:
    """根据 ID 获取分类详情"""
    category = get_category_service(session=session, category_id=id)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    return ImageCategoryPublic.model_validate(category)


@category_router.post(
    "/",
    dependencies=[Depends(require_permission("image_category:create"))],
    response_model=ImageCategoryPublic,
    status_code=201,
)
def create_new_category(
    *,
    session: SessionDep,
    data: ImageCategoryCreate,
) -> Any:
    """创建图片分类（管理员）"""
    # 检查 name 是否已存在
    existing = get_category_by_name(session=session, name=data.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"分类 '{data.name}' 已存在")
    category = create_category_service(session=session, data=data)
    return ImageCategoryPublic.model_validate(category)


@category_router.patch(
    "/{id}",
    dependencies=[Depends(require_permission("image_category:update"))],
    response_model=ImageCategoryPublic,
)
def update_existing_category(
    *,
    session: SessionDep,
    id: uuid.UUID,
    data: ImageCategoryUpdate,
) -> Any:
    """更新图片分类"""
    category = update_category_service(session=session, category_id=id, data=data)
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    return ImageCategoryPublic.model_validate(category)


@category_router.delete(
    "/{id}",
    dependencies=[Depends(require_permission("image_category:delete"))],
)
def delete_existing_category(
    *,
    session: SessionDep,
    id: uuid.UUID,
) -> Message:
    """删除图片分类，有图片引用时拒绝删除"""
    success, msg = delete_category_service(session=session, category_id=id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return Message(message=msg)
