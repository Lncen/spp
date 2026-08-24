"""图片分类初始数据"""
import uuid

from sqlmodel import Session, select

from app.core.time import get_datetime_cn
from app.modules.image.models import ImageCategory

CATEGORIES_DATA = [
    {"name": "avatar", "description": "用户头像图片", "sort_order": 1, "icon": "user"},
    {"name": "product", "description": "商品主图", "sort_order": 2, "icon": "package"},
    {"name": "product_detail", "description": "商品详情页配图", "sort_order": 3, "icon": "file-image"},
]


def seed_image_categories(*, session: Session) -> None:
    """播种默认图片分类，幂等安全（已存在则跳过）"""
    now = get_datetime_cn()

    # 遍历每一条分类数据
    for data in CATEGORIES_DATA:
        # 1. 针对当前这条数据，检查数据库中是否已存在
        existing = session.exec(
            select(ImageCategory).where(ImageCategory.name == data["name"])
        ).first()

        # 2. 如果存在，则跳过当前这一条，继续处理下一条
        if existing:
            continue  # 注意：这里用 continue，而不是 return

        # 3. 如果不存在，则创建并添加到数据库
        category_obj = ImageCategory(
            id=uuid.uuid4(),
            name=data["name"],
            description=data["description"],
            sort_order=data["sort_order"],
            icon=data["icon"],
            image_count=0,
            created_at=now,
            updated_at=now,
        )
        session.add(category_obj)

    # 4. 统一在循环结束后提交事务，提高性能并保证数据一致性
    session.commit()
