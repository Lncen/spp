"""用户模块：路由层。函数名保持不变以保证 OpenAPI operationId 兼容性"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.common.models import Message
from app.modules.setting.application.setting_query import get_setting
from app.modules.user.application.user_create import (
    create_user as create_user_service,
)
from app.modules.user.application.user_create import (
    register_user as register_user_service,
)
from app.modules.user.application.user_delete import (
    delete_current_user as delete_current_user_service,
)
from app.modules.user.application.user_delete import (
    delete_user as delete_user_service,
)
from app.modules.user.application.user_query import (
    get_user_by_id,
    get_user_detail,
    get_users_page,
)
from app.modules.user.application.user_update import (
    update_password_me as update_password_me_service,
)
from app.modules.user.application.user_update import (
    update_user as update_user_service,
)
from app.modules.user.application.user_update import (
    update_user_me as update_user_me_service,
)
from app.modules.user.schemas import (
    UpdatePassword,
    UserCreate,
    UserDetailPublic,
    UserListPublic,
    UserPublic,
    UserRegister,
    UserUpdate,
    UserUpdateMe,
)

# ── 公共用户路由 ──────────────────────────────────────────────
router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserListPublic,
)
def read_users(
    session: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
) -> Any:
    """获取用户列表（仅超级管理员可用）"""
    count, users = get_users_page(
        session=session, skip=skip, limit=limit, search=search
    )
    return UserListPublic(data=users, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """创建新用户（仅超级管理员可用）"""
    return create_user_service(
        session=session, user_create=user_in, send_notification=True
    )


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """更新当前用户个人信息"""
    return update_user_me_service(
        session=session, current_user=current_user, user_in=user_in
    )


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """修改当前用户密码"""
    update_password_me_service(session=session, current_user=current_user, body=body)
    return Message(message="密码修改成功")


@router.get("/me", response_model=UserPublic)
def read_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """获取当前用户信息（含自己的等级名称）"""
    return get_user_detail(session=session, user_id=current_user.id)


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """删除当前用户（超级管理员不允许删除自己，需系统设置开启）"""
    if current_user.is_superuser:
        raise HTTPException(status_code=403, detail="超级管理员不允许删除自己")
    if not get_setting(session=session, key="allow_delete_account"):
        raise HTTPException(status_code=403, detail="当前不允许删除账号")
    delete_current_user_service(session=session, current_user=current_user)
    return Message(message="用户已删除")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """用户自助注册"""
    return register_user_service(session=session, user_in=user_in)


@router.get(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserDetailPublic,
)
def read_user_by_id(user_id: uuid.UUID, session: SessionDep) -> Any:
    """根据 ID 获取用户详情（仅超级管理员可用）"""
    user = get_user_detail(session=session, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """更新用户信息（仅超级管理员可用）"""
    db_user = get_user_by_id(session=session, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="该用户不存在")
    return update_user_service(session=session, db_user=db_user, user_in=user_in)


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """删除用户（仅超级管理员可用，不允许删除自己）"""
    user = get_user_by_id(session=session, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user == current_user:
        raise HTTPException(status_code=403, detail="超级管理员不允许删除自己")
    delete_user_service(session=session, user=user, user_id=user_id)
    return Message(message="用户已删除")
