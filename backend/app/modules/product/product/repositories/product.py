"""商品模块：数据访问层"""

import uuid
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, delete, func, select

from app.modules.image.models import Image
from app.modules.price_template.models import PriceTemplate
from app.modules.product.category.models import ProductCategory
from app.modules.product.constants import ProductStatus, ProductType, SourceType
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.product.product.schemas import (
    ProductBuyParamUpdate,
    ProductCreate,
)
from app.modules.supplier.models import Supplier


def validate_product_refs(
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


def get_product_or_404(*, session: Session, product_id: uuid.UUID) -> Product:
    """根据 ID 获取商品，不存在时抛出 404"""
    db_product = session.get(Product, product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return db_product


def create_product(
    *,
    session: Session,
    product_in: ProductCreate,
    price_template_id: uuid.UUID | None,
) -> Product:
    """创建商品及其关联配置并提交"""
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
    pricing_data = product_in.pricing.model_dump()
    pricing_data["price_template_id"] = price_template_id
    session.add(
        ProductPricing(
            product_id=product_id,
            **pricing_data,
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


def count_products(
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
    return session.exec(select(func.count()).select_from(Product).where(*filters)).one()


def get_product_supplier(
    *, session: Session, product_id: uuid.UUID
) -> ProductSupplier | None:
    """获取商品的货源配置"""
    return session.exec(
        select(ProductSupplier).where(ProductSupplier.product_id == product_id)
    ).first()


def get_product_pricing(
    *, session: Session, product_id: uuid.UUID
) -> ProductPricing | None:
    """获取商品的定价配置"""
    return session.exec(
        select(ProductPricing).where(ProductPricing.product_id == product_id)
    ).first()


def get_product_inventory(
    *, session: Session, product_id: uuid.UUID
) -> ProductInventory | None:
    """获取商品的库存配置"""
    return session.exec(
        select(ProductInventory).where(ProductInventory.product_id == product_id)
    ).first()


def get_product_fulfillment(
    *, session: Session, product_id: uuid.UUID
) -> ProductFulfillment | None:
    """获取商品的履约配置"""
    return session.exec(
        select(ProductFulfillment).where(ProductFulfillment.product_id == product_id)
    ).first()


def add_product_supplier(
    *,
    session: Session,
    product_id: uuid.UUID,
    supplier_dict: dict[str, Any],
) -> None:
    """新增商品货源配置"""
    session.add(ProductSupplier(product_id=product_id, **supplier_dict))


def delete_product_supplier(*, session: Session, db_supplier: ProductSupplier) -> None:
    """删除商品货源配置"""
    session.delete(db_supplier)


def replace_buy_params(
    *,
    session: Session,
    product_id: uuid.UUID,
    params: list[ProductBuyParamUpdate] | None,
) -> None:
    """整体替换商品下单参数（先删后插）"""
    session.exec(
        delete(ProductBuyParam).where(ProductBuyParam.product_id == product_id)
    )
    for param_in in params or []:
        session.add(
            ProductBuyParam(
                product_id=product_id,
                **param_in.model_dump(exclude_unset=True),
            )
        )


def delete_product_configs(*, session: Session, product_id: uuid.UUID) -> None:
    """删除商品的关联配置（下单参数/货源/定价/库存/履约）"""
    session.exec(
        delete(ProductBuyParam).where(ProductBuyParam.product_id == product_id)
    )
    session.exec(
        delete(ProductSupplier).where(ProductSupplier.product_id == product_id)
    )
    session.exec(delete(ProductPricing).where(ProductPricing.product_id == product_id))
    session.exec(
        delete(ProductInventory).where(ProductInventory.product_id == product_id)
    )
    session.exec(
        delete(ProductFulfillment).where(ProductFulfillment.product_id == product_id)
    )


def get_product_suppliers_map(
    *,
    session: Session,
    product_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ProductSupplier]:
    """批量获取商品的货源配置，避免 N+1 查询"""
    if not product_ids:
        return {}
    rows = session.exec(
        select(ProductSupplier).where(ProductSupplier.product_id.in_(product_ids))
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
        select(ProductFulfillment).where(ProductFulfillment.product_id.in_(product_ids))
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
        select(ProductBuyParam).where(ProductBuyParam.product_id.in_(product_ids))
    ).all()
    result: dict[uuid.UUID, list[ProductBuyParam]] = {}
    for row in rows:
        result.setdefault(row.product_id, []).append(row)
    return result


def get_categories_map(
    *,
    session: Session,
    category_ids: set[uuid.UUID],
) -> dict[uuid.UUID, str]:
    """批量获取分类名称"""
    if not category_ids:
        return {}
    rows = session.exec(
        select(ProductCategory).where(ProductCategory.id.in_(category_ids))
    ).all()
    return {category.id: category.name for category in rows}


def get_images_map(
    *,
    session: Session,
    image_ids: set[uuid.UUID],
) -> dict[uuid.UUID, Image]:
    """批量获取图片"""
    if not image_ids:
        return {}
    rows = session.exec(select(Image).where(Image.id.in_(image_ids))).all()
    return {image.id: image for image in rows}


def get_supplier_names_map(
    *,
    session: Session,
    supplier_ids: set[uuid.UUID],
) -> dict[uuid.UUID, str]:
    """批量获取供应商名称"""
    if not supplier_ids:
        return {}
    rows = session.exec(select(Supplier).where(Supplier.id.in_(supplier_ids))).all()
    return {supplier.id: supplier.name for supplier in rows}
