"""钱包模块：路由层"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.modules.wallet.models import Wallet, WalletTransaction
from app.modules.wallet.schemas import (
    WalletAdjust,
    WalletPublic,
    WalletsPublic,
    WalletTransactionPublic,
    WalletTransactionsPublic,
)
from app.modules.wallet.service import adjust_balance, get_or_create_wallet

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.get("/me", response_model=WalletPublic)
def read_wallet_me(*, session: SessionDep, current_user: CurrentUser) -> Any:
    """获取当前用户钱包"""
    return get_or_create_wallet(session=session, user_id=current_user.id)


@router.get("/me/transactions", response_model=WalletTransactionsPublic)
def read_wallet_transactions_me(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    tx_type: str | None = None,
) -> Any:
    """获取当前用户钱包流水"""
    wallet = get_or_create_wallet(session=session, user_id=current_user.id)
    conditions = [WalletTransaction.wallet_id == wallet.id]
    if tx_type:
        conditions.append(WalletTransaction.tx_type == tx_type)

    count_statement = (
        select(func.count()).select_from(WalletTransaction).where(*conditions)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(WalletTransaction)
        .where(*conditions)
        .order_by(col(WalletTransaction.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    transactions = session.exec(statement).all()
    return WalletTransactionsPublic(
        data=[WalletTransactionPublic.model_validate(t) for t in transactions],
        count=count,
    )


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=WalletsPublic,
)
def read_wallets(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """获取全部钱包列表（仅超级管理员可用）"""
    count_statement = select(func.count()).select_from(Wallet)
    count = session.exec(count_statement).one()
    statement = (
        select(Wallet).order_by(col(Wallet.created_at).desc()).offset(skip).limit(limit)
    )
    wallets = session.exec(statement).all()
    return WalletsPublic(
        data=[WalletPublic.model_validate(w) for w in wallets],
        count=count,
    )


@router.post(
    "/{wallet_id}/adjust",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=WalletTransactionPublic,
)
def adjust_wallet_balance(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    wallet_id: uuid.UUID,
    body: WalletAdjust,
) -> Any:
    """管理员调账：正数入账，负数扣款（仅超级管理员可用）"""
    wallet = session.get(Wallet, wallet_id)
    if not wallet:
        raise HTTPException(status_code=404, detail="钱包不存在")
    return adjust_balance(
        session=session,
        wallet=wallet,
        amount=body.amount,
        tx_type="adjust",
        remark=body.remark,
        operator_id=current_user.id,
    )
