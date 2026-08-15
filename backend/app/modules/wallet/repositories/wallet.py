"""钱包模块：数据访问层"""

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, col, delete, func, select, update

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


def purge_old_transactions(
    *, session: Session, before: datetime, limit: int
) -> int:
    """物理删除创建时间早于 before 的钱包流水，返回删除条数。

    仅清理 WalletTransaction 流水数据，不影响 Wallet 余额表；
    分批由调用方控制，避免长事务。
    """
    ids = session.exec(
        select(WalletTransaction.id)
        .where(col(WalletTransaction.created_at) < before)
        .order_by(col(WalletTransaction.created_at).asc())
        .limit(limit)
    ).all()
    if not ids:
        return 0
    session.exec(
        delete(WalletTransaction).where(WalletTransaction.id.in_(ids))
    )
    session.commit()
    return len(ids)


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
