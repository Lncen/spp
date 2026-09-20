"""聊天模块：领域常量与纯规则

聊天只有两类（`ChatType`），不拆分多套模型：

- `DIRECT`：私聊，靠 `direct_key` 保证「同一对用户只有一条」，与发起方向无关；
- `GROUP`：群聊，成员显式维护，数量不限。
"""

import uuid


class ChatType:
    """聊天类型"""

    DIRECT = "DIRECT"
    GROUP = "GROUP"


class ChatStatus:
    """聊天状态"""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class ParticipantRole:
    """聊天成员角色（按聊天类型使用）"""

    # GROUP：群主 / 普通成员；DIRECT 统一使用 MEMBER
    OWNER = "OWNER"
    MEMBER = "MEMBER"


class MessageType:
    """消息类型"""

    TEXT = "TEXT"
    FILE = "FILE"


class ChatRealtimeEvent:
    """聊天模块的 Socket.IO 事件名（前端按同名事件订阅 / 发送）"""

    # 客户端 → 服务端
    SUBSCRIBE = "chat.subscribe"
    UNSUBSCRIBE = "chat.unsubscribe"
    MESSAGE_SEND = "chat.message.send"
    TYPING = "chat.typing"
    READ = "chat.read"
    # 服务端 → 客户端
    MESSAGE_CREATED = "chat.message.created"
    MESSAGE_READ = "chat.message.read"
    UNREAD_UPDATED = "chat.unread.updated"


# 按事件的初始限流参数（次 / 秒），属工程参数，不作为业务规则
RATE_LIMITS_PER_SECOND: dict[str, int] = {
    ChatRealtimeEvent.MESSAGE_SEND: 20,
    ChatRealtimeEvent.TYPING: 10,
    ChatRealtimeEvent.READ: 20,
    ChatRealtimeEvent.SUBSCRIBE: 20,
}


# 消息内容与预览长度上限（与前端输入约束、卡片展示保持一致）
MAX_MESSAGE_CONTENT_LENGTH = 2000
MAX_MESSAGE_PREVIEW_LENGTH = 200

# 消息分页：默认一页 50 条，单页最多 200 条
DEFAULT_MESSAGE_PAGE_SIZE = 50
MAX_MESSAGE_PAGE_SIZE = 200

# 权限码（定义见 init_models_data/permissions.py 的「聊天」分类）
CHAT_SELF_VIEW_PERMISSION_CODE = "chat:self_view"
CHAT_SEND_PERMISSION_CODE = "chat:send"
CHAT_CREATE_PERMISSION_CODE = "chat:create"
CHAT_GROUP_CREATE_PERMISSION_CODE = "chat:group:create"
CHAT_PARTICIPANT_MANAGE_PERMISSION_CODE = "chat:participant:manage"


def build_direct_key(user_id: uuid.UUID | str, other_user_id: uuid.UUID | str) -> str:
    """构造私聊唯一键：两个用户 ID 排序后拼接，保证 A→B 与 B→A 命中同一条聊天"""
    if str(user_id) == str(other_user_id):
        raise ValueError("私聊双方不能是同一个用户")
    first, second = sorted((str(user_id), str(other_user_id)))
    return f"{first}:{second}"


def parse_direct_key(direct_key: str) -> tuple[uuid.UUID, uuid.UUID]:
    """解析私聊唯一键，返回（较小 ID, 较大 ID）"""
    first, second = direct_key.split(":")
    return uuid.UUID(first), uuid.UUID(second)
