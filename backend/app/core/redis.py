"""Redis 客户端封装"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings

redis_client: AsyncRedis | None = None


def get_redis_url(db: int = 0) -> str:
    """构建 Redis 连接 URL"""
    password_part = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
    return f"redis://{password_part}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{db}"


async def init_redis() -> None:
    """初始化 Redis 连接（应用启动时调用）"""
    global redis_client
    redis_client = AsyncRedis.from_url(
        get_redis_url(settings.REDIS_DB),
        decode_responses=True,
    )
    # 验证连接
    await redis_client.ping()


async def close_redis() -> None:
    """关闭 Redis 连接（应用关闭时调用）"""
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None


def get_redis() -> AsyncRedis:
    """获取 Redis 客户端实例

    调用前需确保 init_redis() 已被执行。
    """
    if redis_client is None:
        raise RuntimeError("Redis client 未初始化，请先调用 init_redis()")
    return redis_client


@asynccontextmanager
async def lifespan_redis() -> AsyncIterator[None]:
    """FastAPI lifespan 上下文管理器片段

    在应用的生命周期事件中调用 init/close。
    """
    await init_redis()
    try:
        yield
    finally:
        await close_redis()
