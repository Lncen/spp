"""聊天模块：按业务事件限流

按「事件 + 用户」做固定窗口计数（Redis Lua 原子执行），不使用整条连接的统一限流器：
发送、typing、已读、订阅各自拥有独立配额，某类事件刷屏不会挤掉其他能力。

Redis 不可用时**放行**（fail-open）：限流属于保护措施，实时通道本身是 best-effort，
不应该因为限流组件故障而让用户发不出消息。
"""

import logging
import uuid

from app.core.redis import get_redis
from app.modules.chat.domain.constants import RATE_LIMITS_PER_SECOND

logger = logging.getLogger(__name__)

_RATE_LIMIT_KEY_PREFIX = "chat:ratelimit:"

# 固定窗口计数：首次计数时设置 1 秒过期，超过配额返回 0
_RATE_LIMIT_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
end
if current > tonumber(ARGV[1]) then
    return 0
end
return 1
"""


async def allow_event(
    *,
    event: str,
    user_id: uuid.UUID,
) -> bool:
    """判断该用户在当前窗口内是否还能触发该事件（未配置限额的事件直接放行）"""
    limit = RATE_LIMITS_PER_SECOND.get(event)
    if limit is None:
        return True
    key = f"{_RATE_LIMIT_KEY_PREFIX}{event}:{user_id}"
    try:
        redis = get_redis()
        allowed = await redis.eval(_RATE_LIMIT_LUA, 1, key, limit, 1)
    except Exception:  # noqa: BLE001
        logger.warning("聊天限流校验失败，放行 event=%s", event, exc_info=True)
        return True
    return bool(allowed)
