"""供应商 API 客户端工厂"""
import uuid

from sqlmodel import Session

from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import PlatformEnum
from app.modules.supplier.service.clients.base import (
    SupplierClientBase,
    SupplierClientError,
)
from app.modules.supplier.service.clients.ylsup import YlsupClient


def get_client(supplier: Supplier) -> SupplierClientBase:
    """根据供应商平台获取对应的 API 客户端实例"""
    _client_map: dict[PlatformEnum, type[SupplierClientBase]] = {
        PlatformEnum.YLSUP: YlsupClient,
    }
    client_cls = _client_map.get(supplier.platform)
    if client_cls is None:
        raise ValueError(f"不支持的供应商平台: {supplier.platform}")
    return client_cls(supplier)


def get_client_by_id(session: Session, supplier_id: uuid.UUID) -> SupplierClientBase:
    """根据供应商 ID 从数据库查询并初始化客户端"""
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise ValueError(f"供应商不存在: {supplier_id}")
    return get_client(supplier)


__all__ = [
    "get_client",
    "get_client_by_id",
    "SupplierClientBase",
    "SupplierClientError",
]
