"""供应商 API 客户端"""


from app.modules.supplier.service.clients.base import (
    SupplierClientBase,
    SupplierClientError,
)
from app.modules.supplier.service.clients.factory import get_client, get_client_by_id


__all__ = [
    "get_client",
    "get_client_by_id",
    "SupplierClientBase",
    "SupplierClientError",
]
