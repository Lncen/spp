"""商品模块：查询应用服务"""

import uuid

from sqlmodel import Session

from app.core.config import settings
from app.modules.image.models import Image
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
from app.modules.product.product.repositories.product import (
    count_products as count_products_repo,
)
from app.modules.product.product.repositories.product import (
    get_categories_map,
    get_images_map,
    get_product_buy_params_map,
    get_product_fulfillments_map,
    get_product_inventories_map,
    get_product_or_404,
    get_product_pricings_map,
    get_product_suppliers_map,
    get_supplier_names_map,
)
from app.modules.product.product.repositories.product import (
    list_products as list_products_repo,
)
from app.modules.product.product.schemas import (
    ProductBuyParamPublic,
    ProductFulfillmentPublic,
    ProductInventoryPublic,
    ProductPricingPublic,
    ProductPublic,
    ProductsPublic,
    ProductSupplierPublic,
)


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
            upstream_name=supplier.upstream_name,
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
        sync_status=product.sync_status,
        synced_at=product.synced_at,
        supplier=supplier_public,
        pricing=pricing_public,
        inventory=inventory_public,
        fulfillment=fulfillment_public,
        buy_params=[
            ProductBuyParamPublic.model_validate(param) for param in buy_params
        ],
    )


def to_products_public(
    session: Session, products: list[Product]
) -> list[ProductPublic]:
    """批量将商品转换为响应模型，避免 N+1 查询"""
    product_ids = [product.id for product in products]
    supplier_map = get_product_suppliers_map(session=session, product_ids=product_ids)
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
        product.category_id for product in products if product.category_id is not None
    }
    category_names = get_categories_map(session=session, category_ids=category_ids)
    image_ids = {product.image_id for product in products if product.image_id}
    images = get_images_map(session=session, image_ids=image_ids)

    supplier_ids = {
        supplier.supplier_id
        for supplier in supplier_map.values()
        if supplier.supplier_id is not None
    }
    supplier_names = get_supplier_names_map(session=session, supplier_ids=supplier_ids)

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
) -> ProductsPublic:
    """分页查询商品列表并组装响应"""
    products = list_products_repo(
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
    count = count_products_repo(
        session=session,
        category_id=category_id,
        status=status,
        source_type=source_type,
        product_type=product_type,
        is_closed=is_closed,
        name=name,
    )
    return ProductsPublic(
        data=to_products_public(session, products),
        count=count,
    )


def get_product(*, session: Session, product_id: uuid.UUID) -> ProductPublic:
    """根据 ID 获取商品详情，不存在时抛出 404"""
    product = get_product_or_404(session=session, product_id=product_id)
    return to_products_public(session, [product])[0]
