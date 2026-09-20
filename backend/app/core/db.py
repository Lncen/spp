from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.init_models_data.automation_rules import seed_automation_rules
from app.init_models_data.images import seed_image_categories
from app.init_models_data.levels import seed_levels
from app.init_models_data.permissions import seed_permission_catalog
from app.init_models_data.price_templates import seed_price_templates
from app.init_models_data.product_category import seed_product_category_templates
from app.init_models_data.roles import DEFAULT_USER_ROLE_CODE, seed_system_roles
from app.init_models_data.supplier import seed_supplier_templates
from app.modules.authorization.models import UserRole
from app.modules.role.models import Role
from app.modules.user.application.user_create import create_user
from app.modules.user.models import User
from app.modules.user.schemas import UserCreate

# 数据库会话统一使用中国时区，保证 timestamptz 读取后即北京时间
engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    connect_args={"options": "-c timezone=Asia/Shanghai"},
)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # 播种 10 个修真等级（幂等，已有则跳过）
    default_level_id = seed_levels(session=session)

    # 播种权限定义目录（必须在系统角色之前，角色权限按权限码关联）
    seed_permission_catalog(session=session)

    # 播种系统内置角色与默认权限（幂等，不覆盖自定义角色）
    seed_system_roles(session=session)

    # 播种默认图片分类（幂等，已有则跳过）
    seed_image_categories(session=session)

    # 播种默认价格模板（幂等，已有则跳过）
    seed_price_templates(session=session)

    seed_supplier_templates(session=session)

    seed_product_category_templates(session=session)

    # 播种默认自动化规则（幂等，已有则跳过）
    seed_automation_rules(session=session)

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
            full_name="管理员_1"
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

    # 为未分配任何角色的普通用户补内置「普通用户」角色：
    # 历史账号缺少该角色时用户自助接口会因缺权限码而被拒绝
    default_role = session.exec(
        select(Role).where(Role.code == DEFAULT_USER_ROLE_CODE)
    ).first()
    if default_role is not None:
        users_without_role = session.exec(
            select(User).where(
                User.is_superuser.is_(False),
                ~User.id.in_(select(UserRole.user_id)),
            )
        ).all()
        for user in users_without_role:
            session.add(UserRole(user_id=user.id, role_id=default_role.id))
        if users_without_role:
            session.commit()
