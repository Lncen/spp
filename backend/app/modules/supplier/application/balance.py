"""供应商模块：供应商余额应用服务"""

import uuid
from decimal import Decimal

from sqlmodel import Session

from app.modules.supplier.infrastructure.clients.base import supplier_client
from app.modules.supplier.repositories.supplier import (
    get_supplier_or_404,
    save_supplier_balance,
)


def refresh_supplier_balance(
    *, session: Session, supplier_id: uuid.UUID
) -> Decimal:
    """查询上游实时余额并写回数据库；上游异常时抛出 SupplierClientError"""
    supplier = get_supplier_or_404(session=session, supplier_id=supplier_id)
    with supplier_client(session=session, supplier_id=supplier.id) as client:
        balance = client.query_balance()
    # 上游余额写回数据库，余额列保留 7 位小数
    balance = balance.quantize(Decimal("0.0000001"))
    save_supplier_balance(session=session, supplier=supplier, balance=balance)
    return balance
