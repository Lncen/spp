"""聊天模块：Presence 订阅授权

`realtime` 只知道「某个用户是否在线」，不知道「这个人是不是聊天参与者」。
由 `chat` 在 `chat.subscribe` 通过访问权校验后，决定当前连接可以订阅哪些
`presence:{user_id}` 房间，订阅范围严格限制为这条聊天的参与者。
"""

import uuid

from app.modules.realtime.server import presence_room, sio


async def subscribe_chat_presence(
    *,
    sid: str,
    observer_id: uuid.UUID,
    participant_ids: list[uuid.UUID],
) -> None:
    """订阅聊天参与者的在线状态（含当前用户，便于多端同步）"""
    for participant_id in _observable_ids(
        observer_id=observer_id, participant_ids=participant_ids
    ):
        await sio.enter_room(sid, presence_room(participant_id))


async def unsubscribe_chat_presence(
    *,
    sid: str,
    observer_id: uuid.UUID,
    participant_ids: list[uuid.UUID],
) -> None:
    """取消订阅聊天参与者的在线状态"""
    for participant_id in _observable_ids(
        observer_id=observer_id, participant_ids=participant_ids
    ):
        await sio.leave_room(sid, presence_room(participant_id))


def _observable_ids(
    *,
    observer_id: uuid.UUID,
    participant_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    """可观察对象：聊天参与者（去重，包含自己以便多端感知自身状态）"""
    return list(dict.fromkeys([*participant_ids, observer_id]))
