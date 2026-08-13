"""供应商模块：更新供应商应用服务"""

import uuid

from sqlmodel import Session

from app.modules.supplier.models import Supplier
from app.modules.supplier.repositories.supplier import (
    get_supplier_or_404,
)
from app.modules.supplier.repositories.supplier import (
    update_supplier as update_supplier_repo,
)
from app.modules.supplier.schemas import SupplierUpdate


def update_supplier(
    *, session: Session, supplier_id: uuid.UUID, supplier_in: SupplierUpdate
) -> Supplier:
    """更新供应商信息（超管权限，不含余额）"""
    supplier = get_supplier_or_404(session=session, supplier_id=supplier_id)
    update_dict = supplier_in.model_dump(exclude_unset=True)
    # 禁止通过此接口修改 balance
    update_dict.pop("balance", None)
    return update_supplier_repo(
        session=session,
        supplier=supplier,
        update_dict=update_dict,
    )
