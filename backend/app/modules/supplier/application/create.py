"""供应商模块：创建供应商应用服务"""

from sqlmodel import Session

from app.modules.supplier.models import Supplier
from app.modules.supplier.repositories.supplier import (
    create_supplier as create_supplier_repo,
)
from app.modules.supplier.schemas import SupplierCreate


def create_supplier(*, session: Session, supplier_in: SupplierCreate) -> Supplier:
    """创建供应商"""
    return create_supplier_repo(session=session, supplier_in=supplier_in)
