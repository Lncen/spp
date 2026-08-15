from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

import app.core.celery_app  # noqa: F401  注册默认 Celery 应用（shared_task 线程本地绑定）
from app.api.main import api_router
from app.core.config import settings
from app.core.middleware import MaintenanceMiddleware, SecurityHeadersMiddleware
from app.core.redis import close_redis, init_redis


def custom_generate_unique_id(route: APIRoute) -> str:
   return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：启动时初始化 Redis，关闭时清理"""
    await init_redis()
    if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
        import sentry_sdk
        sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)
    yield
    await close_redis()


app = FastAPI(
   title=settings.PROJECT_NAME,
   openapi_url=f"{settings.API_V1_STR}/openapi.json",
   generate_unique_id_function=custom_generate_unique_id,
   lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MaintenanceMiddleware)

# Set all CORS enabled origins
if settings.all_cors_origins:
   app.add_middleware(
       CORSMiddleware,
       allow_origins=settings.all_cors_origins,
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )

app.include_router(api_router, prefix=settings.API_V1_STR)
# 确保上传目录存在
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

# 挂载上传目录，加上 CORS 中间件以支持跨域访问
uploads_app = StaticFiles(directory=settings.UPLOAD_DIR)
if settings.all_cors_origins:
   uploads_app = CORSMiddleware(
       uploads_app,
       allow_origins=settings.all_cors_origins,
       allow_credentials=True,
       allow_methods=["GET", "HEAD", "OPTIONS"],
       allow_headers=["*"],
   )
app.mount("/uploads", uploads_app, name="uploads")
