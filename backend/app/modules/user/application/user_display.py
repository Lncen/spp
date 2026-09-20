"""用户模块：用户展示名与头像 URL 组装

聊天等模块需要在列表里展示「对方是谁」，展示口径与头像取值集中在这里，
避免各模块各写一套（昵称 → 用户名 → 邮箱 → 兜底 ID）。
"""

import uuid

from sqlmodel import Session, col, select

from app.modules.image.infrastructure.image_storage import build_image_url
from app.modules.image.models import Image
from app.modules.user.models import User


def user_display_name(user: User) -> str:
    """展示名：昵称 → 用户名 → 邮箱，均为空时回退为 用户 + ID 后 6 位"""
    return user.full_name or user.username or user.email or f"用户{str(user.id)[-6:]}"


def user_avatar_urls(
    *, session: Session, users: dict[uuid.UUID, User]
) -> dict[uuid.UUID, str]:
    """批量组装用户头像 URL（未设置头像或图片已删除的用户不返回）"""
    avatar_ids = {user.avatar_id for user in users.values() if user.avatar_id}
    if not avatar_ids:
        return {}
    paths = {
        image.id: image.file_path
        for image in session.exec(
            select(Image).where(col(Image.id).in_(avatar_ids))
        ).all()
    }
    return {
        user_id: build_image_url(paths[user.avatar_id])
        for user_id, user in users.items()
        if user.avatar_id is not None and user.avatar_id in paths
    }


def load_users(
    *, session: Session, user_ids: set[uuid.UUID]
) -> dict[uuid.UUID, User]:
    """按用户 ID 批量加载用户"""
    if not user_ids:
        return {}
    return {
        user.id: user
        for user in session.exec(
            select(User).where(col(User.id).in_(user_ids))
        ).all()
        if user.id is not None
    }
