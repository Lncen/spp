"""商品模块：商品路由层。函数名保持不变以保证 OpenAPI operationId 兼容性"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import select

from app.api.deps import SessionDep, get_current_active_superuser
from app.common.models import Message
from app.core.config import settings
from app.modules.image.models import Image
from app.modules.product.category.models import ProductCategory
from app.modules.product.constants import (
    ProductStatus,
    ProductType,
    SourceType,
)
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.product.product.schemas import (
    ProductBuyParamPublic,
    ProductCreate,
    ProductFulfillmentPublic,
    ProductInventoryPublic,
    ProductPricingPublic,
    ProductPublic,
    ProductsPublic,
    ProductSupplierPublic,
    ProductUpdate,
)
from app.modules.product.product.service import (
    create_product as create_product_service,
)
from app.modules.product.product.service import (
    delete_product as delete_product_service,
)
from app.modules.product.product.service import (
    get_product as get_product_service,
)
from app.modules.product.product.service import (
    get_product_buy_params_map,
    get_product_count,
    get_product_fulfillments_map,
    get_product_inventories_map,
    get_product_pricings_map,
    get_product_suppliers_map,
    list_products,
)
from app.modules.product.product.service import (
    update_product as update_product_service,
)
from app.modules.supplier.models import Supplier

product_router = APIRouter(prefix="/products", tags=["products"])


def _build_image_url(image: Image) -> str:
    """构建图片访问 URL"""
    if settings.STATIC_URL_BASE:
        base = settings.STATIC_URL_BASE.rstrip("/")
        return f"{base}/uploads/{image.file_path}"
    return f"/uploads/{image.file_path}"


def _product_to_public(
    product: Product,
    *,
    category_names: dict[uuid.UUID, str],
    supplier_names: dict[uuid.UUID, str],
    image_url: str | None,
    supplier: ProductSupplier | None,
    pricing: ProductPricing | None,
    inventory: ProductInventory | None,
    fulfillment: ProductFulfillment | None,
    buy_params: list[ProductBuyParam],
) -> ProductPublic:
    """将 Product 及关联配置转换为 ProductPublic"""
    supplier_public = None
    if supplier is not None:
        supplier_public = ProductSupplierPublic(
            supplier_id=supplier.supplier_id,
            supplier_name=(
                supplier_names.get(supplier.supplier_id)
                if supplier.supplier_id is not None
                else None
            ),
            sku_id=supplier.sku_id,
        )

    pricing_public = None
    if pricing is not None:
        pricing_public = ProductPricingPublic(
            price_template_id=pricing.price_template_id,
            cost_price=pricing.cost_price,
            loss_price=pricing.loss_price,
            fixed_price=pricing.fixed_price,
            item_coefficient=pricing.item_coefficient,
            price_display_precision=pricing.price_display_precision,
            rule_type=pricing.rule_type,
            config_mode=pricing.config_mode,
        )

    inventory_public = None
    if inventory is not None:
        inventory_public = ProductInventoryPublic(
            min_quantity=inventory.min_quantity,
            max_quantity=inventory.max_quantity,
            is_repeatable=inventory.is_repeatable,
            is_batch=inventory.is_batch,
            purchase_step=inventory.purchase_step,
            stock=inventory.stock,
        )

    fulfillment_public = None
    if fulfillment is not None:
        fulfillment_public = ProductFulfillmentPublic(
            fulfillment_type=fulfillment.fulfillment_type,
            can_refund=fulfillment.can_refund,
            after_sale_rules=fulfillment.after_sale_rules,
            description=fulfillment.description,
            unit=fulfillment.unit,
            input_fields_overridden=fulfillment.input_fields_overridden,
            params_template=fulfillment.params_template,
        )

    return ProductPublic(
        id=product.id,
        name=product.name,
        category_id=product.category_id,
        category_name=(
            category_names.get(product.category_id)
            if product.category_id is not None
            else None
        ),
        image_id=product.image_id,
        image_url=image_url,
        source_type=product.source_type,
        status=product.status,
        is_closed=product.is_closed,
        sort=product.sort,
        type=product.type,
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
        supplier=supplier_public,
        pricing=pricing_public,
        inventory=inventory_public,
        fulfillment=fulfillment_public,
        buy_params=[
            ProductBuyParamPublic.model_validate(param) for param in buy_params
        ],
    )


def _products_to_public(
    session: SessionDep, products: list[Product]
) -> list[ProductPublic]:
    """批量将商品转换为响应模型，避免 N+1 查询"""
    product_ids = [product.id for product in products]
    supplier_map = get_product_suppliers_map(
        session=session, product_ids=product_ids
    )
    pricing_map = get_product_pricings_map(session=session, product_ids=product_ids)
    inventory_map = get_product_inventories_map(
        session=session, product_ids=product_ids
    )
    fulfillment_map = get_product_fulfillments_map(
        session=session, product_ids=product_ids
    )
    buy_params_map = get_product_buy_params_map(
        session=session, product_ids=product_ids
    )

    category_ids = {
        product.category_id
        for product in products
        if product.category_id is not None
    }
    category_names: dict[uuid.UUID, str] = {}
    if category_ids:
        categories = session.exec(
            select(ProductCategory).where(ProductCategory.id.in_(category_ids))
        ).all()
        category_names = {category.id: category.name for category in categories}

    image_ids = {product.image_id for product in products if product.image_id}
    images: dict[uuid.UUID, Image] = {}
    if image_ids:
        rows = session.exec(select(Image).where(Image.id.in_(image_ids))).all()
        images = {image.id: image for image in rows}

    supplier_ids = {
        supplier.supplier_id
        for supplier in supplier_map.values()
        if supplier.supplier_id is not None
    }
    supplier_names: dict[uuid.UUID, str] = {}
    if supplier_ids:
        suppliers = session.exec(
            select(Supplier).where(Supplier.id.in_(supplier_ids))
        ).all()
        supplier_names = {supplier.id: supplier.name for supplier in suppliers}

    return [
        _product_to_public(
            product,
            category_names=category_names,
            supplier_names=supplier_names,
            image_url=(
                _build_image_url(images[product.image_id])
                if product.image_id in images
                else None
            ),
            supplier=supplier_map.get(product.id),
            pricing=pricing_map.get(product.id),
            inventory=inventory_map.get(product.id),
            fulfillment=fulfillment_map.get(product.id),
            buy_params=buy_params_map.get(product.id, []),
        )
        for product in products
    ]


@product_router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProductsPublic,
)
def read_products(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    category_id: uuid.UUID | None = None,
    status: ProductStatus | None = None,
    source_type: SourceType | None = None,
    product_type: ProductType | None = None,
    is_closed: bool | None = None,
    name: str | None = None,
) -> Any:
    """分页查询商品（仅超管）"""
    products = list_products(
        session=session,
        skip=skip,
        limit=limit,
        category_id=category_id,
        status=status,
        source_type=source_type,
        product_type=product_type,
        is_closed=is_closed,
        name=name,
    )
    count = get_product_count(
        session=session,
        category_id=category_id,
        status=status,
        source_type=source_type,
        product_type=product_type,
        is_closed=is_closed,
        name=name,
    )
    return ProductsPublic(
        data=_products_to_public(session, products),
        count=count,
    )


@product_router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProductPublic,
)
def create_product(
    *, session: SessionDep, product_in: ProductCreate
) -> Any:
    """创建商品及其关联配置（仅超管）"""
    product = create_product_service(session=session, product_in=product_in)
    return _products_to_public(session, [product])[0]


@product_router.get(
    "/{product_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProductPublic,
)
def read_product(session: SessionDep, product_id: uuid.UUID) -> Any:
    """根据 ID 获取商品（仅超管）"""
    product = get_product_service(session=session, product_id=product_id)
    return _products_to_public(session, [product])[0]


@product_router.put(
    "/{product_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProductPublic,
)
def update_product(
    *,
    session: SessionDep,
    product_id: uuid.UUID,
    product_in: ProductUpdate,
) -> Any:
    """更新商品及其关联配置（仅超管）"""
    product = update_product_service(
        session=session,
        product_id=product_id,
        product_in=product_in,
    )
    return _products_to_public(session, [product])[0]


@product_router.delete(
    "/{product_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_product(session: SessionDep, product_id: uuid.UUID) -> Message:
    """删除商品及其关联配置（仅超管）"""
    delete_product_service(session=session, product_id=product_id)
    return Message(message="商品已删除")
