"""用户等级模块：业务逻辑层"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.modules.level.models import UserLevel
from app.modules.level.schemas import LevelUpdate


def get_all_levels(*, session: Session) -> list[UserLevel]:
    """获取全部等级列表（按 level 升序）"""
    statement = select(UserLevel).order_by(col(UserLevel.level))
    return session.exec(statement).all()


def get_level_count(*, session: Session) -> int:
    """获取等级总数"""
    statement = select(func.count()).select_from(UserLevel)
    return session.exec(statement).one()


def get_level_by_number(*, session: Session, level: int) -> UserLevel:
    """按等级编号获取等级记录"""
    statement = select(UserLevel).where(UserLevel.level == level)
    db_level = session.exec(statement).first()
    if not db_level:
        raise HTTPException(status_code=404, detail="等级不存在")
    return db_level


def update_level(
    *, session: Session, level: int, level_in: LevelUpdate
) -> UserLevel:
    """更新等级字段"""
    db_level = get_level_by_number(session=session, level=level)

    update_dict = level_in.model_dump(exclude_unset=True)

    # 如果设置了 is_default=True，先将所有等级设为 False
    if update_dict.get("is_default") is True:
        statement = select(UserLevel).where(UserLevel.is_default == True)
        for row in session.exec(statement).all():
            row.is_default = False
            session.add(row)

    db_level.sqlmodel_update(update_dict)
    session.add(db_level)
    session.commit()
    session.refresh(db_level)
    return db_level
