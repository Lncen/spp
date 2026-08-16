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
