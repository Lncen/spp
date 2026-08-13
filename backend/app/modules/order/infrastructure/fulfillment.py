"""订单模块：上游履约调用基础设施"""

from typing import Any

from sqlmodel import Session, select

from app.modules.order.domain.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.product.product.models import ProductSupplier
from app.modules.supplier.models import Supplier
from app.modules.supplier.service.clients.base import (
    SupplierClientBase,
    SupplierClientError,
    SupplierClientUnknownError,
)


def _fulfill_api_item(*, session: Session, db_order: Order) -> None:
    """调用供应商 API 下单，写入供应商订单号"""
    supplier_id, sku_id = db_order.supplier_id, db_order.sku_id
    if supplier_id is None or not sku_id:
        # 旧订单未落货源快照时回退查询商品当前货源
        supplier_sku = session.exec(
            select(ProductSupplier).where(
                ProductSupplier.product_id == db_order.product_id
            )
        ).first()
        if (
            supplier_sku is None
            or supplier_sku.supplier_id is None
            or not supplier_sku.sku_id
        ):
            raise SupplierClientError("商品未配置供应商或 SKU")
        supplier_id, sku_id = supplier_sku.supplier_id, supplier_sku.sku_id
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise SupplierClientError("供应商不存在")
    client = SupplierClientBase.get_client(supplier)
    try:
        upstream_params = dict(db_order.params or {})
        upstream_params.pop("customer_order_id", None)
        supplier_order_id = client.create_order(
            product_id=sku_id,
            quantity=db_order.quantity,
            customer_order_id=db_order.order_no,
            **upstream_params,
        )

        if supplier_order_id is None:
            raise SupplierClientUnknownError(
                "上游下单成功但未返回订单号，需人工确认"
            )
        db_order.supplier_order_id = supplier_order_id
        db_order.status = OrderStatus.PROCESSING
        session.add(db_order)
    finally:
        client.close()
