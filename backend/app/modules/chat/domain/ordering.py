"""聊天模块：消息顺序规则

消息主键是 UUID v4，没有时间顺序，因此「谁更新」一律按 `(created_at, id)` 判断：

- 分页与未读数使用 `(created_at, id)` 升序；
- 已读游标与 `Chat.last_message_*` 只允许沿该顺序向前推进。

本模块只放纯规则，不依赖数据库与 Web 框架。
"""

from datetime import datetime


def is_after(
    *,
    created_at: datetime,
    message_id: object,
    than_created_at: datetime | None,
    than_message_id: object | None,
) -> bool:
    """判断 `(created_at, message_id)` 是否晚于参照位置

    参照位置为空（还没有游标 / 还没有最后消息）时，任何消息都算更新。
    """
    if than_created_at is None or than_message_id is None:
        return True
    if created_at > than_created_at:
        return True
    if created_at < than_created_at:
        return False
    return str(message_id) > str(than_message_id)


def build_preview(*, message_type: str, content: str, file_name: str | None) -> str:
    """构造聊天列表的最后消息预览（文件消息显示文件名）"""
    if message_type == "FILE":
        return file_name or "[文件]"
    return content
