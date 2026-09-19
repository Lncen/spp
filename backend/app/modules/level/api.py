"""用户等级模块：路由层"""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, require_permission
from app.modules.level.models import UserLevel
from app.modules.level.schemas import LevelPublic, LevelsPublic, LevelUpdate
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


@router.get(
    "/",
    dependencies=[Depends(require_permission("level:view"))],
    response_model=LevelsPublic,
)
def read_levels(session: SessionDep) -> Any:
    """获取全部等级列表"""
    levels = get_all_levels(session=session)
    count = get_level_count(session=session)
    return LevelsPublic(
        data=[_level_to_public(level_obj) for level_obj in levels],
        count=count,
    )


@router.get(
    "/{level}",
    dependencies=[Depends(require_permission("level:view"))],
    response_model=LevelPublic,
)
def read_level(session: SessionDep, level: int) -> Any:
    """按等级编号获取等级详情"""
    level_obj = get_level_by_number(session=session, level=level)
    return _level_to_public(level_obj)


@router.put(
    "/{level}",
    dependencies=[Depends(require_permission("level:update"))],
    response_model=LevelPublic,
)
def update_level_endpoint(
    session: SessionDep,
    level: int,
    level_in: LevelUpdate,
) -> Any:
    """更新等级信息"""
    level_obj = update_level(session=session, level=level, level_in=level_in)
    return _level_to_public(level_obj)
