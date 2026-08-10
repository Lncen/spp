from app.modules.auth.api.login import router as login_router
from app.modules.auth.api.password import router as password_router
from app.modules.auth.api.token import router as token_router

__all__= [
    "login_router",
    "password_router",
    "token_router"
]
