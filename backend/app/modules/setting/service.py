"""全局设置模块：业务逻辑层"""

import json
import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from redis.asyncio import Redis as AsyncRedis
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.redis import get_redis, run_redis_sync
from app.modules.setting.constants import DEFAULT_SETTINGS, get_default_setting
from app.modules.setting.models import AppSetting
from app.modules.setting.schemas import SettingUpdate

logger = logging.getLogger(__name__)

# Redis 中全局设置的 hash 键
SETTINGS_CACHE_KEY = "app:settings"
# 缓存缺失哨兵，用于区分“键不存在”与“值为 None”
_MISS = object()


def get_all_settings(*, session: Session) -> list[AppSetting]:
    """获取全部设置（按 key 升序）"""
    statement = select(AppSetting).order_by(col(AppSetting.key))
    return list(session.exec(statement).all())


def _serialize_setting_item(
    *,
    value: Any,
    description: str | None,
    updated_by: uuid.UUID | None,
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
        item["updated_by"] = uuid.UUID(item["updated_by"])
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


def _cache_get(key: str) -> Any:
    """读取单个缓存项；缓存不可用或键缺失返回 _MISS"""
    raw = _run_cache_redis(lambda r: r.hget(SETTINGS_CACHE_KEY, key))
    return _MISS if raw is None else raw


def _cache_get_all() -> dict[str, str] | None:
    """读取全部缓存项；缓存不可用返回 None"""
    raw = _run_cache_redis(lambda r: r.hgetall(SETTINGS_CACHE_KEY))
    return raw if isinstance(raw, dict) else None


def _load_settings_cache(*, session: Session) -> None:
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


def _cache_set(*, session: Session, key: str, setting: AppSetting) -> None:
    """写库成功后同步更新 Redis 缓存并重置 TTL；缓存未初始化时先全量加载"""
    if not _cache_get_all():
        _load_settings_cache(session=session)
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


def get_setting(*, session: Session, key: str) -> Any:
    """读取设置值：优先 Redis 缓存，缓存缺失时懒加载，Redis 不可用回落数据库"""
    raw = _cache_get(key)
    if raw is not _MISS:
        return json.loads(raw)["value"]
    _load_settings_cache(session=session)
    raw = _cache_get(key)
    if raw is not _MISS:
        return json.loads(raw)["value"]
    setting = session.exec(
        select(AppSetting).where(AppSetting.key == key)
    ).first()
    if setting is not None:
        return setting.value
    default = get_default_setting(key)
    return default["value"] if default else None


def get_setting_items(*, session: Session) -> list[dict[str, Any]]:
    """全部设置：优先 Redis 缓存，缓存缺失时懒加载，Redis 不可用回落数据库"""
    cache = _cache_get_all()
    if cache:
        return _cache_to_items(cache)
    _load_settings_cache(session=session)
    cache = _cache_get_all()
    if cache:
        return _cache_to_items(cache)
    return _get_setting_items_from_db(session=session)


def _cache_to_items(cache: dict[str, str]) -> list[dict[str, Any]]:
    """缓存项排序并还原为设置列表"""
    items = [_parse_setting_item(key=key, raw=raw) for key, raw in cache.items()]
    return sorted(items, key=lambda item: item["key"])


def _get_setting_items_from_db(*, session: Session) -> list[dict[str, Any]]:
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


def update_setting(
    *,
    session: Session,
    key: str,
    setting_in: SettingUpdate,
    user_id: uuid.UUID,
) -> AppSetting:
    """新增或更新设置项（upsert），写库后同步刷新缓存，返回更新后的记录"""
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
    _cache_set(session=session, key=key, setting=setting)
    return setting
