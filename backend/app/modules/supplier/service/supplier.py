"""供应商模块：业务逻辑层"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session

from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import SupplierCreate
from app.modules.supplier.service.clients.base import ClientMeta, SupplierClientBase


def create_supplier(*, session: Session, supplier_in: SupplierCreate) -> Supplier:
    """创建供应商"""
    db_supplier = Supplier.model_validate(supplier_in)
    session.add(db_supplier)
    session.commit()
    session.refresh(db_supplier)
    return db_supplier


@contextmanager
def supplier_client(*, session: Session, supplier_id) -> Iterator[SupplierClientBase]:
    """根据供应商ID获取客户端，作为上下文管理器使用，退出时自动关闭"""
    sup = session.get(Supplier, supplier_id)
    if not sup:
        raise ValueError(f"供应商不存在 (ID: {supplier_id})")

    client = ClientMeta.get_client(sup)
    try:
        yield client
    finally:
        client.close()
