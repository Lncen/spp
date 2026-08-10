"""全局设置模块：Redis 缓存基础设施"""

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis as AsyncRedis
from sqlmodel import Session

from app.core.config import settings
from app.core.redis import get_redis, run_redis_sync
from app.modules.setting.domain.constants import DEFAULT_SETTINGS
from app.modules.setting.repositories.setting import get_all_settings

logger = logging.getLogger(__name__)

# Redis 中全局设置的 hash 键
SETTINGS_CACHE_KEY = "app:settings"
# 缓存缺失哨兵，用于区分"键不存在"与"值为 None"
_MISS = object()


def _serialize_setting_item(
    *,
    value: Any,
    description: str | None,
    updated_by: UUID | None,
    updated_at: datetime | None,
) -> str:
    """设置项序列化为 Redis 缓存 JSON"""
    item = {
        "value": value,
        "description": description,
        "updated_by": str(updated_by) if updated_by else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }
    return json.dumps(item, ensure_ascii=False)


def _parse_setting_item(key: str, raw: str) -> dict[str, Any]:
    """从 Redis 缓存 JSON 还原设置项（字段与 SettingRead 一致）"""
    item: dict[str, Any] = json.loads(raw)
    item["key"] = key
    if item.get("updated_by"):
        item["updated_by"] = UUID(item["updated_by"])
    if item.get("updated_at"):
        item["updated_at"] = datetime.fromisoformat(item["updated_at"])
    return item


def _run_cache_redis(command: Callable[[AsyncRedis], Any]) -> Any | None:
    """执行缓存 Redis 命令；失败返回 None，由调用方回落数据库"""
    try:
        return run_redis_sync(command(get_redis()))
    except Exception:
        logger.warning("设置缓存 Redis 操作失败，本次回落数据库", exc_info=True)
        return None


def cache_get(key: str) -> Any:
    """读取单个缓存项；缓存不可用或键缺失返回 _MISS"""
    raw = _run_cache_redis(lambda r: r.hget(SETTINGS_CACHE_KEY, key))
    return _MISS if raw is None else raw


def cache_get_all() -> dict[str, str] | None:
    """读取全部缓存项；缓存不可用返回 None"""
    raw = _run_cache_redis(lambda r: r.hgetall(SETTINGS_CACHE_KEY))
    return raw if isinstance(raw, dict) else None


def load_settings_cache(*, session: Session) -> None:
    """从数据库全量加载设置到 Redis 缓存（懒加载）"""
    rows = {s.key: s for s in get_all_settings(session=session)}
    mapping: dict[str, str] = {}
    for key, default in DEFAULT_SETTINGS.items():
        row = rows.get(key)
        mapping[key] = _serialize_setting_item(
            value=row.value if row else default.get("value"),
            description=default.get("description"),
            updated_by=row.updated_by if row else None,
            updated_at=row.updated_at if row else None,
        )
    for key, row in rows.items():
        if key not in mapping:
            mapping[key] = _serialize_setting_item(
                value=row.value,
                description=row.description,
                updated_by=row.updated_by,
                updated_at=row.updated_at,
            )
    _run_cache_redis(lambda r: r.hset(SETTINGS_CACHE_KEY, mapping=mapping))
    _run_cache_redis(
        lambda r: r.expire(SETTINGS_CACHE_KEY, settings.SETTINGS_CACHE_TTL_SECONDS)
    )


def cache_set(*, session: Session, key: str, setting: Any) -> None:
    """写库成功后同步更新 Redis 缓存并重置 TTL；缓存未初始化时先全量加载"""
    if not cache_get_all():
        load_settings_cache(session=session)
    raw = _serialize_setting_item(
        value=setting.value,
        description=setting.description,
        updated_by=setting.updated_by,
        updated_at=setting.updated_at,
    )
    _run_cache_redis(lambda r: r.hset(SETTINGS_CACHE_KEY, key, raw))
    _run_cache_redis(
        lambda r: r.expire(SETTINGS_CACHE_KEY, settings.SETTINGS_CACHE_TTL_SECONDS)
    )


def cache_to_items(cache: dict[str, str]) -> list[dict[str, Any]]:
    """缓存项排序并还原为设置列表"""
    items = [_parse_setting_item(key=key, raw=raw) for key, raw in cache.items()]
    return sorted(items, key=lambda item: item["key"])
