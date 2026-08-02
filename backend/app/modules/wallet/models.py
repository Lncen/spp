"""钱包模块：数据库模型"""

import uuid
from decimal import Decimal

from sqlmodel import Field, Relationship, SQLModel

from app.core.mixin.models import BaseModelMixin


class Wallet(BaseModelMixin, SQLModel, table=True):
    """用户钱包数据库模型"""

    user_id: uuid.UUID = Field(
        unique=True,
        index=True,
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
        title="用户 ID",
        description="钱包所属用户的 UUID，一个用户仅有一个钱包",
    )
    balance: Decimal = Field(
        default=Decimal("0.00"),
        max_digits=18,
        decimal_places=2,
        title="余额",
        description="钱包当前可用余额，单位为元，精确到分",
    )
    currency: str = Field(
        default="CNY",
        max_length=3,
        title="币种",
        description="钱包币种，默认 CNY",
    )

    # 关系字段不需要也不支持 Field 参数，保持原样即可
    transactions: list[WalletTransaction] = Relationship(
        back_populates="wallet", cascade_delete=True
    )


class WalletTransaction(BaseModelMixin, SQLModel, table=True):
    """钱包交易流水数据库模型"""

    wallet_id: uuid.UUID = Field(
        index=True,
        foreign_key="wallet.id",
        nullable=False,
        ondelete="CASCADE",
        title="钱包 ID",
        description="关联钱包的 UUID，删除钱包时流水级联删除",
    )
    amount: Decimal = Field(
        max_digits=18,
        decimal_places=2,
        title="变动金额",
        description="有符号金额，入账为正，扣款为负",
    )
    balance_after: Decimal = Field(
        max_digits=18,
        decimal_places=2,
        title="变动后余额",
        description="本次变动后的钱包余额",
    )
    tx_type: str = Field(
        index=True,
        max_length=32,
        title="交易类型",
        description="交易类型：recharge 充值、consume 消费、refund 退款、adjust 调账",
    )
    ref_type: str | None = Field(
        default=None,
        max_length=32,
        title="关联业务类型",
        description="关联的业务类型，如 order",
    )
    ref_id: uuid.UUID | None = Field(
        default=None,
        title="关联业务 ID",
        description="关联业务记录的 UUID",
    )
    remark: str | None = Field(
        default=None,
        max_length=255,
        title="备注",
        description="交易备注",
    )
    operator_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        ondelete="SET NULL",
        title="操作人 ID",
        description="执行本次操作的用户 UUID，系统操作时为 None",
    )

    # 关系字段不需要也不支持 Field 参数，保持原样即可
    wallet: Wallet = Relationship(back_populates="transactions")
