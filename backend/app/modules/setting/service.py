"""全局设置模块：业务逻辑层"""

import uuid
from typing import Any

from sqlmodel import Session, col, select

from app.modules.setting.constants import DEFAULT_SETTINGS, get_default_setting
from app.modules.setting.models import AppSetting
from app.modules.setting.schemas import SettingUpdate


def get_all_settings(*, session: Session) -> list[AppSetting]:
    """获取全部设置（按 key 升序）"""
    statement = select(AppSetting).order_by(col(AppSetting.key))
    return list(session.exec(statement).all())


def get_setting(*, session: Session, key: str) -> Any:
    """读取单个设置值：数据库优先，缺失时回落到默认值"""
    setting = session.exec(
        select(AppSetting).where(AppSetting.key == key)
    ).first()
    if setting is not None:
        return setting.value
    default = get_default_setting(key)
    return default["value"] if default else None


def get_setting_items(*, session: Session) -> list[dict[str, Any]]:
    """全部设置：默认定义 + 数据库覆盖"""
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


def update_setting(
    *,
    session: Session,
    key: str,
    setting_in: SettingUpdate,
    user_id: uuid.UUID,
) -> AppSetting:
    """新增或更新设置项（upsert），返回更新后的记录"""
    setting = session.exec(
        select(AppSetting).where(AppSetting.key == key)
    ).first()
    default = get_default_setting(key) or {}
    if setting is None:
        setting = AppSetting(
            key=key,
            value=setting_in.value,
            description=default.get("description"),
            updated_by=user_id,
        )
        session.add(setting)
    else:
        setting.value = setting_in.value
        setting.updated_by = user_id
    session.commit()
    session.refresh(setting)
    return setting
