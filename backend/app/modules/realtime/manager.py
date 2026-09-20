"""在线状态管理：进程内连接绑定 + Redis 跨进程 Presence

Presence 的事实来源在 Redis，进程内只保存本进程的 sid 绑定：

- `realtime:online:{user_id}` 保存该用户全部活跃连接 sid（多设备多 sid，跨 worker 共享）；
- 心跳（`PRESENCE_HEARTBEAT_SECONDS`）续期 TTL（`PRESENCE_TTL_SECONDS`），
  worker 崩溃 / 进程被杀后由 TTL 自动离线，不需要额外清理任务；
- 断开连接时用 Lua 原子执行 SREM + SCARD + DEL：只有该用户最后一个连接消失才删除 key，
  避免留下空 Set 导致「已离线却显示在线」。
"""

import logging
import uuid
from collections import defaultdict

from app.core.redis import get_redis, run_redis_sync

logger = logging.getLogger(__name__)

_ONLINE_KEY_PREFIX = "realtime:online:"

# 客户端心跳间隔（秒）：前端按该值定时续期
PRESENCE_HEARTBEAT_SECONDS = 30
# 在线状态 TTL（秒）：超过该时长没有心跳即视为离线
PRESENCE_TTL_SECONDS = 90

# 断开连接：移除 sid，集合为空时删除 key，返回剩余连接数
_REMOVE_CONNECTION_LUA = """
local key = KEYS[1]
redis.call('SREM', key, ARGV[1])
local remaining = redis.call('SCARD', key)
if remaining == 0 then
    redis.call('DEL', key)
end
return remaining
"""

_user_sids: dict[uuid.UUID, set[str]] = defaultdict(set)
_sid_users: dict[str, uuid.UUID] = {}


def _online_key(user_id: uuid.UUID | str) -> str:
    return f"{_ONLINE_KEY_PREFIX}{user_id}"


def add_connection(user_id: uuid.UUID, sid: str) -> None:
    """记录本进程的连接绑定（一个用户可多端在线）"""
    _user_sids[user_id].add(sid)
    _sid_users[sid] = user_id


def remove_connection(sid: str) -> uuid.UUID | None:
    """移除本进程的连接绑定，返回对应的用户 ID（无绑定时返回 None）"""
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


def has_local_connections(user_id: uuid.UUID) -> bool:
    """本进程是否仍有该用户的活跃连接"""
    return bool(_user_sids.get(user_id))


async def mark_online(user_id: uuid.UUID, sid: str) -> bool:
    """登记在线连接并续期 TTL，返回「本次是否由离线转为在线」"""
    try:
        redis = get_redis()
        key = _online_key(user_id)
        pipe = redis.pipeline()
        pipe.scard(key)
        pipe.sadd(key, sid)
        pipe.expire(key, PRESENCE_TTL_SECONDS)
        results = await pipe.execute()
    except Exception:  # noqa: BLE001
        logger.warning("在线状态写入失败 user=%s", user_id, exc_info=True)
        return False
    return int(results[0]) == 0


async def refresh_heartbeat(user_id: uuid.UUID, sid: str) -> bool:
    """心跳续期；sid 已被 TTL 清理时重新登记，返回是否续期成功"""
    try:
        redis = get_redis()
        key = _online_key(user_id)
        pipe = redis.pipeline()
        pipe.sadd(key, sid)
        pipe.expire(key, PRESENCE_TTL_SECONDS)
        results = await pipe.execute()
    except Exception:  # noqa: BLE001
        logger.warning("在线状态续期失败 user=%s", user_id, exc_info=True)
        return False
    return bool(results[1])


async def mark_offline(user_id: uuid.UUID, sid: str) -> bool:
    """移除在线连接，返回「该用户是否已全部离线」"""
    try:
        redis = get_redis()
        remaining = await redis.eval(
            _REMOVE_CONNECTION_LUA,
            1,
            _online_key(user_id),
            sid,
        )
    except Exception:  # noqa: BLE001
        logger.warning("在线状态清理失败 user=%s", user_id, exc_info=True)
        return False
    return int(remaining) == 0


async def _batch_online_async(user_ids: list[uuid.UUID]) -> dict[str, bool]:
    """批量查询在线状态（异步实现）"""
    redis = get_redis()
    pipe = redis.pipeline()
    for user_id in user_ids:
        pipe.scard(_online_key(user_id))
    results = await pipe.execute()
    return {
        str(user_id): int(count) > 0
        for user_id, count in zip(user_ids, results, strict=False)
    }


def batch_online(user_ids: list[uuid.UUID]) -> dict[str, bool]:
    """批量查询在线状态（同步上下文，Redis 不可用时全部按离线降级）"""
    if not user_ids:
        return {}
    try:
        return run_redis_sync(_batch_online_async(user_ids))
    except Exception:  # noqa: BLE001
        logger.warning("在线状态查询失败，降级返回离线", exc_info=True)
        return {}
