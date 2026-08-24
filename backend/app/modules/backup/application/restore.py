"""备份合并恢复应用服务"""

import base64
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlmodel import Session, SQLModel, select

from app.core.config import settings
from app.modules.backup.schemas import (
    EntityRestoreStats,
    RestoreResultPublic,
)
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


def _merge_single(
    *,
    session: Session,
    model: type[SQLModel],
    record: dict[str, Any],
    unique_finder: Callable[[SQLModel], SQLModel | None],
    field_mapper: Callable[[SQLModel, dict[str, uuid.UUID]], None],
    mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    """合并单条记录，按 ID 优先、唯一键兜底，不删除当前系统数据。"""
    parsed = model.model_validate(record)
    old_id = str(parsed.id)
    field_mapper(parsed, mapping)
    existing = session.get(model, parsed.id)
    if existing is None:
        existing = unique_finder(parsed)
    stats = EntityRestoreStats()
    if existing is None:
        session.add(parsed)
        stats.inserted = 1
        mapping[old_id] = parsed.id
        return stats
    data = parsed.model_dump(exclude={"id"})
    existing.sqlmodel_update(data)
    session.add(existing)
    stats.updated = 1
    mapping[old_id] = existing.id
    return stats


def _merge_records(
    *,
    session: Session,
    model: type[SQLModel],
    records: list[dict[str, Any]],
    unique_finder: Callable[[SQLModel], SQLModel | None],
    field_mapper: Callable[[SQLModel, dict[str, uuid.UUID]], None],
    mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    """批量合并记录。"""
    stats = EntityRestoreStats()
    for record in records:
        row_stats = _merge_single(
            session=session,
            model=model,
            record=record,
            unique_finder=unique_finder,
            field_mapper=field_mapper,
            mapping=mapping,
        )
        stats.inserted += row_stats.inserted
        stats.updated += row_stats.updated
    session.flush()
    return stats


def _restore_users(
    session: Session,
    records: list[dict[str, Any]],
) -> tuple[EntityRestoreStats, dict[str, uuid.UUID]]:
    mapping: dict[str, uuid.UUID] = {}

    def finder(parsed: SQLModel) -> SQLModel | None:
        user = session.exec(select(User).where(User.email == parsed.email)).first()
        if user is not None:
            return user
        return session.exec(
            select(User).where(User.username == parsed.username)
        ).first()

    stats = _merge_records(
        session=session,
        model=User,
        records=records,
        unique_finder=finder,
        field_mapper=lambda _parsed, _mapping: None,
        mapping=mapping,
    )
    return stats, mapping


def _restore_suppliers(
    session: Session,
    records: list[dict[str, Any]],
) -> tuple[EntityRestoreStats, dict[str, uuid.UUID]]:
    mapping: dict[str, uuid.UUID] = {}

    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(Supplier).where(Supplier.name == parsed.name)
        ).first()

    stats = _merge_records(
        session=session,
        model=Supplier,
        records=records,
        unique_finder=finder,
        field_mapper=lambda _parsed, _mapping: None,
        mapping=mapping,
    )
    return stats, mapping


def _restore_image_categories(
    session: Session,
    records: list[dict[str, Any]],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(ImageCategory).where(ImageCategory.name == parsed.name)
        ).first()

    return _merge_records(
        session=session,
        model=ImageCategory,
        records=records,
        unique_finder=finder,
        field_mapper=lambda _parsed, _mapping: None,
        mapping={},
    )


def _restore_images(
    session: Session,
    records: list[dict[str, Any]],
    user_mapping: dict[str, uuid.UUID],
) -> tuple[EntityRestoreStats, dict[str, uuid.UUID]]:
    mapping: dict[str, uuid.UUID] = {}

    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(Image).where(Image.file_hash == parsed.file_hash)
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.owner_id = user_mapping.get(str(parsed.owner_id), parsed.owner_id)

    stats = _merge_records(
        session=session,
        model=Image,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping=mapping,
    )
    return stats, mapping


def _safe_upload_rel_path(file_path: str) -> Path:
    """校验图片相对路径，禁止绝对路径与路径穿越。"""
    path = Path(file_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("图片备份包含非法路径")
    return path


def _restore_image_files(
    _session: Session,
    records: list[dict[str, Any]],
) -> EntityRestoreStats:
    """把备份中的图片文件写回上传目录。"""
    stats = EntityRestoreStats()
    for record in records:
        content = record.get("content")
        if not content:
            continue
        rel_path = _safe_upload_rel_path(record["file_path"])
        abs_path = Path(settings.UPLOAD_DIR) / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(base64.b64decode(content))
        stats.inserted += 1
    return stats


def _restore_product_categories(
    session: Session,
    records: list[dict[str, Any]],
    image_mapping: dict[str, uuid.UUID],
) -> tuple[EntityRestoreStats, dict[str, uuid.UUID]]:
    """恢复商品分类，先恢复父级再恢复子级。"""
    stats = EntityRestoreStats()
    mapping: dict[str, uuid.UUID] = {}
    remaining = list(records)

    while remaining:
        deferred: list[dict[str, Any]] = []
        progressed = False
        for record in remaining:
            parsed = ProductCategory.model_validate(record)
            merged_record = dict(record)
            if parsed.icon_id is not None:
                parsed.icon_id = image_mapping.get(
                    str(parsed.icon_id), parsed.icon_id
                )
                if session.get(Image, parsed.icon_id) is None:
                    parsed.icon_id = None
                merged_record["icon_id"] = (
                    str(parsed.icon_id) if parsed.icon_id is not None else None
                )
            if parsed.parent_id is not None:
                parent_id = mapping.get(str(parsed.parent_id), parsed.parent_id)
                parsed.parent_id = parent_id
                merged_record["parent_id"] = str(parent_id)
                if session.get(ProductCategory, parent_id) is None:
                    deferred.append(record)
                    continue
            row_stats = _merge_single(
                session=session,
                model=ProductCategory,
                record=merged_record,
                unique_finder=lambda _parsed: None,
                field_mapper=lambda _parsed, _mapping: None,
                mapping=mapping,
            )
            stats.inserted += row_stats.inserted
            stats.updated += row_stats.updated
            progressed = True
        if not progressed and deferred:
            raise ValueError("商品分类层级不完整，无法恢复")
        remaining = deferred
    session.flush()
    return stats, mapping


def _restore_price_templates(
    session: Session,
    records: list[dict[str, Any]],
) -> tuple[EntityRestoreStats, dict[str, uuid.UUID]]:
    mapping: dict[str, uuid.UUID] = {}

    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(PriceTemplate).where(PriceTemplate.name == parsed.name)
        ).first()

    stats = _merge_records(
        session=session,
        model=PriceTemplate,
        records=records,
        unique_finder=finder,
        field_mapper=lambda _parsed, _mapping: None,
        mapping=mapping,
    )
    return stats, mapping


def _restore_price_template_rules(
    session: Session,
    records: list[dict[str, Any]],
    template_mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(PriceTemplateRule).where(
                PriceTemplateRule.price_template_id == parsed.price_template_id,
                PriceTemplateRule.level_id == parsed.level_id,
            )
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.price_template_id = template_mapping.get(
            str(parsed.price_template_id), parsed.price_template_id
        )

    return _merge_records(
        session=session,
        model=PriceTemplateRule,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping={},
    )


def _restore_wallets(
    session: Session,
    records: list[dict[str, Any]],
    user_mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(Wallet).where(Wallet.user_id == parsed.user_id)
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.user_id = user_mapping.get(str(parsed.user_id), parsed.user_id)

    return _merge_records(
        session=session,
        model=Wallet,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping={},
    )


def _restore_products(
    session: Session,
    records: list[dict[str, Any]],
    category_mapping: dict[str, uuid.UUID],
    image_mapping: dict[str, uuid.UUID],
) -> tuple[EntityRestoreStats, dict[str, uuid.UUID]]:
    mapping: dict[str, uuid.UUID] = {}

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        if parsed.category_id is not None:
            parsed.category_id = category_mapping.get(
                str(parsed.category_id), parsed.category_id
            )
            if session.get(ProductCategory, parsed.category_id) is None:
                parsed.category_id = None
        if parsed.image_id is not None:
            parsed.image_id = image_mapping.get(str(parsed.image_id), parsed.image_id)
            if session.get(Image, parsed.image_id) is None:
                parsed.image_id = None

    stats = _merge_records(
        session=session,
        model=Product,
        records=records,
        unique_finder=lambda _parsed: None,
        field_mapper=mapper,
        mapping=mapping,
    )
    return stats, mapping


def _restore_product_suppliers(
    session: Session,
    records: list[dict[str, Any]],
    product_mapping: dict[str, uuid.UUID],
    supplier_mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(ProductSupplier).where(
                ProductSupplier.product_id == parsed.product_id
            )
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.product_id = product_mapping.get(str(parsed.product_id), parsed.product_id)
        if parsed.supplier_id is not None:
            parsed.supplier_id = supplier_mapping.get(
                str(parsed.supplier_id), parsed.supplier_id
            )
            if session.get(Supplier, parsed.supplier_id) is None:
                parsed.supplier_id = None

    return _merge_records(
        session=session,
        model=ProductSupplier,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping={},
    )


def _restore_product_pricings(
    session: Session,
    records: list[dict[str, Any]],
    product_mapping: dict[str, uuid.UUID],
    template_mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(ProductPricing).where(
                ProductPricing.product_id == parsed.product_id
            )
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.product_id = product_mapping.get(str(parsed.product_id), parsed.product_id)
        if parsed.price_template_id is not None:
            parsed.price_template_id = template_mapping.get(
                str(parsed.price_template_id), parsed.price_template_id
            )

    return _merge_records(
        session=session,
        model=ProductPricing,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping={},
    )


def _restore_product_inventories(
    session: Session,
    records: list[dict[str, Any]],
    product_mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(ProductInventory).where(
                ProductInventory.product_id == parsed.product_id
            )
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.product_id = product_mapping.get(str(parsed.product_id), parsed.product_id)

    return _merge_records(
        session=session,
        model=ProductInventory,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping={},
    )


def _restore_product_fulfillments(
    session: Session,
    records: list[dict[str, Any]],
    product_mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(ProductFulfillment).where(
                ProductFulfillment.product_id == parsed.product_id
            )
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.product_id = product_mapping.get(str(parsed.product_id), parsed.product_id)

    return _merge_records(
        session=session,
        model=ProductFulfillment,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping={},
    )


def _restore_product_buy_params(
    session: Session,
    records: list[dict[str, Any]],
    product_mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(ProductBuyParam).where(
                ProductBuyParam.product_id == parsed.product_id,
                ProductBuyParam.key == parsed.key,
            )
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.product_id = product_mapping.get(str(parsed.product_id), parsed.product_id)

    return _merge_records(
        session=session,
        model=ProductBuyParam,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping={},
    )


def _restore_orders(
    session: Session,
    records: list[dict[str, Any]],
    user_mapping: dict[str, uuid.UUID],
    supplier_mapping: dict[str, uuid.UUID],
    product_mapping: dict[str, uuid.UUID],
) -> tuple[EntityRestoreStats, dict[str, uuid.UUID]]:
    order_mapping: dict[str, uuid.UUID] = {}

    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(Order).where(Order.order_no == parsed.order_no)
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.user_id = user_mapping.get(str(parsed.user_id), parsed.user_id)
        if parsed.supplier_id is not None:
            parsed.supplier_id = supplier_mapping.get(
                str(parsed.supplier_id), parsed.supplier_id
            )
        if parsed.product_id is not None:
            parsed.product_id = product_mapping.get(
                str(parsed.product_id), parsed.product_id
            )
            if session.get(Product, parsed.product_id) is None:
                parsed.product_id = None

    stats = _merge_records(
        session=session,
        model=Order,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping=order_mapping,
    )
    return stats, order_mapping


def _restore_order_params(
    session: Session,
    records: list[dict[str, Any]],
    order_mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(OrderParam).where(
                OrderParam.order_id == parsed.order_id,
                OrderParam.key == parsed.key,
            )
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.order_id = order_mapping.get(str(parsed.order_id), parsed.order_id)

    return _merge_records(
        session=session,
        model=OrderParam,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping={},
    )


def restore_backup(
    *,
    session: Session,
    payload: dict[str, Any],
) -> RestoreResultPublic:
    """合并恢复备份数据，恢复失败时整体回滚。"""
    data = payload.get("data") or {}
    try:
        # 图片分类与用户/供应商先恢复，供图片与商品引用。
        image_categories = _restore_image_categories(
            session,
            data.get("image_categories") or [],
        )
        users, user_mapping = _restore_users(session, data.get("users") or [])
        suppliers, supplier_mapping = _restore_suppliers(
            session,
            data.get("suppliers") or [],
        )
        images, image_mapping = _restore_images(
            session,
            data.get("images") or [],
            user_mapping,
        )
        image_files = _restore_image_files(
            session,
            data.get("images_files") or [],
        )

        # 商品依赖顺序：分类 -> 价格模板 -> 商品 -> 商品关联配置。
        product_categories, category_mapping = _restore_product_categories(
            session,
            data.get("product_categories") or [],
            image_mapping,
        )
        price_templates, template_mapping = _restore_price_templates(
            session,
            data.get("price_templates") or [],
        )
        price_template_rules = _restore_price_template_rules(
            session,
            data.get("price_template_rules") or [],
            template_mapping,
        )

        wallets = _restore_wallets(
            session,
            data.get("wallets") or [],
            user_mapping,
        )
        products, product_mapping = _restore_products(
            session,
            data.get("products") or [],
            category_mapping,
            image_mapping,
        )
        product_suppliers = _restore_product_suppliers(
            session,
            data.get("product_suppliers") or [],
            product_mapping,
            supplier_mapping,
        )
        product_pricings = _restore_product_pricings(
            session,
            data.get("product_pricings") or [],
            product_mapping,
            template_mapping,
        )
        product_inventories = _restore_product_inventories(
            session,
            data.get("product_inventories") or [],
            product_mapping,
        )
        product_fulfillments = _restore_product_fulfillments(
            session,
            data.get("product_fulfillments") or [],
            product_mapping,
        )
        product_buy_params = _restore_product_buy_params(
            session,
            data.get("product_buy_params") or [],
            product_mapping,
        )

        orders, order_mapping = _restore_orders(
            session,
            data.get("orders") or [],
            user_mapping,
            supplier_mapping,
            product_mapping,
        )
        order_params = _restore_order_params(
            session,
            data.get("order_params") or [],
            order_mapping,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return RestoreResultPublic(
        users=users,
        wallets=wallets,
        orders=orders,
        order_params=order_params,
        suppliers=suppliers,
        product_categories=product_categories,
        price_templates=price_templates,
        price_template_rules=price_template_rules,
        products=products,
        product_suppliers=product_suppliers,
        product_pricings=product_pricings,
        product_inventories=product_inventories,
        product_fulfillments=product_fulfillments,
        product_buy_params=product_buy_params,
        image_categories=image_categories,
        images=images,
        images_files=image_files,
    )
