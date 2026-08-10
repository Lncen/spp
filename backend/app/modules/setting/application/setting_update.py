"""全局设置模块：设置更新应用服务"""

import uuid

from sqlmodel import Session

from app.modules.setting.infrastructure.cache import cache_set
from app.modules.setting.models import AppSetting
from app.modules.setting.repositories.setting import upsert_setting
from app.modules.setting.schemas import SettingUpdate


def update_setting(
    *,
    session: Session,
    key: str,
    setting_in: SettingUpdate,
    user_id: uuid.UUID,
) -> AppSetting:
    """新增或更新设置项（upsert），写库后同步刷新缓存，返回更新后的记录"""
    setting = upsert_setting(
        session=session,
        key=key,
        value=setting_in.value,
        user_id=user_id,
    )
    session.commit()
    session.refresh(setting)
    cache_set(session=session, key=key, setting=setting)
    return setting
