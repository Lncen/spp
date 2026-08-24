"""数据备份 API 请求与响应模型"""

from datetime import datetime

from sqlmodel import SQLModel


class BackupCounts(SQLModel):
    """单份备份的数据条数统计"""

    users: int = 0
    wallets: int = 0
    orders: int = 0
    order_params: int = 0
    suppliers: int = 0
    product_categories: int = 0
    price_templates: int = 0
    price_template_rules: int = 0
    products: int = 0
    product_suppliers: int = 0
    product_pricings: int = 0
    product_inventories: int = 0
    product_fulfillments: int = 0
    product_buy_params: int = 0
    image_categories: int = 0
    images: int = 0
    images_files: int = 0


class BackupPublic(SQLModel):
    """备份文件列表项"""

    filename: str
    created_at: datetime
    size: int
    order_hours: int
    counts: BackupCounts


class BackupsPublic(SQLModel):
    """备份文件列表响应"""

    data: list[BackupPublic]
    count: int


class EntityRestoreStats(SQLModel):
    """单类数据恢复统计"""

    inserted: int = 0
    updated: int = 0


class RestoreResultPublic(SQLModel):
    """合并恢复结果"""

    users: EntityRestoreStats
    wallets: EntityRestoreStats
    orders: EntityRestoreStats
    order_params: EntityRestoreStats
    suppliers: EntityRestoreStats
    product_categories: EntityRestoreStats
    price_templates: EntityRestoreStats
    price_template_rules: EntityRestoreStats
    products: EntityRestoreStats
    product_suppliers: EntityRestoreStats
    product_pricings: EntityRestoreStats
    product_inventories: EntityRestoreStats
    product_fulfillments: EntityRestoreStats
    product_buy_params: EntityRestoreStats
    image_categories: EntityRestoreStats
    images: EntityRestoreStats
    images_files: EntityRestoreStats
