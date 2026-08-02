"""供应商模块：业务逻辑层"""

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlmodel import Session, select

from app.modules.product.category.models import ProductCategory
from app.modules.product.category.service import sync_category_product_count
from app.modules.product.constants import (
    InputType,
    ProductStatus,
    ProductType,
    RedeemType,
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
from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import SupplierCreate
from app.modules.supplier.service.clients.base import ClientMeta, SupplierClientBase


def create_supplier(*, session: Session, supplier_in: SupplierCreate) -> Supplier:
    """创建供应商"""
    db_supplier = Supplier.model_validate(supplier_in)
    session.add(db_supplier)
    session.commit()
    session.refresh(db_supplier)
    return db_supplier


@contextmanager
def supplier_client(*, session: Session, supplier_id) -> Iterator[SupplierClientBase]:
    """根据供应商ID获取客户端，作为上下文管理器使用，退出时自动关闭"""
    sup = session.get(Supplier, supplier_id)
    if not sup:
        raise ValueError(f"供应商不存在 (ID: {supplier_id})")

    client = ClientMeta.get_client(sup, session=session)
    try:
        yield client
    finally:
        client.close()


def list_upstream_products(
    *,
    session: Session,
    supplier_id,
    category_id: str | None = None,
) -> list[dict[str, Any]]:
    """获取上游商品列表，并标记是否已同步到本地"""
    with supplier_client(session=session, supplier_id=supplier_id) as client:
        items = client.query_products_list(
            page=1,
            page_size=100,
            category_id=category_id,
        )

    local_rows = session.exec(
        select(ProductSupplier).where(ProductSupplier.supplier_id == supplier_id)
    ).all()
    local_by_sku = {
        row.sku_id: row.product_id for row in local_rows if row.sku_id
    }

    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or "id" not in item:
            continue
        upstream_id = str(item["id"])
        raw_price = item.get("price")
        result.append(
            {
                "upstream_id": upstream_id,
                "name": str(item.get("name") or ""),
                "cost_price": (
                    Decimal(str(raw_price)) if raw_price not in (None, "") else None
                ),
                "synced": upstream_id in local_by_sku,
                "local_product_id": local_by_sku.get(upstream_id),
            }
        )
    return result


def list_upstream_categories(
    *,
    session: Session,
    supplier_id,
) -> list[dict[str, str]]:
    """获取上游商品分类列表"""
    with supplier_client(session=session, supplier_id=supplier_id) as client:
        categories = client.get_categories()

    return [
        {
            "id": str(item["id"]),
            "name": str(item["name"]),
            "parent_id": str(item.get("parent_id") or "0"),
        }
        for item in categories
        if isinstance(item, dict) and "id" in item and "name" in item
    ]


def _parse_decimal(value: Any, field: str) -> Decimal:
    """解析上游数字字段，失败时抛出带字段名的异常"""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValueError(f"上游字段 {field} 无法解析为数字: {value!r}") from e


def _parse_int(value: Any, default: int) -> int:
    """解析上游整数字段，非法值回退默认值"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_type_config(value: Any) -> list[dict[str, Any]]:
    """解析上游 type_config，字符串 JSON 解析失败时返回空列表"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _build_buy_params(detail: dict[str, Any]) -> list[dict[str, Any]]:
    """将上游 buy_params 转为本地 ProductBuyParam 字段字典"""
    result: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for param in detail.get("buy_params") or []:
        if not isinstance(param, dict):
            continue
        key = str(param.get("key") or "").strip()
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        verify = param.get("verify")
        verify = verify if isinstance(verify, dict) else {}
        upstream_type = _parse_int(param.get("type"), 0)
        input_type = (
            InputType.LINK_EXTRACT if upstream_type == 61 else InputType.TEXT
        )
        result.append(
            {
                "key": key,
                "label": str(param.get("name") or key),
                "value": str(param.get("value") or ""),
                "description": str(param.get("description") or ""),
                "input_type": input_type,
                "type_config": _parse_type_config(param.get("type_config")),
                "default_value": str(param.get("value") or ""),
                "use_default": bool(param.get("is_default")),
                "is_required": True,
                "is_hidden": False,
                "is_edit": True,
                "validate_min": max(
                    _parse_int(verify.get("min"), 0), 0
                ),
                "validate_max": max(
                    _parse_int(verify.get("max"), 0), 0
                ),
            }
        )
    return result


def sync_upstream_product(
    *,
    session: Session,
    supplier: Supplier,
    detail: dict[str, Any],
    category_id: uuid.UUID | None = None,
) -> tuple[str, Any]:
    """同步单个上游商品到本地：匹配时只更新成本价，未匹配时创建完整商品"""
    if "id" not in detail:
        raise ValueError("上游商品详情缺少 id 字段")
    if "price" not in detail:
        raise ValueError("上游商品详情缺少 price 字段")

    upstream_id = str(detail["id"])
    cost_price = _parse_decimal(detail["price"], "price")
    if category_id is not None and session.get(ProductCategory, category_id) is None:
        raise ValueError("本地分类不存在")
    db_supplier = session.exec(
        select(ProductSupplier).where(
            ProductSupplier.supplier_id == supplier.id,
            ProductSupplier.sku_id == upstream_id,
        )
    ).first()

    if db_supplier:
        db_product = session.get(Product, db_supplier.product_id)
        if db_product is None:
            raise ValueError("已同步商品缺少商品记录，无法更新")
        db_pricing = session.exec(
            select(ProductPricing).where(
                ProductPricing.product_id == db_supplier.product_id
            )
        ).first()
        if db_pricing is None:
            raise ValueError("已同步商品缺少定价配置，无法更新成本价")
        old_category_id = db_product.category_id
        db_pricing.cost_price = cost_price
        if category_id is not None and category_id != db_product.category_id:
            db_product.category_id = category_id
            session.add(db_product)
        session.add(db_pricing)
        session.commit()
        if category_id is not None and old_category_id != category_id:
            if old_category_id is not None:
                sync_category_product_count(
                    session=session, category_id=old_category_id
                )
            sync_category_product_count(session=session, category_id=category_id)
        return "updated", db_supplier.product_id

    min_quantity = max(_parse_int(detail.get("buy_min_limit"), 1), 1)
    max_quantity = max(_parse_int(detail.get("buy_max_limit"), 1_000_000), 1)
    if max_quantity < min_quantity:
        max_quantity = min_quantity
    stock = max(_parse_int(detail.get("stock"), -1), -1)
    product_type = (
        ProductType.CARD
        if _parse_int(detail.get("is_card_code"), 0) == 1
        else ProductType.NORMAL_PRODUCT
    )
    buy_params = _build_buy_params(detail)

    product = Product(
        name=str(detail.get("name") or f"上游商品 {upstream_id}"),
        category_id=category_id,
        image_id=None,
        source_type=SourceType.API_INTEGRATION,
        status=ProductStatus.PENDING_REVIEW,
        is_closed=False,
        sort=0,
        type=product_type,
    )
    session.add(product)
    session.flush()
    product_id = product.id

    session.add(
        ProductSupplier(
            product_id=product_id,
            supplier_id=supplier.id,
            sku_id=upstream_id,
        )
    )
    session.add(
        ProductPricing(
            product_id=product_id,
            cost_price=cost_price,
            fixed_price=cost_price,
            loss_price=Decimal("0.00"),
        )
    )
    session.add(
        ProductInventory(
            product_id=product_id,
            min_quantity=min_quantity,
            max_quantity=max_quantity,
            is_repeatable=_parse_int(detail.get("is_repeat"), 0) == 1,
            is_batch=_parse_int(detail.get("is_batch"), 1) == 1,
            stock=stock,
        )
    )
    session.add(
        ProductFulfillment(
            product_id=product_id,
            fulfillment_type=RedeemType.AUTO_API,
            description=str(detail.get("particulars") or ""),
            unit=str(detail.get("unit") or "1"),
            params_template=buy_params,
        )
    )
    for param in buy_params:
        session.add(ProductBuyParam(product_id=product_id, **param))

    session.commit()
    if category_id is not None:
        sync_category_product_count(session=session, category_id=category_id)
    return "created", product_id
