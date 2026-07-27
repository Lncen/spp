from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.init_models_data.images import seed_image_categories
from app.init_models_data.levels import seed_levels
from app.modules.user.models import User
from app.modules.user.schemas import UserCreate
from app.modules.user.service import create_user

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # 播种 10 个修真等级（幂等，已有则跳过）
    default_level_id = seed_levels(session=session)

    # 播种默认图片分类（幂等，已有则跳过）
    seed_image_categories(session=session)

    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = create_user(session=session, user_create=user_in)
        # 为超级管理员分配默认等级
        user.level_id = default_level_id
        session.add(user)
        session.commit()

    # 为已存在但未分配等级的用户设置默认等级
    users_no_level = session.exec(
        select(User).where(User.level_id.is_(None))
    ).all()
    for u in users_no_level:
        u.level_id = default_level_id
        session.add(u)
    if users_no_level:
        session.commit()
