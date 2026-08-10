"""全局设置模块：设置查询应用服务"""

import json
from typing import Any

from sqlmodel import Session

from app.modules.setting.domain.constants import get_default_setting
from app.modules.setting.infrastructure.cache import (
    _MISS,
    cache_get,
    cache_get_all,
    cache_to_items,
    load_settings_cache,
)
from app.modules.setting.repositories.setting import (
    get_setting_from_db,
    get_setting_items_from_db,
)


def get_setting(*, session: Session, key: str) -> Any:
    """读取设置值：优先 Redis 缓存，缓存缺失时懒加载，Redis 不可用回落数据库"""
    raw = cache_get(key)
    if raw is not _MISS:
        return json.loads(raw)["value"]
    load_settings_cache(session=session)
    raw = cache_get(key)
    if raw is not _MISS:
        return json.loads(raw)["value"]
    setting = get_setting_from_db(session=session, key=key)
    if setting is not None:
        return setting.value
    default = get_default_setting(key)
    return default["value"] if default else None


def get_setting_items(*, session: Session) -> list[dict[str, Any]]:
    """全部设置：优先 Redis 缓存，缓存缺失时懒加载，Redis 不可用回落数据库"""
    cache = cache_get_all()
    if cache:
        return cache_to_items(cache)
    load_settings_cache(session=session)
    cache = cache_get_all()
    if cache:
        return cache_to_items(cache)
    return get_setting_items_from_db(session=session)
