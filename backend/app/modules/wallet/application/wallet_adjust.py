"""钱包模块：调账应用服务"""

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.wallet.models import Wallet, WalletTransaction
from app.modules.wallet.repositories.wallet import apply_balance_change


def adjust_balance(
    *,
    session: Session,
    wallet: Wallet,
    amount: Decimal,
    tx_type: str,
    remark: str | None = None,
    operator_id: uuid.UUID | None = None,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
    commit: bool = True,
) -> WalletTransaction:
    """原子调整钱包余额并写入流水，余额不足时拒绝扣款"""
    if amount == 0:
        raise HTTPException(status_code=422, detail="调账金额不能为 0")

    apply_balance_change(session=session, wallet=wallet, amount=amount)
    transaction = WalletTransaction(
        wallet_id=wallet.id,
        amount=amount,
        balance_after=wallet.balance,
        tx_type=tx_type,
        ref_type=ref_type,
        ref_id=ref_id,
        remark=remark,
        operator_id=operator_id,
    )
    session.add(transaction)
    if commit:
        session.commit()
        session.refresh(transaction)
    else:
        session.flush()
        session.refresh(transaction)
    return transaction
