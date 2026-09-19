"""授权模块：权限缓存基础设施

缓存键：``spp:perm:{version}:user:{user_id}``，值为用户有效权限码 JSON 列表。
``version`` 用于权限定义变更时整体失效，避免使用 SCAN 遍历删除。
Redis 不可用时全部降级为缓存未命中，由调用方回落数据库。

本文件是叶子基础设施，不引用任何业务模块的 application / repositories，
以便其他模块（如角色管理）在清理授权后直接失效缓存而不会形成循环依赖。
"""

import json
import logging
import uuid
from collections.abc import Callable, Iterable
from typing import Any

from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings
from app.core.redis import get_redis, is_redis_ready, run_redis_sync

logger = logging.getLogger(__name__)

PERMISSION_CACHE_VERSION_KEY = "spp:perm:version"
_DEFAULT_VERSION = 1


def _run_cache_redis(command: Callable[[AsyncRedis], Any]) -> Any | None:
    """执行缓存 Redis 命令；失败返回 None，由调用方回落数据库"""
    if not is_redis_ready():
        return None
    try:
        return run_redis_sync(command(get_redis()))
    except Exception:
        logger.warning("权限缓存 Redis 操作失败，本次回落数据库", exc_info=True)
        return None


def _user_cache_key(*, user_id: uuid.UUID, version: int) -> str:
    """用户权限缓存键"""
    return f"spp:perm:{version}:user:{user_id}"


def get_cache_version() -> int:
    """当前缓存版本号，缺失或非法时回落默认版本"""
    raw = _run_cache_redis(lambda r: r.get(PERMISSION_CACHE_VERSION_KEY))
    try:
        return int(raw) if raw is not None else _DEFAULT_VERSION
    except (TypeError, ValueError):
        return _DEFAULT_VERSION


def get_user_permission_codes(*, user_id: uuid.UUID) -> set[str] | None:
    """读取用户权限码缓存；未命中或缓存不可用返回 None"""
    version = get_cache_version()
    raw = _run_cache_redis(
        lambda r: r.get(_user_cache_key(user_id=user_id, version=version))
    )
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("权限缓存内容无法解析，按未命中处理 user_id=%s", user_id)
        return None
    if not isinstance(payload, list):
        return None
    return {str(code) for code in payload}


def set_user_permission_codes(
    *, user_id: uuid.UUID, codes: set[str]
) -> None:
    """写入用户权限码缓存并设置 TTL"""
    version = get_cache_version()
    payload = json.dumps(sorted(codes), ensure_ascii=False)
    _run_cache_redis(
        lambda r: r.set(
            _user_cache_key(user_id=user_id, version=version),
            payload,
            ex=settings.PERMISSION_CACHE_TTL_SECONDS,
        )
    )


def invalidate_user_permissions(*, user_ids: Iterable[uuid.UUID]) -> None:
    """失效指定用户的权限缓存（角色分配、角色权限变更、角色停用时调用）"""
    version = get_cache_version()
    keys = [
        _user_cache_key(user_id=user_id, version=version)
        for user_id in set(user_ids)
    ]
    if not keys:
        return
    _run_cache_redis(lambda r: r.delete(*keys))


def invalidate_all_permissions() -> None:
    """整体失效权限缓存：递增版本号，旧键由 TTL 自然回收"""
    _run_cache_redis(lambda r: r.incr(PERMISSION_CACHE_VERSION_KEY))
