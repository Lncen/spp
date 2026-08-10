"""订单模块：库存数据访问"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, update

from app.modules.product.product.models import ProductInventory


def deduct_stock(
    *, session: Session, inventory: ProductInventory, quantity: int
) -> None:
    """条件扣减库存，库存不足时抛错；无限库存直接跳过"""
    if inventory.stock == -1:
        return
    result = session.exec(
        update(ProductInventory)
        .where(
            ProductInventory.id == inventory.id,
            ProductInventory.stock >= quantity,
        )
        .values(stock=ProductInventory.stock - quantity)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=400, detail="库存不足")


def restore_stock(
    *, session: Session, product_id: uuid.UUID | None, quantity: int
) -> None:
    """订单取消或退款时原子回补库存；无限库存或商品无库存记录时跳过"""
    if product_id is None:
        return
    session.exec(
        update(ProductInventory)
        .where(
            ProductInventory.product_id == product_id,
            ProductInventory.stock != -1,
        )
        .values(stock=ProductInventory.stock + quantity)
    )
