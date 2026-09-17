"""供应商模块：路由层"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, get_current_active_superuser
from app.common.models import Message
from app.modules.automation.application.schedule import get_task_status
from app.modules.automation.schemas import TaskStatusPublic
from app.modules.supplier.application.balance import refresh_supplier_balance
from app.modules.supplier.application.create import (
    create_supplier as create_supplier_app,
)
from app.modules.supplier.application.delete import (
    delete_supplier as delete_supplier_app,
)
from app.modules.supplier.application.query import (
    get_platform_options as get_platform_options_app,
)
from app.modules.supplier.application.query import (
    get_supplier as get_supplier_app,
)
from app.modules.supplier.application.query import (
    list_suppliers as list_suppliers_app,
)
from app.modules.supplier.application.query import to_supplier_public
from app.modules.supplier.application.update import (
    update_supplier as update_supplier_app,
)
from app.modules.supplier.application.upstream import (
    create_upstream_products_sync as create_upstream_products_sync_app,
)
from app.modules.supplier.application.upstream import (
    list_upstream_categories as list_upstream_categories_app,
)
from app.modules.supplier.application.upstream import (
    list_upstream_products as list_upstream_products_app,
)
from app.modules.supplier.infrastructure.clients.base import SupplierClientError
from app.modules.supplier.schemas import (
    BalancePublic,
    PlatformOptionsPublic,
    SupplierCreate,
    SupplierPublic,
    SuppliersPublic,
    SupplierUpdate,
    UpstreamCategoriesPublic,
    UpstreamProductsPublic,
    UpstreamProductSyncPublic,
    UpstreamProductSyncRequest,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SuppliersPublic,
)
def read_suppliers(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """获取供应商列表（超管权限）"""
    return list_suppliers_app(session=session, skip=skip, limit=limit)


@router.get(
    "/platform-options",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=PlatformOptionsPublic,
)
def get_platform_options() -> Any:
    """获取平台枚举选项列表（超管权限，前端下拉菜单使用）"""
    return get_platform_options_app()


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SupplierPublic,
)
def read_supplier(
    session: SessionDep,
    id: uuid.UUID = ...,
) -> Any:
    """根据 ID 获取供应商详情（超管权限）"""
    return get_supplier_app(session=session, supplier_id=id)


@router.get(
    "/{id}/balance",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=BalancePublic,
)
def read_supplier_balance(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """获取供应商上游实时余额（超管权限）"""
    try:
        balance = refresh_supplier_balance(session=session, supplier_id=id)
    except SupplierClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return BalancePublic(balance=balance)


@router.get(
    "/{id}/upstream-products",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UpstreamProductsPublic,
)
def read_upstream_products(
    session: SessionDep,
    id: uuid.UUID,
    category_id: str | None = None,
) -> Any:
    """获取上游商品列表并标记本地同步状态（超管权限）"""
    try:
        items = list_upstream_products_app(
            session=session,
            supplier_id=id,
            category_id=category_id,
        )
    except SupplierClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return UpstreamProductsPublic(data=items, count=len(items))


@router.get(
    "/{id}/upstream-categories",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UpstreamCategoriesPublic,
)
def read_upstream_categories(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """获取上游商品分类列表（超管权限）"""
    try:
        items = list_upstream_categories_app(session=session, supplier_id=id)
    except SupplierClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return UpstreamCategoriesPublic(data=items)


@router.post(
    "/{id}/upstream-products/sync",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UpstreamProductSyncPublic,
)
def create_upstream_products_sync(
    session: SessionDep,
    id: uuid.UUID,
    sync_in: UpstreamProductSyncRequest,
) -> Any:
    """按勾选的上游商品 ID 创建异步同步任务（超管权限）"""
    task_id = create_upstream_products_sync_app(
        session=session,
        supplier_id=id,
        product_ids=sync_in.product_ids,
        category_id=sync_in.category_id,
    )
    return UpstreamProductSyncPublic(task_id=task_id)


@router.get(
    "/{id}/upstream-products/sync/{task_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TaskStatusPublic,
)
def read_upstream_products_sync_status(
    session: SessionDep,
    id: uuid.UUID,
    task_id: str,
) -> Any:
    """查询上游商品同步任务状态（超管权限）"""
    get_supplier_app(session=session, supplier_id=id)
    return get_task_status(task_id)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SupplierPublic,
)
def create_supplier(
    *,
    session: SessionDep,
    supplier_in: SupplierCreate,
) -> Any:
    """创建供应商（超管权限）"""
    supplier = create_supplier_app(session=session, supplier_in=supplier_in)
    return to_supplier_public(supplier)


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SupplierPublic,
)
def update_supplier(
    *,
    session: SessionDep,
    id: uuid.UUID,
    supplier_in: SupplierUpdate,
) -> Any:
    """更新供应商信息（超管权限，不含余额）"""
    supplier = update_supplier_app(
        session=session,
        supplier_id=id,
        supplier_in=supplier_in,
    )
    return to_supplier_public(supplier)


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_supplier(
    session: SessionDep,
    id: uuid.UUID = ...,
) -> Message:
    """删除供应商（超管权限）"""
    delete_supplier_app(session=session, supplier_id=id)
    return Message(message="供应商已删除")
