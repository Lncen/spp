"""数据库模型聚合文件——兼容 Alembic 自动迁移

此文件仅导入并注册所有 SQLModel 表模型，
让 Alembic 的 env.py 能够通过 `from app.models import SQLModel`
获取完整的 metadata。
"""

from sqlmodel import SQLModel

from app.modules.level.models import UserLevel
from app.modules.image.models import Image, ImageCategory
from app.modules.item.models import Item
from app.modules.user.models import User
from app.modules.supplier.models import Supplier

__all__ = ["SQLModel", "UserLevel", "Item", "User", "Image", "ImageCategory", "Supplier"]
