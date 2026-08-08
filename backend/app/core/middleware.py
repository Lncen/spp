"""安全增强中间件"""

from collections.abc import Awaitable, Callable

from sqlmodel import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.db import engine
from app.modules.setting.service import get_setting

# 维护模式下仍然放行的接口：健康检查、登录、设置读写、OpenAPI 文档
MAINTENANCE_EXEMPT_PREFIXES: tuple[str, ...] = (
    f"{settings.API_V1_STR}/utils/health-check/",
    f"{settings.API_V1_STR}/login/access-token",
    f"{settings.API_V1_STR}/settings",
    f"{settings.API_V1_STR}/openapi.json",
)


def _is_maintenance_mode() -> bool:
    """读取维护模式开关（默认关闭）"""
    with Session(engine) as session:
        return bool(get_setting(session=session, key="maintenance_mode"))


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """添加安全响应头"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)

        # 防止 MIME 嗅探
        response.headers["X-Content-Type-Options"] = "nosniff"
        # 防止点击劫持
        response.headers["X-Frame-Options"] = "DENY"
        # 禁用不必要的 API 特性
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        if settings.ENVIRONMENT != "local":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )

        return response


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """维护模式中间件：开启时除白名单接口外全部返回 503"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if path.startswith(MAINTENANCE_EXEMPT_PREFIXES):
            return await call_next(request)
        if await run_in_threadpool(_is_maintenance_mode):
            return JSONResponse(
                status_code=503,
                content={"detail": "系统维护中，请稍后再试"},
            )
        return await call_next(request)
