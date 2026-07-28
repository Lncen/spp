"""供应商模块：业务逻辑层"""
from sqlmodel import Session

from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import SupplierCreate
from app.modules.supplier.service.clients import get_client


def create_supplier(*, session: Session, supplier_in: SupplierCreate) -> Supplier:
    """创建供应商"""
    db_supplier = Supplier.model_validate(supplier_in)
    session.add(db_supplier)
    session.commit()
    session.refresh(db_supplier)
    return db_supplier


def sync_balance(*, session: Session, supplier: Supplier) -> Supplier:
    """通过供应商 API 查询并更新余额"""
    with get_client(supplier) as client:
        balance = client.query_balance()

    supplier.balance = balance
    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return supplier
