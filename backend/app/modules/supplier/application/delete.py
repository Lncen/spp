"""供应商模块：删除供应商应用服务"""

import uuid

from sqlmodel import Session

from app.modules.supplier.repositories.supplier import (
    delete_supplier as delete_supplier_repo,
)
from app.modules.supplier.repositories.supplier import (
    get_supplier_or_404,
)


def delete_supplier(*, session: Session, supplier_id: uuid.UUID) -> None:
    """删除供应商"""
    supplier = get_supplier_or_404(session=session, supplier_id=supplier_id)
    delete_supplier_repo(session=session, supplier=supplier)
