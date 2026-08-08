"""供应商模块：路由层"""
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.common.models import Message
from app.core.celery_app import celery_app
from app.modules.schedule.schemas import TaskStatusPublic
from app.modules.schedule.service import get_task_status
from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import (
    BalancePublic,
    PlatformEnum,
    PlatformOption,
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
from app.modules.supplier.service import (
    create_supplier as create_supplier_service,
)
from app.modules.supplier.service import (
    list_upstream_categories,
    list_upstream_products,
    supplier_client,
)
from app.modules.supplier.service.clients.base import SupplierClientError

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _mask_secret(secret: str) -> str:
    """脱敏 app_secret，仅保留后4位"""
    if len(secret) <= 4:
        return "****"
    return f"****{secret[-4:]}"


def _supplier_to_public(supplier: Supplier) -> SupplierPublic:
    """将 Supplier 转换为 SupplierPublic（含 app_secret 脱敏）"""
    data = supplier.model_dump(exclude={"app_secret"})
    data["app_secret"] = _mask_secret(supplier.app_secret)
    return SupplierPublic.model_validate(data)


def _suppliers_to_public(suppliers: list[Supplier]) -> list[SupplierPublic]:
    """将 Supplier 列表转换为 SupplierPublic 列表"""
    return [_supplier_to_public(s) for s in suppliers]


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
    count_statement = select(func.count()).select_from(Supplier)
    count = session.exec(count_statement).one()
    statement = (
        select(Supplier)
        .order_by(col(Supplier.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    suppliers = session.exec(statement).all()
    return SuppliersPublic(
        data=_suppliers_to_public(suppliers),
        count=count,
    )


@router.get(
    "/platform-options",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=PlatformOptionsPublic,
)
def get_platform_options() -> Any:
    """获取平台枚举选项列表（超管权限，前端下拉菜单使用）"""
    options = [
        PlatformOption(value=m.value, label=m.name)
        for m in PlatformEnum
    ]
    return PlatformOptionsPublic(data=options)


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
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return _supplier_to_public(supplier)


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
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    try:
        with supplier_client(session=session, supplier_id=supplier.id) as client:
            balance = client.query_balance()
    except SupplierClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    # 上游余额写回数据库，余额列保留 7 位小数
    balance = balance.quantize(Decimal("0.0000001"))
    supplier.balance = balance
    session.add(supplier)
    session.commit()
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
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    try:
        items = list_upstream_products(
            session=session,
            supplier_id=supplier.id,
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
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    try:
        items = list_upstream_categories(session=session, supplier_id=supplier.id)
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
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    if not sync_in.product_ids:
        raise HTTPException(status_code=400, detail="请至少选择一个商品")
    task = celery_app.send_task(
        "app.tasks.supplier.sync_upstream_products",
        kwargs={
            "supplier_id": str(supplier.id),
            "product_ids": sync_in.product_ids,
            "category_id": (
                str(sync_in.category_id) if sync_in.category_id else None
            ),
        },
    )
    return UpstreamProductSyncPublic(task_id=task.id)


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
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
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
    supplier = create_supplier_service(session=session, supplier_in=supplier_in)
    return _supplier_to_public(supplier)


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
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    update_dict = supplier_in.model_dump(exclude_unset=True)
    # 禁止通过此接口修改 balance
    update_dict.pop("balance", None)

    supplier.sqlmodel_update(update_dict)
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return _supplier_to_public(supplier)


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
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    session.delete(supplier)
    session.commit()
    return Message(message="供应商已删除")
