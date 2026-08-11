"""钱包模块：领域常量"""

from enum import StrEnum


class WalletTxType(StrEnum):
    """钱包交易类型"""

    RECHARGE = "recharge"  # 充值
    CONSUME = "consume"  # 消费
    REFUND = "refund"  # 退款
    ADJUST = "adjust"  # 调账
