"""钱包模块：路由层。函数名保持不变以保证 OpenAPI operationId 兼容性"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    CurrentUser,
    SessionDep,
    require_permission,
)
from app.modules.system_log.application.audit_log_create import record_audit_log
from app.modules.wallet.application.wallet_adjust import adjust_balance
from app.modules.wallet.application.wallet_query import (
    get_or_create_user_wallet,
    get_or_create_wallet,
    get_wallet_by_id,
    get_wallet_transactions_page,
    get_wallets_page,
)
from app.modules.wallet.application.wallet_update import (
    update_wallet_status as update_wallet_status_service,
)
from app.modules.wallet.domain.constants import WalletTxType
from app.modules.wallet.schemas import (
    WalletAdjust,
    WalletPublic,
    WalletsPublic,
    WalletTransactionPublic,
    WalletTransactionsPublic,
    WalletUpdate,
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
    dependencies=[Depends(require_permission("wallet:view"))],
    response_model=WalletPublic,
)
def read_wallet_by_user_id(*, session: SessionDep, user_id: uuid.UUID) -> Any:
    """获取指定用户钱包，不存在时自动创建"""
    return get_or_create_user_wallet(session=session, user_id=user_id)


@router.get(
    "/",
    dependencies=[Depends(require_permission("wallet:view"))],
    response_model=WalletsPublic,
)
def read_wallets(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """获取全部钱包列表"""
    count, wallets = get_wallets_page(session=session, skip=skip, limit=limit)
    return WalletsPublic(
        data=[WalletPublic.model_validate(w) for w in wallets],
        count=count,
    )


@router.get(
    "/{wallet_id}",
    dependencies=[Depends(require_permission("wallet:view"))],
    response_model=WalletPublic,
)
def read_wallet_by_id(*, session: SessionDep, wallet_id: uuid.UUID) -> Any:
    """按 ID 获取钱包"""
    return get_wallet_by_id(session=session, wallet_id=wallet_id)


@router.get(
    "/{wallet_id}/transactions",
    dependencies=[Depends(require_permission("wallet:view"))],
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
    """获取指定钱包流水"""
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
    dependencies=[Depends(require_permission("wallet:adjust"))],
    response_model=WalletTransactionPublic,
)
def adjust_wallet_balance(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    wallet_id: uuid.UUID,
    body: WalletAdjust,
) -> Any:
    """管理员调账：正数入账，负数扣款"""
    wallet = get_wallet_by_id(session=session, wallet_id=wallet_id)
    balance_before = str(wallet.balance)
    amount = str(body.amount)
    transaction = adjust_balance(
        session=session,
        wallet=wallet,
        amount=body.amount,
        tx_type=WalletTxType.ADJUST,
        remark=body.remark,
        operator_id=current_user.id,
    )
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    request_id = request.headers.get("x-request-id")
    record_audit_log(
        session=session,
        actor=current_user,
        action="wallet.adjust",
        resource_type="wallet",
        resource_id=str(wallet.id),
        before={"balance": balance_before},
        after={"balance": str(transaction.balance_after)},
        changes={
            "balance": {
                "old": balance_before,
                "new": str(transaction.balance_after),
            },
            "amount": {"old": None, "new": amount},
        },
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    return transaction


@router.patch(
    "/{wallet_id}",
    dependencies=[Depends(require_permission("wallet:update"))],
    response_model=WalletPublic,
)
def update_wallet_status(
    *, session: SessionDep, wallet_id: uuid.UUID, body: WalletUpdate
) -> Any:
    """更新钱包启用状态"""
    wallet = get_wallet_by_id(session=session, wallet_id=wallet_id)
    return update_wallet_status_service(
        session=session, wallet=wallet, is_active=body.is_active
    )
