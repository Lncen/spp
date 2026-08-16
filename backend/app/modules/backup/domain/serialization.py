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

def model_to_record(obj: SQLModel, fields: tuple[str, ...]) -> dict[str, Any]:
    """把表模型转成 JSON 可序列化的备份记录，只保留声明字段。"""
    data = obj.model_dump(mode="json")
    return {field: data[field] for field in fields}
