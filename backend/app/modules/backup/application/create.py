"""创建数据备份应用服务"""

import base64
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.time import get_datetime_cn
from app.modules.backup.domain.serialization import (
    IMAGE_CATEGORY_FIELDS,
    IMAGE_FIELDS,
    ORDER_FIELDS,
    ORDER_PARAM_FIELDS,
    PRICE_TEMPLATE_FIELDS,
    PRICE_TEMPLATE_RULE_FIELDS,
    PRODUCT_BUY_PARAM_FIELDS,
    PRODUCT_CATEGORY_FIELDS,
    PRODUCT_FIELDS,
    PRODUCT_FULFILLMENT_FIELDS,
    PRODUCT_INVENTORY_FIELDS,
    PRODUCT_PRICING_FIELDS,
    PRODUCT_SUPPLIER_FIELDS,
    SUPPLIER_FIELDS,
    USER_FIELDS,
    WALLET_FIELDS,
    model_to_record,
)
from app.modules.backup.infrastructure.storage import (
    cleanup_old_backups,
    ensure_backup_dir,
    get_retention_days,
    write_backup,
)
from app.modules.backup.schemas import BackupCounts, BackupPublic
from app.modules.image.models import Image, ImageCategory
from app.modules.order.models import Order, OrderParam
from app.modules.price_template.models import PriceTemplate, PriceTemplateRule
from app.modules.product.category.models import ProductCategory
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.supplier.models import Supplier
from app.modules.user.models import User
from app.modules.wallet.models import Wallet


def _collect_backup_data(
    *,
    session: Session,
    order_hours: int,
) -> tuple[dict[str, list[dict[str, Any]]], BackupCounts]:
    """查询并序列化备份范围数据。"""
    users = session.exec(select(User)).all()
    wallets = session.exec(select(Wallet)).all()
    suppliers = session.exec(select(Supplier)).all()
    product_categories = session.exec(select(ProductCategory)).all()
    price_templates = session.exec(select(PriceTemplate)).all()
    price_template_rules = session.exec(select(PriceTemplateRule)).all()
    products = session.exec(select(Product)).all()
    product_ids = [product.id for product in products]
    product_suppliers: list[ProductSupplier] = []
    product_pricings: list[ProductPricing] = []
    product_inventories: list[ProductInventory] = []
    product_fulfillments: list[ProductFulfillment] = []
    product_buy_params: list[ProductBuyParam] = []
    if product_ids:
        product_suppliers = session.exec(
            select(ProductSupplier).where(
                ProductSupplier.product_id.in_(product_ids)
            )
        ).all()
        product_pricings = session.exec(
            select(ProductPricing).where(ProductPricing.product_id.in_(product_ids))
        ).all()
        product_inventories = session.exec(
            select(ProductInventory).where(
                ProductInventory.product_id.in_(product_ids)
            )
        ).all()
        product_fulfillments = session.exec(
            select(ProductFulfillment).where(
                ProductFulfillment.product_id.in_(product_ids)
            )
        ).all()
        product_buy_params = session.exec(
            select(ProductBuyParam).where(
                ProductBuyParam.product_id.in_(product_ids)
            )
        ).all()
    image_categories = session.exec(select(ImageCategory)).all()
    images = session.exec(select(Image)).all()

    image_files: list[dict[str, Any]] = []
    for image in images:
        abs_path = Path(settings.UPLOAD_DIR) / image.file_path
        if abs_path.is_file():
            content = base64.b64encode(abs_path.read_bytes()).decode("ascii")
            image_files.append(
                {
                    "file_path": image.file_path,
                    "filename": image.filename,
                    "content": content,
                }
            )

    since = get_datetime_cn() - timedelta(hours=order_hours)
    orders = session.exec(
        select(Order).where(Order.created_at >= since)
    ).all()
    order_ids = [order.id for order in orders]
    order_params = []
    if order_ids:
        order_params = session.exec(
            select(OrderParam).where(OrderParam.order_id.in_(order_ids))
        ).all()

    data = {
        "users": [model_to_record(user, USER_FIELDS) for user in users],
        "wallets": [model_to_record(wallet, WALLET_FIELDS) for wallet in wallets],
        "orders": [model_to_record(order, ORDER_FIELDS) for order in orders],
        "order_params": [
            model_to_record(param, ORDER_PARAM_FIELDS) for param in order_params
        ],
        "suppliers": [
            model_to_record(supplier, SUPPLIER_FIELDS) for supplier in suppliers
        ],
        "product_categories": [
            model_to_record(category, PRODUCT_CATEGORY_FIELDS)
            for category in product_categories
        ],
        "price_templates": [
            model_to_record(template, PRICE_TEMPLATE_FIELDS)
            for template in price_templates
        ],
        "price_template_rules": [
            model_to_record(rule, PRICE_TEMPLATE_RULE_FIELDS)
            for rule in price_template_rules
        ],
        "products": [model_to_record(product, PRODUCT_FIELDS) for product in products],
        "product_suppliers": [
            model_to_record(row, PRODUCT_SUPPLIER_FIELDS)
            for row in product_suppliers
        ],
        "product_pricings": [
            model_to_record(row, PRODUCT_PRICING_FIELDS)
            for row in product_pricings
        ],
        "product_inventories": [
            model_to_record(row, PRODUCT_INVENTORY_FIELDS)
            for row in product_inventories
        ],
        "product_fulfillments": [
            model_to_record(row, PRODUCT_FULFILLMENT_FIELDS)
            for row in product_fulfillments
        ],
        "product_buy_params": [
            model_to_record(row, PRODUCT_BUY_PARAM_FIELDS)
            for row in product_buy_params
        ],
        "image_categories": [
            model_to_record(category, IMAGE_CATEGORY_FIELDS)
            for category in image_categories
        ],
        "images": [model_to_record(image, IMAGE_FIELDS) for image in images],
        "images_files": image_files,
    }
    counts = BackupCounts(
        users=len(data["users"]),
        wallets=len(data["wallets"]),
        orders=len(data["orders"]),
        order_params=len(data["order_params"]),
        suppliers=len(data["suppliers"]),
        product_categories=len(data["product_categories"]),
        price_templates=len(data["price_templates"]),
        price_template_rules=len(data["price_template_rules"]),
        products=len(data["products"]),
        product_suppliers=len(data["product_suppliers"]),
        product_pricings=len(data["product_pricings"]),
        product_inventories=len(data["product_inventories"]),
        product_fulfillments=len(data["product_fulfillments"]),
        product_buy_params=len(data["product_buy_params"]),
        image_categories=len(data["image_categories"]),
        images=len(data["images"]),
        images_files=len(data["images_files"]),
    )
    return data, counts


def create_backup(*, session: Session) -> BackupPublic:
    """创建一份本地备份并清理过期备份。"""
    order_hours = settings.BACKUP_ORDER_HOURS
    data, counts = _collect_backup_data(
        session=session,
        order_hours=order_hours,
    )
    directory = ensure_backup_dir(session=session)
    created_at = get_datetime_cn()
    file_path, filename = write_backup(
        directory=directory,
        created_at=created_at,
        order_hours=order_hours,
        counts=counts.model_dump(),
        data=data,
    )
    cleanup_old_backups(
        directory=directory,
        retention_days=get_retention_days(session=session),
    )
    return BackupPublic(
        filename=filename,
        created_at=created_at,
        size=file_path.stat().st_size,
        order_hours=order_hours,
        counts=counts,
    )
