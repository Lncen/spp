"""创建数据备份应用服务"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.modules.backup.domain.serialization import (
    ORDER_FIELDS,
    ORDER_PARAM_FIELDS,
    SUPPLIER_FIELDS,
    USER_FIELDS,
    WALLET_FIELDS,
    model_to_record,
)
from app.modules.backup.infrastructure.storage import (
    cleanup_old_backups,
    ensure_backup_dir,
    get_retention_days,
    write_backup,
)
from app.modules.backup.schemas import BackupCounts, BackupPublic
from app.modules.order.models import Order, OrderParam
from app.modules.supplier.models import Supplier
from app.modules.user.models import User
from app.modules.wallet.models import Wallet


def _collect_backup_data(
    *,
    session: Session,
    order_hours: int,
) -> tuple[dict[str, list[dict[str, Any]]], BackupCounts]:
    """查询并序列化备份范围数据。"""
    users = session.exec(select(User)).all()
    wallets = session.exec(select(Wallet)).all()
    suppliers = session.exec(select(Supplier)).all()

    since = datetime.now(UTC) - timedelta(hours=order_hours)
    orders = session.exec(
        select(Order).where(Order.created_at >= since)
    ).all()
    order_ids = [order.id for order in orders]
    order_params = []
    if order_ids:
        order_params = session.exec(
            select(OrderParam).where(OrderParam.order_id.in_(order_ids))
        ).all()

    data = {
        "users": [model_to_record(user, USER_FIELDS) for user in users],
        "wallets": [model_to_record(wallet, WALLET_FIELDS) for wallet in wallets],
        "orders": [model_to_record(order, ORDER_FIELDS) for order in orders],
        "order_params": [
            model_to_record(param, ORDER_PARAM_FIELDS) for param in order_params
        ],
        "suppliers": [
            model_to_record(supplier, SUPPLIER_FIELDS) for supplier in suppliers
        ],
    }
    counts = BackupCounts(
        users=len(data["users"]),
        wallets=len(data["wallets"]),
        orders=len(data["orders"]),
        order_params=len(data["order_params"]),
        suppliers=len(data["suppliers"]),
    )
    return data, counts


def create_backup(*, session: Session) -> BackupPublic:
    """创建一份本地备份并清理过期备份。"""
    order_hours = settings.BACKUP_ORDER_HOURS
    data, counts = _collect_backup_data(
        session=session,
        order_hours=order_hours,
    )
    directory = ensure_backup_dir(session=session)
    created_at = datetime.now(UTC)
    file_path, filename = write_backup(
        directory=directory,
        created_at=created_at,
        order_hours=order_hours,
        counts=counts.model_dump(),
        data=data,
    )
    cleanup_old_backups(
        directory=directory,
        retention_days=get_retention_days(session=session),
    )
    return BackupPublic(
        filename=filename,
        created_at=created_at,
        size=file_path.stat().st_size,
        order_hours=order_hours,
        counts=counts,
    )
