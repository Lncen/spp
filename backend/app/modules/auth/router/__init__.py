from app.modules.auth.router.login import router as login_router
from app.modules.auth.router.password import router as password_router
from app.modules.auth.router.token import router as token_router

__all__= [
    "login_router",
    "password_router",
    "token_router"
]
