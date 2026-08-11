"""钱包模块：路由层。函数名保持不变以保证 OpenAPI operationId 兼容性"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.modules.wallet.application.wallet_adjust import adjust_balance
from app.modules.wallet.application.wallet_query import (
    get_or_create_user_wallet,
    get_or_create_wallet,
    get_wallet_by_id,
    get_wallet_transactions_page,
    get_wallets_page,
)
from app.modules.wallet.domain.constants import WalletTxType
from app.modules.wallet.schemas import (
    WalletAdjust,
    WalletPublic,
    WalletsPublic,
    WalletTransactionPublic,
    WalletTransactionsPublic,
)

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
    count, transactions = get_wallet_transactions_page(
        session=session,
        wallet_id=wallet.id,
        skip=skip,
        limit=limit,
        tx_type=tx_type,
    )
    return WalletTransactionsPublic(
        data=[WalletTransactionPublic.model_validate(t) for t in transactions],
        count=count,
    )


@router.get(
    "/user/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=WalletPublic,
)
def read_wallet_by_user_id(*, session: SessionDep, user_id: uuid.UUID) -> Any:
    """获取指定用户钱包（仅超级管理员可用），不存在时自动创建"""
    return get_or_create_user_wallet(session=session, user_id=user_id)


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=WalletsPublic,
)
def read_wallets(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """获取全部钱包列表（仅超级管理员可用）"""
    count, wallets = get_wallets_page(session=session, skip=skip, limit=limit)
    return WalletsPublic(
        data=[WalletPublic.model_validate(w) for w in wallets],
        count=count,
    )


@router.get(
    "/{wallet_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=WalletPublic,
)
def read_wallet_by_id(*, session: SessionDep, wallet_id: uuid.UUID) -> Any:
    """按 ID 获取钱包（仅超级管理员可用）"""
    return get_wallet_by_id(session=session, wallet_id=wallet_id)


@router.get(
    "/{wallet_id}/transactions",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=WalletTransactionsPublic,
)
def read_wallet_transactions(
    *,
    session: SessionDep,
    wallet_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    tx_type: str | None = None,
) -> Any:
    """获取指定钱包流水（仅超级管理员可用）"""
    get_wallet_by_id(session=session, wallet_id=wallet_id)
    count, transactions = get_wallet_transactions_page(
        session=session,
        wallet_id=wallet_id,
        skip=skip,
        limit=limit,
        tx_type=tx_type,
    )
    return WalletTransactionsPublic(
        data=[WalletTransactionPublic.model_validate(t) for t in transactions],
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
    wallet = get_wallet_by_id(session=session, wallet_id=wallet_id)
    return adjust_balance(
        session=session,
        wallet=wallet,
        amount=body.amount,
        tx_type=WalletTxType.ADJUST,
        remark=body.remark,
        operator_id=current_user.id,
    )
