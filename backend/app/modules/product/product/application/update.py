"""商品模块：更新商品应用服务"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.product.category.service import sync_category_product_count
from app.modules.product.product.domain.validation import (
    validate_buy_param_keys,
    validate_quantity_bounds,
    validate_single_price_rule,
)
from app.modules.product.product.models import Product
from app.modules.product.product.repositories.product import (
    add_product_supplier,
    delete_product_supplier,
    get_product_fulfillment,
    get_product_inventory,
    get_product_or_404,
    get_product_pricing,
    get_product_supplier,
    replace_buy_params,
    validate_product_refs,
)
from app.modules.product.product.schemas import ProductUpdate


def update_product(
    *,
    session: Session,
    product_id: uuid.UUID,
    product_in: ProductUpdate,
) -> Product:
    """更新商品主表与关联配置"""
    db_product = get_product_or_404(session=session, product_id=product_id)
    update_dict = product_in.model_dump(exclude_unset=True)
    fields_set = product_in.model_fields_set

    has_supplier = "supplier" in fields_set
    supplier_update = product_in.supplier
    update_dict.pop("supplier", None)
    has_pricing = "pricing" in fields_set
    pricing_update = product_in.pricing
    update_dict.pop("pricing", None)
    has_inventory = "inventory" in fields_set
    inventory_update = product_in.inventory
    update_dict.pop("inventory", None)
    has_fulfillment = "fulfillment" in fields_set
    fulfillment_update = product_in.fulfillment
    update_dict.pop("fulfillment", None)
    has_buy_params = "buy_params" in fields_set
    buy_params_update = product_in.buy_params
    update_dict.pop("buy_params", None)

    old_category_id = db_product.category_id
    new_category_id = update_dict.get("category_id", old_category_id)
    if "category_id" in update_dict:
        validate_product_refs(
            session=session,
            category_id=new_category_id,
            price_template_id=None,
            supplier_id=None,
            image_id=update_dict.get("image_id"),
        )
    if "image_id" in update_dict:
        validate_product_refs(
            session=session,
            category_id=None,
            price_template_id=None,
            supplier_id=None,
            image_id=update_dict["image_id"],
        )

    db_product.sqlmodel_update(update_dict)
    session.add(db_product)

    db_supplier = get_product_supplier(session=session, product_id=product_id)
    if has_supplier:
        if supplier_update is None:
            if db_supplier:
                delete_product_supplier(session=session, db_supplier=db_supplier)
        else:
            supplier_dict = supplier_update.model_dump(exclude_unset=True)
            if "supplier_id" in supplier_dict:
                validate_product_refs(
                    session=session,
                    category_id=None,
                    price_template_id=None,
                    supplier_id=supplier_dict["supplier_id"],
                )
            if db_supplier:
                db_supplier.sqlmodel_update(supplier_dict)
                session.add(db_supplier)
            else:
                add_product_supplier(
                    session=session,
                    product_id=product_id,
                    supplier_dict=supplier_dict,
                )

    db_pricing = get_product_pricing(session=session, product_id=product_id)
    if has_pricing:
        if pricing_update is None:
            raise HTTPException(status_code=400, detail="商品必须保留定价配置")
        if db_pricing is None:
            raise HTTPException(status_code=400, detail="商品定价配置不存在")
        pricing_dict = pricing_update.model_dump(exclude_unset=True)
        if "price_template_id" in pricing_dict:
            validate_product_refs(
                session=session,
                category_id=None,
                price_template_id=pricing_dict["price_template_id"],
                supplier_id=None,
            )
        validate_single_price_rule(
            price_template_id=pricing_dict.get(
                "price_template_id", db_pricing.price_template_id
            ),
            fixed_price=pricing_dict.get("fixed_price", db_pricing.fixed_price),
            item_coefficient=pricing_dict.get(
                "item_coefficient", db_pricing.item_coefficient
            ),
        )
        db_pricing.sqlmodel_update(pricing_dict)
        session.add(db_pricing)

    db_inventory = get_product_inventory(session=session, product_id=product_id)
    if has_inventory:
        if inventory_update is None:
            raise HTTPException(status_code=400, detail="商品必须保留库存配置")
        if db_inventory is None:
            raise HTTPException(status_code=400, detail="商品库存配置不存在")
        inventory_dict = inventory_update.model_dump(exclude_unset=True)
        validate_quantity_bounds(
            min_quantity=inventory_dict.get("min_quantity", db_inventory.min_quantity),
            max_quantity=inventory_dict.get("max_quantity", db_inventory.max_quantity),
        )
        db_inventory.sqlmodel_update(inventory_dict)
        session.add(db_inventory)

    db_fulfillment = get_product_fulfillment(session=session, product_id=product_id)
    if has_fulfillment:
        if fulfillment_update is None:
            raise HTTPException(status_code=400, detail="商品必须保留履约配置")
        if db_fulfillment is None:
            raise HTTPException(status_code=400, detail="商品履约配置不存在")
        db_fulfillment.sqlmodel_update(
            fulfillment_update.model_dump(exclude_unset=True)
        )
        session.add(db_fulfillment)

    if has_buy_params:
        if buy_params_update is not None:
            validate_buy_param_keys(params=buy_params_update)
        replace_buy_params(
            session=session,
            product_id=product_id,
            params=buy_params_update,
        )

    session.commit()
    session.refresh(db_product)

    if "category_id" in update_dict and old_category_id != new_category_id:
        sync_category_product_count(session=session, category_id=old_category_id)
        sync_category_product_count(session=session, category_id=new_category_id)
    return db_product
