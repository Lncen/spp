"""钱包模块：更新应用服务"""

from sqlmodel import Session

from app.modules.wallet.models import Wallet


def update_wallet_status(
    *, session: Session, wallet: Wallet, is_active: bool
) -> Wallet:
    """更新钱包启用状态并提交事务"""
    wallet.is_active = is_active
    session.add(wallet)
    session.commit()
    session.refresh(wallet)
    return wallet
