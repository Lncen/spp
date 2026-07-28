"""供应商模块：业务逻辑层"""
from sqlmodel import Session

from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import SupplierCreate


def create_supplier(*, session: Session, supplier_in: SupplierCreate) -> Supplier:
    """创建供应商"""
    db_supplier = Supplier.model_validate(supplier_in)
    session.add(db_supplier)
    session.commit()
    session.refresh(db_supplier)
    return db_supplier


def sync_balance(*, session: Session, supplier: Supplier) -> Supplier:
    """通过供应商 API 查询并更新余额

    此处为同步余额的入口，具体 API 调用由业务方注入。
    当前实现为桩逻辑，待接入真实 API 后替换。
    """
    # TODO: 调用供应商 API 查询余额
    # 示例：response = await query_supplier_balance(supplier)
    # supplier.balance = response.balance

    session.add(supplier)
    session.commit()
    session.refresh(supplier)
    return supplier
