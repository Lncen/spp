"""备份数据序列化规则"""

from typing import Any

from sqlmodel import SQLModel

USER_FIELDS = (
    "id",
    "level_id",
    "username",
    "email",
    "is_superuser",
    "full_name",
    "can_order",
    "avatar_id",
    "remark",
    "bio",
    "hashed_password",
    "is_active",
    "created_at",
    "updated_at",
)

WALLET_FIELDS = (
    "id",
    "user_id",
    "balance",
    "currency",
    "is_active",
    "created_at",
    "updated_at",
)

ORDER_FIELDS = (
    "id",
    "order_no",
    "user_id",
    "status",
    "total_amount",
    "currency",
    "remark",
    "paid_at",
    "processing_at",
    "completed_at",
    "canceled_at",
    "refunded_at",
    "failed_at",
    "fulfill_failed_count",
    "product_id",
    "product_name",
    "quantity",
    "start_quantity",
    "current_quantity",
    "unit_price",
    "subtotal",
    "base_price",
    "cost_price",
    "loss_price",
    "params",
    "fulfillment_type",
    "supplier_id",
    "sku_id",
    "supplier_order_id",
    "can_refund",
    "is_active",
    "created_at",
    "updated_at",
)

ORDER_PARAM_FIELDS = (
    "id",
    "order_id",
    "key",
    "value",
    "is_active",
    "created_at",
    "updated_at",
)

SUPPLIER_FIELDS = (
    "id",
    "name",
    "platform",
    "base_url",
    "app_key",
    "app_secret",
    "status",
    "connection_status",
    "timeout_seconds",
    "retry_times",
    "description",
    "balance",
    "is_active",
    "created_at",
    "updated_at",
)

PRODUCT_CATEGORY_FIELDS = (
    "id",
    "name",
    "parent_id",
    "icon_id",
    "product_count",
    "sort",
    "is_active",
    "created_at",
    "updated_at",
)

PRICE_TEMPLATE_FIELDS = (
    "id",
    "name",
    "is_default",
    "description",
    "is_active",
    "created_at",
    "updated_at",
)

PRICE_TEMPLATE_RULE_FIELDS = (
    "id",
    "price_template_id",
    "level_id",
    "discount_rate",
    "is_active",
    "created_at",
    "updated_at",
)

PRODUCT_FIELDS = (
    "id",
    "name",
    "category_id",
    "image_id",
    "source_type",
    "status",
    "is_closed",
    "sort",
    "type",
    "sync_status",
    "synced_at",
    "is_active",
    "created_at",
    "updated_at",
)

PRODUCT_SUPPLIER_FIELDS = (
    "id",
    "product_id",
    "supplier_id",
    "sku_id",
    "upstream_name",
    "is_active",
    "created_at",
    "updated_at",
)

PRODUCT_PRICING_FIELDS = (
    "id",
    "product_id",
    "price_template_id",
    "cost_price",
    "loss_price",
    "fixed_price",
    "item_coefficient",
    "price_display_precision",
    "is_active",
    "created_at",
    "updated_at",
)

PRODUCT_INVENTORY_FIELDS = (
    "id",
    "product_id",
    "min_quantity",
    "max_quantity",
    "is_repeatable",
    "is_batch",
    "purchase_step",
    "stock",
    "is_active",
    "created_at",
    "updated_at",
)

PRODUCT_FULFILLMENT_FIELDS = (
    "id",
    "product_id",
    "fulfillment_type",
    "can_refund",
    "after_sale_rules",
    "description",
    "unit",
    "input_fields_overridden",
    "params_template",
    "is_active",
    "created_at",
    "updated_at",
)

PRODUCT_BUY_PARAM_FIELDS = (
    "id",
    "product_id",
    "key",
    "label",
    "value",
    "description",
    "input_type",
    "type_config",
    "default_value",
    "use_default",
    "is_required",
    "is_hidden",
    "is_edit",
    "validate_min",
    "validate_max",
    "is_active",
    "created_at",
    "updated_at",
)

IMAGE_CATEGORY_FIELDS = (
    "id",
    "name",
    "description",
    "sort_order",
    "icon",
    "image_count",
    "is_active",
    "created_at",
    "updated_at",
)

IMAGE_FIELDS = (
    "id",
    "owner_id",
    "file_hash",
    "file_path",
    "filename",
    "file_size",
    "width",
    "height",
    "category",
    "is_active",
    "created_at",
    "updated_at",
)


def model_to_record(obj: SQLModel, fields: tuple[str, ...]) -> dict[str, Any]:
    """把表模型转成 JSON 可序列化的备份记录，只保留声明字段。"""
    data = obj.model_dump(mode="json")
    return {field: data[field] for field in fields}
