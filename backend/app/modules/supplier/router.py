"""供应商模块：路由层"""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.common.models import Message
from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import (
    PlatformEnum,
    PlatformOption,
    PlatformOptionsPublic,
    SupplierBalancePublic,
    SupplierCreate,
    SupplierPublic,
    SuppliersPublic,
    SupplierUpdate,
)
from app.modules.supplier.service import (
    create_supplier as create_supplier_service,
    sync_balance as sync_balance_service,
)
from app.modules.supplier.service.clients.base import SupplierClientError
from app.modules.user.models import User

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def require_superuser(current_user: CurrentUser) -> User:
    """校验当前用户为超管"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")
    return current_user

SuperuserDep = Annotated[User, Depends(require_superuser)]


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


@router.get("/", response_model=SuppliersPublic)
def read_suppliers(
    session: SessionDep,
    current_user: SuperuserDep,
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


@router.get("/platform-options", response_model=PlatformOptionsPublic)
def get_platform_options(
    current_user: SuperuserDep,
) -> Any:
    """获取平台枚举选项列表（超管权限，前端下拉菜单使用）"""
    options = [
        PlatformOption(value=m.value, label=m.name)
        for m in PlatformEnum
    ]
    return PlatformOptionsPublic(data=options)


@router.get("/{id}", response_model=SupplierPublic)
def read_supplier(
    session: SessionDep,
    current_user: SuperuserDep,
    id: uuid.UUID = ...,
) -> Any:
    """根据 ID 获取供应商详情（超管权限）"""
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return _supplier_to_public(supplier)


@router.post("/", response_model=SupplierPublic)
def create_supplier(
    *,
    session: SessionDep,
    current_user: SuperuserDep,
    supplier_in: SupplierCreate,
) -> Any:
    """创建供应商（超管权限）"""
    supplier = create_supplier_service(session=session, supplier_in=supplier_in)
    return _supplier_to_public(supplier)


@router.put("/{id}", response_model=SupplierPublic)
def update_supplier(
    *,
    session: SessionDep,
    current_user: SuperuserDep,
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


@router.delete("/{id}", response_model=Message)
def delete_supplier(
    session: SessionDep,
    current_user: SuperuserDep,
    id: uuid.UUID = ...,
) -> Message:
    """删除供应商（超管权限）"""
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")
    session.delete(supplier)
    session.commit()
    return Message(message="供应商已删除")


@router.post("/{id}/sync-balance", response_model=SupplierBalancePublic)
def sync_supplier_balance(
    session: SessionDep,
    current_user: SuperuserDep,
    id: uuid.UUID = ...,
) -> Any:
    """同步供应商余额（通过供应商 API 查询更新，超管权限）"""
    supplier = session.get(Supplier, id)
    if not supplier:
        raise HTTPException(status_code=404, detail="供应商不存在")

    try:
        supplier = sync_balance_service(session=session, supplier=supplier)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SupplierClientError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return SupplierBalancePublic(
        id=supplier.id,
        name=supplier.name,
        balance=supplier.balance,
    )
