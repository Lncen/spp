"""在线连接管理（进程内连接 + Redis 跨进程在线状态）"""

import logging
import uuid
from collections import defaultdict

from app.core.redis import get_redis, run_redis_sync

logger = logging.getLogger(__name__)

_ONLINE_KEY_PREFIX = "realtime:online:"
_ONLINE_TTL_SECONDS = 3 * 24 * 60 * 60  # worker 崩溃兜底，7 天后自动清理

_user_sids: dict[uuid.UUID, set[str]] = defaultdict(set)
_sid_users: dict[str, uuid.UUID] = {}


def _online_key(user_id: uuid.UUID | str) -> str:
    return f"{_ONLINE_KEY_PREFIX}{user_id}"


def add_connection(user_id: uuid.UUID, sid: str) -> None:
    """记录用户与连接 sid 的绑定（一个用户可多端在线）"""
    _user_sids[user_id].add(sid)
    _sid_users[sid] = user_id


def remove_connection(sid: str) -> uuid.UUID | None:
    """移除连接绑定，返回对应的用户 ID（无绑定时返回 None）"""
    user_id = _sid_users.pop(sid, None)
    if user_id is not None:
        sids = _user_sids.get(user_id)
        if sids:
            sids.discard(sid)
            if not sids:
                _user_sids.pop(user_id, None)
    return user_id


def get_user_by_sid(sid: str) -> uuid.UUID | None:
    """按连接 sid 查询绑定的用户 ID"""
    return _sid_users.get(sid)


def online_user_ids() -> list[uuid.UUID]:
    """当前进程在线用户 ID 列表"""
    return list(_user_sids)


async def set_online(user_id: uuid.UUID, sid: str) -> None:
    """记录 Redis 在线状态（跨进程可见），连接断开时清理"""
    try:
        redis = get_redis()
        key = _online_key(user_id)
        await redis.sadd(key, sid)
        await redis.expire(key, _ONLINE_TTL_SECONDS)
    except Exception:  # noqa: BLE001
        logger.warning("在线状态写入失败 user=%s", user_id, exc_info=True)


async def set_offline(user_id: uuid.UUID, sid: str) -> None:
    """移除连接对应的在线标记"""
    try:
        redis = get_redis()
        await redis.srem(_online_key(user_id), sid)
    except Exception:  # noqa: BLE001
        logger.warning("在线状态清理失败 user=%s", user_id, exc_info=True)


async def _batch_online_async(user_ids: list[uuid.UUID]) -> dict[str, bool]:
    """批量查询在线状态（异步实现）"""
    redis = get_redis()
    pipe = redis.pipeline()
    for user_id in user_ids:
        pipe.exists(_online_key(user_id))
    results = await pipe.execute()
    return {
        str(user_id): bool(exists)
        for user_id, exists in zip(user_ids, results, strict=False)
    }


def batch_online(user_ids: list[uuid.UUID]) -> dict[str, bool]:
    """批量查询在线状态（同步上下文，Redis 不可用时全部返回 False）"""
    if not user_ids:
        return {}
    try:
        return run_redis_sync(_batch_online_async(user_ids))
    except Exception:  # noqa: BLE001
        logger.warning("在线状态查询失败，降级返回离线", exc_info=True)
        return {}
