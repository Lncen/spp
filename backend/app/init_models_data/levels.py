"""用户等级初始数据"""

import uuid

from sqlmodel import Session, select

from app.core.time import get_datetime_cn
from app.modules.level.models import UserLevel


# 10 个修真等级的固定 UUID（确保幂等性）
LEVEL_UUIDS = {
    1: uuid.UUID("a0000000-0000-0000-0000-000000000001"),
    2: uuid.UUID("a0000000-0000-0000-0000-000000000002"),
    3: uuid.UUID("a0000000-0000-0000-0000-000000000003"),
    4: uuid.UUID("a0000000-0000-0000-0000-000000000004"),
    5: uuid.UUID("a0000000-0000-0000-0000-000000000005"),
    6: uuid.UUID("a0000000-0000-0000-0000-000000000006"),
    7: uuid.UUID("a0000000-0000-0000-0000-000000000007"),
    8: uuid.UUID("a0000000-0000-0000-0000-000000000008"),
    9: uuid.UUID("a0000000-0000-0000-0000-000000000009"),
    10: uuid.UUID("a0000000-0000-0000-0000-00000000000a"),
}

LEVELS_DATA = [
    {"level": 1, "name": "练气期", "description": "感悟天地灵气，踏入修炼之门", "is_default": True},
    {"level": 2, "name": "筑基期", "description": "筑就道基，脱胎换骨", "is_default": False},
    {"level": 3, "name": "金丹期", "description": "凝结金丹，寿元大增", "is_default": False},
    {"level": 4, "name": "元婴期", "description": "元婴破体而出，神识通玄", "is_default": False},
    {"level": 5, "name": "化神期", "description": "炼神返虚，天人交感", "is_default": False},
    {"level": 6, "name": "炼虚期", "description": "虚实相生，法力无边", "is_default": False},
    {"level": 7, "name": "合体期", "description": "道法自然，天人合一", "is_default": False},
    {"level": 8, "name": "大乘期", "description": "功德圆满，大乘之境", "is_default": False},
    {"level": 9, "name": "渡劫期", "description": "历经天劫，九死一生", "is_default": False},
    {"level": 10, "name": "飞升期", "description": "破碎虚空，位列仙班", "is_default": False},
]

DEFAULT_LEVEL_UUID = LEVEL_UUIDS[1]


def seed_levels(*, session: Session) -> uuid.UUID:
    """播种 10 个用户等级，幂等安全（已存在则跳过）。返回默认等级的 UUID。"""
    existing = session.exec(select(UserLevel).limit(1)).first()
    if existing:
        # 已有数据，只返回默认等级 UUID
        default = session.exec(
            select(UserLevel).where(UserLevel.is_default == True)
        ).first()
        return default.id if default else DEFAULT_LEVEL_UUID

    now = get_datetime_cn()
    for data in LEVELS_DATA:
        level_obj = UserLevel(
            id=LEVEL_UUIDS[data["level"]],
            level=data["level"],
            name=data["name"],
            description=data["description"],
            is_default=data["is_default"],
            created_at=now,
            updated_at=now,
        )
        session.add(level_obj)

    session.commit()
    return DEFAULT_LEVEL_UUID
