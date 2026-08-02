"""钱包模块：API 请求与响应模型"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel


class WalletAdjust(SQLModel):
    """管理员调账请求"""

    amount: Decimal = Field(
        max_digits=18,
        decimal_places=2,
        title="调账金额",
        description="正数入账，负数扣款，不能为 0",
    )
    remark: str = Field(
        min_length=1,
        max_length=255,
        title="调账备注",
        description="本次调账的备注说明",
    )


class WalletPublic(SQLModel):
    """钱包公开响应"""

    id: uuid.UUID
    user_id: uuid.UUID
    balance: Decimal
    currency: str
    created_at: datetime | None = None


class WalletsPublic(SQLModel):
    """钱包列表响应"""

    data: list[WalletPublic]
    count: int


class WalletTransactionPublic(SQLModel):
    """钱包交易流水公开响应"""

    id: uuid.UUID
    wallet_id: uuid.UUID
    amount: Decimal
    balance_after: Decimal
    tx_type: str
    ref_type: str | None = None
    ref_id: uuid.UUID | None = None
    remark: str | None = None
    operator_id: uuid.UUID | None = None
    created_at: datetime | None = None


class WalletTransactionsPublic(SQLModel):
    """钱包交易流水列表响应"""

    data: list[WalletTransactionPublic]
    count: int
