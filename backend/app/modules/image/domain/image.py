"""图片模块：领域规则"""

import uuid


def can_access_image(
    *,
    image_owner_id: uuid.UUID,
    owner_is_superuser: bool,
    user_id: uuid.UUID,
    user_is_superuser: bool,
) -> bool:
    """用户是否可查看图片：超管可见全部；普通用户可见自己上传的或系统（超管）图片"""
    if user_is_superuser:
        return True
    return image_owner_id == user_id or owner_is_superuser


def can_use_as_avatar(
    *,
    image_owner_id: uuid.UUID,
    owner_is_superuser: bool,
    user_id: uuid.UUID,
) -> bool:
    """普通用户是否可将图片用作头像：自己的图片或系统（超管）默认头像"""
    return image_owner_id == user_id or owner_is_superuser
