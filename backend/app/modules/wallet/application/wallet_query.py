"""钱包模块：钱包查询应用服务"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.user.models import User
from app.modules.wallet.models import Wallet, WalletTransaction
from app.modules.wallet.repositories.wallet import (
    count_wallet_transactions,
    count_wallets,
    create_wallet_record,
    list_wallet_transactions,
    list_wallets,
)
from app.modules.wallet.repositories.wallet import (
    get_wallet_by_id as get_wallet_by_id_record,
)
from app.modules.wallet.repositories.wallet import (
    get_wallet_by_user_id as get_wallet_by_user_id_record,
)


def get_wallet_by_user_id(*, session: Session, user_id: uuid.UUID) -> Wallet | None:
    """根据用户 ID 获取钱包"""
    return get_wallet_by_user_id_record(session=session, user_id=user_id)


def get_or_create_wallet(*, session: Session, user_id: uuid.UUID) -> Wallet:
    """获取用户钱包，不存在则自动创建"""
    wallet = get_wallet_by_user_id_record(session=session, user_id=user_id)
    if wallet:
        return wallet
    wallet = create_wallet_record(session=session, user_id=user_id)
    session.commit()
    session.refresh(wallet)
    return wallet


def get_or_create_user_wallet(*, session: Session, user_id: uuid.UUID) -> Wallet:
    """获取指定用户钱包，不存在则自动创建；用户不存在时抛出 404"""
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return get_or_create_wallet(session=session, user_id=user_id)


def get_wallet_by_id(*, session: Session, wallet_id: uuid.UUID) -> Wallet:
    """按 ID 获取钱包，不存在时抛出 404"""
    wallet = get_wallet_by_id_record(session=session, wallet_id=wallet_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="钱包不存在")
    return wallet


def get_wallets_page(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[int, list[Wallet]]:
    """分页查询钱包，返回 (总数, 钱包列表)"""
    count = count_wallets(session=session)
    wallets = list_wallets(session=session, skip=skip, limit=limit)
    return count, wallets


def get_wallet_transactions_page(
    *,
    session: Session,
    wallet_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    tx_type: str | None = None,
) -> tuple[int, list[WalletTransaction]]:
    """分页查询钱包流水，返回 (总数, 流水列表)"""
    count = count_wallet_transactions(
        session=session, wallet_id=wallet_id, tx_type=tx_type
    )
    transactions = list_wallet_transactions(
        session=session,
        wallet_id=wallet_id,
        skip=skip,
        limit=limit,
        tx_type=tx_type,
    )
    return count, transactions
