"""备份合并恢复应用服务"""

import uuid
from collections.abc import Callable
from typing import Any

from sqlmodel import Session, SQLModel, select

from app.modules.backup.schemas import (
    EntityRestoreStats,
    RestoreResultPublic,
)
from app.modules.order.models import Order, OrderParam
from app.modules.supplier.models import Supplier
from app.modules.user.models import User
from app.modules.wallet.models import Wallet


def _merge_records(
    *,
    session: Session,
    model: type[SQLModel],
    records: list[dict[str, Any]],
    unique_finder: Callable[[SQLModel], SQLModel | None],
    field_mapper: Callable[[SQLModel, dict[str, uuid.UUID]], None],
    mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    """按 ID 优先、唯一键兜底合并记录，不删除当前系统数据。"""
    stats = EntityRestoreStats()
    for record in records:
        parsed = model.model_validate(record)
        old_id = str(parsed.id)
        field_mapper(parsed, mapping)
        existing = session.get(model, parsed.id)
        if existing is None:
            existing = unique_finder(parsed)
        if existing is None:
            session.add(parsed)
            stats.inserted += 1
            mapping[old_id] = parsed.id
            continue
        data = parsed.model_dump(exclude={"id"})
        existing.sqlmodel_update(data)
        session.add(existing)
        stats.updated += 1
        mapping[old_id] = existing.id
    session.flush()
    return stats


def _restore_users(
    session: Session,
    records: list[dict[str, Any]],
) -> tuple[EntityRestoreStats, dict[str, uuid.UUID]]:
    mapping: dict[str, uuid.UUID] = {}

    def finder(parsed: SQLModel) -> SQLModel | None:
        user = session.exec(select(User).where(User.email == parsed.email)).first()
        if user is not None:
            return user
        return session.exec(select(User).where(User.username == parsed.username)).first()

    stats = _merge_records(
        session=session,
        model=User,
        records=records,
        unique_finder=finder,
        field_mapper=lambda _parsed, _mapping: None,
        mapping=mapping,
    )
    return stats, mapping


def _restore_wallets(
    session: Session,
    records: list[dict[str, Any]],
    user_mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(Wallet).where(Wallet.user_id == parsed.user_id)
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.user_id = user_mapping.get(str(parsed.user_id), parsed.user_id)

    return _merge_records(
        session=session,
        model=Wallet,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping={},
    )


def _restore_suppliers(
    session: Session,
    records: list[dict[str, Any]],
) -> tuple[EntityRestoreStats, dict[str, uuid.UUID]]:
    mapping: dict[str, uuid.UUID] = {}

    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(Supplier).where(Supplier.name == parsed.name)
        ).first()

    stats = _merge_records(
        session=session,
        model=Supplier,
        records=records,
        unique_finder=finder,
        field_mapper=lambda _parsed, _mapping: None,
        mapping=mapping,
    )
    return stats, mapping


def _restore_orders(
    session: Session,
    records: list[dict[str, Any]],
    user_mapping: dict[str, uuid.UUID],
    supplier_mapping: dict[str, uuid.UUID],
) -> tuple[EntityRestoreStats, dict[str, uuid.UUID]]:
    order_mapping: dict[str, uuid.UUID] = {}

    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(Order).where(Order.order_no == parsed.order_no)
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.user_id = user_mapping.get(str(parsed.user_id), parsed.user_id)
        if parsed.supplier_id is not None:
            parsed.supplier_id = supplier_mapping.get(
                str(parsed.supplier_id), parsed.supplier_id
            )

    stats = _merge_records(
        session=session,
        model=Order,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping=order_mapping,
    )
    return stats, order_mapping


def _restore_order_params(
    session: Session,
    records: list[dict[str, Any]],
    order_mapping: dict[str, uuid.UUID],
) -> EntityRestoreStats:
    def finder(parsed: SQLModel) -> SQLModel | None:
        return session.exec(
            select(OrderParam).where(
                OrderParam.order_id == parsed.order_id,
                OrderParam.key == parsed.key,
            )
        ).first()

    def mapper(parsed: SQLModel, _mapping: dict[str, uuid.UUID]) -> None:
        parsed.order_id = order_mapping.get(str(parsed.order_id), parsed.order_id)

    return _merge_records(
        session=session,
        model=OrderParam,
        records=records,
        unique_finder=finder,
        field_mapper=mapper,
        mapping={},
    )


def restore_backup(
    *,
    session: Session,
    payload: dict[str, Any],
) -> RestoreResultPublic:
    """合并恢复备份数据，恢复失败时整体回滚。"""
    data = payload.get("data") or {}
    try:
        suppliers, supplier_mapping = _restore_suppliers(
            session,
            data.get("suppliers") or [],
        )
        users, user_mapping = _restore_users(session, data.get("users") or [])

        # 上面先恢复引用数据；下面按实际入库 ID 建立映射，避免引用到旧 ID。
        wallets = _restore_wallets(
            session,
            data.get("wallets") or [],
            user_mapping,
        )
        orders, order_mapping = _restore_orders(
            session,
            data.get("orders") or [],
            user_mapping,
            supplier_mapping,
        )
        order_params = _restore_order_params(
            session,
            data.get("order_params") or [],
            order_mapping,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return RestoreResultPublic(
        users=users,
        wallets=wallets,
        orders=orders,
        order_params=order_params,
        suppliers=suppliers,
    )
