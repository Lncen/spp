"""全局设置模块：路由层"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUser, SessionDep, get_current_user
from app.modules.setting.schemas import (
    SettingRead,
    SettingsRead,
    SettingUpdate,
)
from app.modules.setting.service import (
    get_setting_items,
    update_setting,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get(
    "/",
    response_model=SettingsRead,
    dependencies=[Depends(get_current_user)],
)
def read_settings(session: SessionDep) -> Any:
    """获取全部设置（需登录）"""
    return SettingsRead(
        data=[SettingRead(**item) for item in get_setting_items(session=session)]
    )


@router.put("/{key}", response_model=SettingRead)
def update_setting_endpoint(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    key: str,
    setting_in: SettingUpdate,
) -> Any:
    """新增或更新全局开关（仅超级管理员）"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="权限不足")
    if not key.strip():
        raise HTTPException(status_code=422, detail="设置键不能为空")
    setting = update_setting(
        session=session,
        key=key,
        setting_in=setting_in,
        user_id=current_user.id,
    )
    return SettingRead(
        key=setting.key,
        value=setting.value,
        description=setting.description,
        updated_by=setting.updated_by,
        updated_at=setting.updated_at,
    )
