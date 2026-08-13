"""供应商模块：查询应用服务"""

import uuid

from sqlmodel import Session

from app.modules.supplier.models import Supplier
from app.modules.supplier.repositories.supplier import (
    get_supplier_or_404 as get_supplier_repo,
)
from app.modules.supplier.repositories.supplier import (
    list_suppliers as list_suppliers_repo,
)
from app.modules.supplier.schemas import (
    PlatformEnum,
    PlatformOption,
    PlatformOptionsPublic,
    SupplierPublic,
    SuppliersPublic,
)

__all__ = [
    "get_platform_options",
    "get_supplier",
    "list_suppliers",
    "to_supplier_public",
    "to_suppliers_public",
]


def _mask_secret(secret: str) -> str:
    """脱敏 app_secret，仅保留后4位"""
    if len(secret) <= 4:
        return "****"
    return f"****{secret[-4:]}"


def to_supplier_public(supplier: Supplier) -> SupplierPublic:
    """将 Supplier 转换为 SupplierPublic（含 app_secret 脱敏）"""
    data = supplier.model_dump(exclude={"app_secret"})
    data["app_secret"] = _mask_secret(supplier.app_secret)
    return SupplierPublic.model_validate(data)


def to_suppliers_public(suppliers: list[Supplier]) -> list[SupplierPublic]:
    """将 Supplier 列表转换为 SupplierPublic 列表"""
    return [to_supplier_public(s) for s in suppliers]


def list_suppliers(
    *, session: Session, skip: int, limit: int
) -> SuppliersPublic:
    """分页查询供应商列表"""
    suppliers, count = list_suppliers_repo(
        session=session,
        skip=skip,
        limit=limit,
    )
    return SuppliersPublic(
        data=to_suppliers_public(suppliers),
        count=count,
    )


def get_supplier(
    *, session: Session, supplier_id: uuid.UUID
) -> SupplierPublic:
    """按 ID 获取供应商详情，不存在时抛出 404"""
    supplier = get_supplier_repo(session=session, supplier_id=supplier_id)
    return to_supplier_public(supplier)


def get_platform_options() -> PlatformOptionsPublic:
    """获取平台枚举选项列表"""
    options = [
        PlatformOption(value=m.value, label=m.name)
        for m in PlatformEnum
    ]
    return PlatformOptionsPublic(data=options)
