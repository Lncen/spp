"""商品模块：商品业务逻辑层"""

import uuid
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, delete, func, select

from app.modules.image.models import Image
from app.modules.price_template.models import PriceTemplate
from app.modules.product.category.models import ProductCategory
from app.modules.product.category.service import sync_category_product_count
from app.modules.product.constants import ProductStatus, ProductType, SourceType
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.product.product.schemas import ProductCreate, ProductUpdate
from app.modules.supplier.models import Supplier


def _validate_product_refs(
    *,
    session: Session,
    category_id: uuid.UUID | None,
    price_template_id: uuid.UUID | None,
    supplier_id: uuid.UUID | None,
    image_id: uuid.UUID | None = None,
) -> None:
    """校验商品关联的分类、价格模板、供应商与主图存在"""
    if category_id is not None and session.get(ProductCategory, category_id) is None:
        raise HTTPException(status_code=400, detail="商品分类不存在")
    if (
        price_template_id is not None
        and session.get(PriceTemplate, price_template_id) is None
    ):
        raise HTTPException(status_code=400, detail="价格模板不存在")
    if supplier_id is not None and session.get(Supplier, supplier_id) is None:
        raise HTTPException(status_code=400, detail="供应商不存在")
    if image_id is not None and session.get(Image, image_id) is None:
        raise HTTPException(status_code=400, detail="商品主图不存在")


def _validate_buy_params(*, params: list[Any]) -> None:
    """校验下单参数 key 非空且不重复"""
    keys = [param.key for param in params]
    if any(key is None for key in keys):
        raise HTTPException(status_code=400, detail="购买参数 key 不能为空")
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=400, detail="购买参数 key 不能重复")


def create_product(*, session: Session, product_in: ProductCreate) -> Product:
    """创建商品及其关联配置"""
    _validate_product_refs(
        session=session,
        category_id=product_in.category_id,
        price_template_id=product_in.pricing.price_template_id,
        supplier_id=(
            product_in.supplier.supplier_id if product_in.supplier else None
        ),
        image_id=product_in.image_id,
    )
    _validate_buy_params(params=product_in.buy_params)

    db_product = Product(
        name=product_in.name,
        category_id=product_in.category_id,
        image_id=product_in.image_id,
        source_type=product_in.source_type,
        status=product_in.status,
        is_closed=product_in.is_closed,
        sort=product_in.sort,
        type=product_in.type,
    )
    session.add(db_product)
    session.flush()
    product_id = db_product.id

    if product_in.supplier is not None:
        session.add(
            ProductSupplier(
                product_id=product_id,
                **product_in.supplier.model_dump(),
            )
        )
    session.add(
        ProductPricing(
            product_id=product_id,
            **product_in.pricing.model_dump(),
        )
    )
    session.add(
        ProductInventory(
            product_id=product_id,
            **product_in.inventory.model_dump(),
        )
    )
    session.add(
        ProductFulfillment(
            product_id=product_id,
            **product_in.fulfillment.model_dump(),
        )
    )
    for param_in in product_in.buy_params:
        session.add(
            ProductBuyParam(
                product_id=product_id,
                **param_in.model_dump(),
            )
        )

    session.commit()
    session.refresh(db_product)
    sync_category_product_count(
        session=session,
        category_id=product_in.category_id,
    )
    return db_product


