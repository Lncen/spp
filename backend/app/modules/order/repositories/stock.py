"""订单模块：库存数据访问"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, select, update

from app.modules.product.product.models import ProductInventory


def deduct_stock(
    *, session: Session, inventory: ProductInventory, quantity: int
) -> None:
    """锁定库存行并条件扣减；库存不足时抛错；无限库存直接跳过

    先对库存行 SELECT ... FOR UPDATE：同一商品的所有下单事务
    在库存行上串行，为后续防重复下单检查提供串行点（并发下可
    看到已提交的订单），锁保持到事务结束。
    """
    locked = session.exec(
        select(ProductInventory)
        .where(ProductInventory.id == inventory.id)
        .with_for_update()
    ).first()
    if locked is None:
        raise HTTPException(status_code=400, detail="库存记录不存在")
    if locked.stock == -1:
        return
    result = session.exec(
        update(ProductInventory)
        .where(
            ProductInventory.id == locked.id,
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
