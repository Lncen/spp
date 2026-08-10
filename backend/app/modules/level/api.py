"""用户等级模块：路由层"""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.common.models import Message
from app.modules.level.models import UserLevel
from app.modules.level.schemas import LevelPublic, LevelUpdate, LevelsPublic
from app.modules.level.service import (
    get_all_levels,
    get_level_by_number,
    get_level_count,
    update_level,
)

router = APIRouter(prefix="/levels", tags=["levels"])


def _level_to_public(level_obj: UserLevel) -> LevelPublic:
    """将 UserLevel 对象转换为 LevelPublic"""
    return LevelPublic(
        level=level_obj.level,
        name=level_obj.name,
        description=level_obj.description,
        is_default=level_obj.is_default,
        id=str(level_obj.id),
    )


@router.get("/", response_model=LevelsPublic)
def read_levels(
    session: SessionDep, current_user: CurrentUser,
) -> Any:
    """获取全部等级列表"""
    levels = get_all_levels(session=session)
    count = get_level_count(session=session)
    return LevelsPublic(
        data=[_level_to_public(l) for l in levels],
        count=count,
    )


@router.get("/{level}", response_model=LevelPublic)
def read_level(
    session: SessionDep, current_user: CurrentUser, level: int,
) -> Any:
    """按等级编号获取等级详情"""
    level_obj = get_level_by_number(session=session, level=level)
    return _level_to_public(level_obj)


@router.put("/{level}", response_model=LevelPublic)
def update_level_endpoint(
    session: SessionDep,
    current_user: CurrentUser,
    level: int,
    level_in: LevelUpdate,
) -> Any:
    """更新等级信息（仅超级管理员）"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")

    level_obj = update_level(session=session, level=level, level_in=level_in)
    return _level_to_public(level_obj)
