"""钱包模块：数据访问层"""

import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, col, func, select, update

from app.modules.wallet.models import Wallet, WalletTransaction


def get_wallet_by_user_id(*, session: Session, user_id: uuid.UUID) -> Wallet | None:
    """根据用户 ID 获取钱包"""
    statement = select(Wallet).where(Wallet.user_id == user_id)
    return session.exec(statement).first()


def get_wallet_by_id(*, session: Session, wallet_id: uuid.UUID) -> Wallet | None:
    """按 ID 获取钱包"""
    return session.get(Wallet, wallet_id)


def create_wallet_record(*, session: Session, user_id: uuid.UUID) -> Wallet:
    """创建用户钱包（不提交，由应用层控制事务）"""
    wallet = Wallet(user_id=user_id)
    session.add(wallet)
    session.flush()
    return wallet


def count_wallets(*, session: Session) -> int:
    """统计钱包总数"""
    return session.exec(select(func.count()).select_from(Wallet)).one()


def list_wallets(*, session: Session, skip: int = 0, limit: int = 100) -> list[Wallet]:
    """按创建时间倒序分页查询钱包"""
    statement = (
        select(Wallet).order_by(col(Wallet.created_at).desc()).offset(skip).limit(limit)
    )
    return list(session.exec(statement).all())


def count_wallet_transactions(
    *, session: Session, wallet_id: uuid.UUID, tx_type: str | None = None
) -> int:
    """统计钱包流水数量"""
    conditions = [WalletTransaction.wallet_id == wallet_id]
    if tx_type:
        conditions.append(WalletTransaction.tx_type == tx_type)
    statement = (
        select(func.count()).select_from(WalletTransaction).where(*conditions)
    )
    return session.exec(statement).one()


def list_wallet_transactions(
    *,
    session: Session,
    wallet_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    tx_type: str | None = None,
) -> list[WalletTransaction]:
    """按创建时间倒序分页查询钱包流水"""
    conditions = [WalletTransaction.wallet_id == wallet_id]
    if tx_type:
        conditions.append(WalletTransaction.tx_type == tx_type)
    statement = (
        select(WalletTransaction)
        .where(*conditions)
        .order_by(col(WalletTransaction.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def apply_balance_change(
    *, session: Session, wallet: Wallet, amount: Decimal
) -> Wallet:
    """原子更新钱包余额，余额不足时回滚并抛出 400"""
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
    return wallet