def get_product(*, session: Session, product_id: uuid.UUID) -> Product:
    """根据 ID 获取商品"""
    db_product = session.get(Product, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return db_product


def _product_filters(
    *,
    category_id: uuid.UUID | None,
    status: ProductStatus | None,
    source_type: SourceType | None,
    product_type: ProductType | None,
    is_closed: bool | None,
    name: str | None,
) -> list[Any]:
    filters = []
    if category_id is not None:
        filters.append(Product.category_id == category_id)
    if status is not None:
        filters.append(Product.status == status)
    if source_type is not None:
        filters.append(Product.source_type == source_type)
    if product_type is not None:
        filters.append(Product.type == product_type)
    if is_closed is not None:
        filters.append(Product.is_closed == is_closed)
    if name:
        filters.append(Product.name.ilike(f"%{name}%"))
    return filters


def list_products(
    *,
    session: Session,
    skip: int,
    limit: int,
    category_id: uuid.UUID | None = None,
    status: ProductStatus | None = None,
    source_type: SourceType | None = None,
    product_type: ProductType | None = None,
    is_closed: bool | None = None,
    name: str | None = None,
) -> list[Product]:
    """分页查询商品，支持分类/状态/来源/类型/关闭状态/名称筛选"""
    filters = _product_filters(
        category_id=category_id,
        status=status,
        source_type=source_type,
        product_type=product_type,
        is_closed=is_closed,
        name=name,
    )
    statement = (
        select(Product)
        .where(*filters)
        .order_by(
            col(Product.sort).desc(),
            col(Product.created_at).desc(),
        )
        .offset(skip)
        .limit(limit)
    )
    return session.exec(statement).all()


def get_product_count(
    *,
    session: Session,
    category_id: uuid.UUID | None = None,
    status: ProductStatus | None = None,
    source_type: SourceType | None = None,
    product_type: ProductType | None = None,
    is_closed: bool | None = None,
    name: str | None = None,
) -> int:
    """获取商品数量（与列表同条件）"""
    filters = _product_filters(
        category_id=category_id,
        status=status,
        source_type=source_type,
        product_type=product_type,
        is_closed=is_closed,
        name=name,
    )
    return session.exec(
        select(func.count()).select_from(Product).where(*filters)
    ).one()


def update_product(
    *,
    session: Session,
    product_id: uuid.UUID,
    product_in: ProductUpdate,
) -> Product:
    """更新商品主表与关联配置"""
    db_product = get_product(session=session, product_id=product_id)
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
        _validate_product_refs(
            session=session,
            category_id=new_category_id,
            price_template_id=None,
            supplier_id=None,
            image_id=update_dict.get("image_id"),
        )
    if "image_id" in update_dict:
        _validate_product_refs(
            session=session,
            category_id=None,
            price_template_id=None,
            supplier_id=None,
            image_id=update_dict["image_id"],
        )

    db_product.sqlmodel_update(update_dict)
    session.add(db_product)

    db_supplier = session.exec(
        select(ProductSupplier).where(ProductSupplier.product_id == product_id)
    ).first()
    if has_supplier:
        if supplier_update is None:
            if db_supplier:
                session.delete(db_supplier)
        else:
            supplier_dict = supplier_update.model_dump(exclude_unset=True)
            if "supplier_id" in supplier_dict:
                _validate_product_refs(
                    session=session,
                    category_id=None,
                    price_template_id=None,
                    supplier_id=supplier_dict["supplier_id"],
                )
            if db_supplier:
                db_supplier.sqlmodel_update(supplier_dict)
                session.add(db_supplier)
            else:
                session.add(
                    ProductSupplier(
                        product_id=product_id,
                        **supplier_dict,
                    )
                )

    db_pricing = session.exec(
        select(ProductPricing).where(ProductPricing.product_id == product_id)
    ).first()
    if has_pricing:
        if pricing_update is None:
            raise HTTPException(status_code=400, detail="商品必须保留定价配置")
        if db_pricing is None:
            raise HTTPException(status_code=400, detail="商品定价配置不存在")
        pricing_dict = pricing_update.model_dump(exclude_unset=True)
        if "price_template_id" in pricing_dict:
            _validate_product_refs(
                session=session,
                category_id=None,
                price_template_id=pricing_dict["price_template_id"],
                supplier_id=None,
            )
        new_price_template_id = pricing_dict.get(
            "price_template_id",
            db_pricing.price_template_id,
        )
        new_fixed_price = pricing_dict.get("fixed_price", db_pricing.fixed_price)
        new_item_coefficient = pricing_dict.get(
            "item_coefficient",
            db_pricing.item_coefficient,
        )
        filled_count = sum(
            1
            for value in (
                new_price_template_id,
                new_fixed_price,
                new_item_coefficient,
            )
            if value is not None
        )
        if filled_count != 1:
            raise HTTPException(
                status_code=400,
                detail="固定价格、商品系数、价格模板三者必须且只能设置一个",
            )
        db_pricing.sqlmodel_update(pricing_dict)
        session.add(db_pricing)

    db_inventory = session.exec(
        select(ProductInventory).where(ProductInventory.product_id == product_id)
    ).first()
    if has_inventory:
        if inventory_update is None:
            raise HTTPException(status_code=400, detail="商品必须保留库存配置")
        if db_inventory is None:
            raise HTTPException(status_code=400, detail="商品库存配置不存在")
        inventory_dict = inventory_update.model_dump(exclude_unset=True)
        min_quantity = inventory_dict.get("min_quantity", db_inventory.min_quantity)
        max_quantity = inventory_dict.get("max_quantity", db_inventory.max_quantity)
        if min_quantity > max_quantity:
            raise HTTPException(
                status_code=400,
                detail="最小购买数量不能大于最大购买数量",
            )
        db_inventory.sqlmodel_update(inventory_dict)
        session.add(db_inventory)

    db_fulfillment = session.exec(
        select(ProductFulfillment).where(
            ProductFulfillment.product_id == product_id
        )
    ).first()
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
        session.exec(
            delete(ProductBuyParam).where(ProductBuyParam.product_id == product_id)
        )
        if buy_params_update is not None:
            _validate_buy_params(params=buy_params_update)
            for param_in in buy_params_update:
                session.add(
                    ProductBuyParam(
                        product_id=product_id,
                        **param_in.model_dump(exclude_unset=True),
                    )
                )

    session.commit()
    session.refresh(db_product)

    if "category_id" in update_dict and old_category_id != new_category_id:
        sync_category_product_count(session=session, category_id=old_category_id)
        sync_category_product_count(session=session, category_id=new_category_id)
    return db_product


def delete_product(*, session: Session, product_id: uuid.UUID) -> None:
    """删除商品及其关联配置"""
    db_product = get_product(session=session, product_id=product_id)
    category_id = db_product.category_id
    session.exec(
        delete(ProductBuyParam).where(ProductBuyParam.product_id == product_id)
    )
    session.exec(
        delete(ProductSupplier).where(ProductSupplier.product_id == product_id)
    )
    session.exec(
        delete(ProductPricing).where(ProductPricing.product_id == product_id)
    )
    session.exec(
        delete(ProductInventory).where(ProductInventory.product_id == product_id)
    )
    session.exec(
        delete(ProductFulfillment).where(
            ProductFulfillment.product_id == product_id
        )
    )
    session.delete(db_product)
    session.commit()
    sync_category_product_count(session=session, category_id=category_id)


def get_product_suppliers_map(
    *,
    session: Session,
    product_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ProductSupplier]:
    """批量获取商品的货源配置，避免 N+1 查询"""
    if not product_ids:
        return {}
    rows = session.exec(
        select(ProductSupplier).where(
            ProductSupplier.product_id.in_(product_ids)
        )
    ).all()
    return {row.product_id: row for row in rows}


def get_product_pricings_map(
    *,
    session: Session,
    product_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ProductPricing]:
    """批量获取商品的定价配置"""
    if not product_ids:
        return {}
    rows = session.exec(
        select(ProductPricing).where(ProductPricing.product_id.in_(product_ids))
    ).all()
    return {row.product_id: row for row in rows}


def get_product_inventories_map(
    *,
    session: Session,
    product_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ProductInventory]:
    """批量获取商品的库存配置"""
    if not product_ids:
        return {}
    rows = session.exec(
        select(ProductInventory).where(ProductInventory.product_id.in_(product_ids))
    ).all()
    return {row.product_id: row for row in rows}


def get_product_fulfillments_map(
    *,
    session: Session,
    product_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ProductFulfillment]:
    """批量获取商品的履约配置"""
    if not product_ids:
        return {}
    rows = session.exec(
        select(ProductFulfillment).where(
            ProductFulfillment.product_id.in_(product_ids)
        )
    ).all()
    return {row.product_id: row for row in rows}


def get_product_buy_params_map(
    *,
    session: Session,
    product_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[ProductBuyParam]]:
    """批量获取商品的下单参数"""
    if not product_ids:
        return {}
    rows = session.exec(
        select(ProductBuyParam).where(
            ProductBuyParam.product_id.in_(product_ids)
        )
    ).all()
    result: dict[uuid.UUID, list[ProductBuyParam]] = {}
    for row in rows:
        result.setdefault(row.product_id, []).append(row)
    return result
