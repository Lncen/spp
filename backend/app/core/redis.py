"""Redis 客户端封装"""

import asyncio
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager

from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings

redis_client: AsyncRedis | None = None
_event_loop: asyncio.AbstractEventLoop | None = None


def get_redis_url(db: int = 0) -> str:
    """构建 Redis 连接 URL"""
    password_part = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
    return f"redis://{password_part}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{db}"


async def init_redis() -> None:
    """初始化 Redis 连接（应用启动时调用）"""
    global redis_client, _event_loop
    _event_loop = asyncio.get_running_loop()
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


def is_redis_ready() -> bool:
    """Redis 客户端与主事件循环是否已就绪

    未就绪的场景（如 CLI 初始化脚本、Celery 冷启动）下，调用方应跳过缓存操作，
    直接回落数据库，避免产生误导性的异常日志。
    """
    return (
        redis_client is not None
        and _event_loop is not None
        and not _event_loop.is_closed()
    )


def run_redis_sync[T](awaitable: Awaitable[T], *, timeout: float = 5.0) -> T:
    """在同步上下文（如 FastAPI 线程池路由）中执行 Redis 命令

    将协程调度到应用主事件循环，避免连接跨事件循环复用。
    """
    if _event_loop is None or _event_loop.is_closed():
        raise RuntimeError("Redis 主事件循环未就绪")

    async def _run() -> T:
        return await awaitable

    future = asyncio.run_coroutine_threadsafe(_run(), _event_loop)
    return future.result(timeout=timeout)


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
