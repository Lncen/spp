"""钱包模块：业务逻辑层"""

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select, update

from app.modules.wallet.models import Wallet, WalletTransaction


def get_wallet_by_user_id(*, session: Session, user_id: uuid.UUID) -> Wallet | None:
    """根据用户 ID 获取钱包"""
    statement = select(Wallet).where(Wallet.user_id == user_id)
    return session.exec(statement).first()


def get_or_create_wallet(*, session: Session, user_id: uuid.UUID) -> Wallet:
    """获取用户钱包，不存在则自动创建"""
    wallet = get_wallet_by_user_id(session=session, user_id=user_id)
    if wallet:
        return wallet
    wallet = Wallet(user_id=user_id)
    session.add(wallet)
    session.commit()
    session.refresh(wallet)
    return wallet


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

    statement = (
        update(Wallet)
        .where(Wallet.id == wallet.id, Wallet.balance + amount >= 0)
        .values(balance=Wallet.balance + amount)
    )
    result = session.exec(statement)
    if result.rowcount == 0:
        session.rollback()
        raise HTTPException(status_code=400, detail="余额不足，无法扣减")

    session.refresh(wallet)
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
