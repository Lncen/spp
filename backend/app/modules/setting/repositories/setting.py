"""全局设置模块：数据访问层"""

import uuid
from typing import Any

from sqlmodel import Session, col, select

from app.modules.setting.domain.constants import DEFAULT_SETTINGS, get_default_setting
from app.modules.setting.models import AppSetting


def get_all_settings(*, session: Session) -> list[AppSetting]:
    """获取全部设置（按 key 升序）"""
    statement = select(AppSetting).order_by(col(AppSetting.key))
    return list(session.exec(statement).all())


def get_setting_from_db(*, session: Session, key: str) -> AppSetting | None:
    """按 key 查询数据库中的设置项，不存在返回 None"""
    return session.exec(
        select(AppSetting).where(AppSetting.key == key)
    ).first()


def get_setting_items_from_db(*, session: Session) -> list[dict[str, Any]]:
    """全部设置：默认定义 + 数据库覆盖（Redis 不可用时的兜底）"""
    rows = {s.key: s for s in get_all_settings(session=session)}
    keys = list(dict.fromkeys([*DEFAULT_SETTINGS.keys(), *rows.keys()]))
    result: list[dict[str, Any]] = []
    for key in keys:
        default = get_default_setting(key) or {}
        row = rows.get(key)
        result.append(
            {
                "key": key,
                "value": row.value if row else default.get("value"),
                "description": default.get("description"),
                "updated_by": row.updated_by if row else None,
                "updated_at": row.updated_at if row else None,
            }
        )
    return result


def upsert_setting(
    *,
    session: Session,
    key: str,
    value: Any,
    user_id: uuid.UUID,
) -> AppSetting:
    """新增或更新设置项（upsert），不提交事务，由调用方控制"""
    setting = session.exec(
        select(AppSetting).where(AppSetting.key == key)
    ).first()
    default = get_default_setting(key) or {}
    if setting is None:
        setting = AppSetting(
            key=key,
            value=value,
            description=default.get("description"),
            updated_by=user_id,
        )
        session.add(setting)
    else:
        setting.value = value
        setting.updated_by = user_id
    session.flush()
    return setting
