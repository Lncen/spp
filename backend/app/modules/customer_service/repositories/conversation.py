"""客服模块：会话数据访问"""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, col, delete, select

from app.modules.customer_service.domain.constants import ConversationStatus
from app.modules.customer_service.models import Conversation, ConversationMessage
from app.modules.user.models import User


def create_conversation(
    *,
    session: Session,
    user_id: uuid.UUID,
) -> Conversation:
    """创建会话"""
    conversation = Conversation(user_id=user_id)
    session.add(conversation)
    session.flush()
    return conversation


def get_conversation(
    *,
    session: Session,
    conversation_id: uuid.UUID,
) -> Conversation | None:
    """按 ID 获取会话"""
    return session.get(Conversation, conversation_id)


def get_open_conversation_by_user(
    *,
    session: Session,
    user_id: uuid.UUID,
) -> Conversation | None:
    """获取用户的进行中会话"""
    return session.exec(
        select(Conversation)
        .where(
            col(Conversation.user_id) == user_id,
            col(Conversation.status) == ConversationStatus.OPEN,
        )
        .order_by(Conversation.created_at.desc())
    ).first()


def lock_conversation_owner(
    *,
    session: Session,
    user_id: uuid.UUID,
) -> None:
    """锁定会话所属用户行，串行化同一用户的并发建会话

    会话表没有 ``(user_id, status=open)`` 唯一约束（新增约束需改 Migration，暂不引入），
    「先查后插」在并发下会建出多条进行中会话，因此建会话前先对用户行加排他锁，
    把同一用户的并发请求串行化；锁随事务提交/回滚释放。
    仅支持行锁的数据库（PostgreSQL）生效，SQLite 等会忽略该语句。
    """
    session.exec(
        select(User.id)
        .where(col(User.id) == user_id)
        .with_for_update()
    ).first()


def list_conversations_by_user(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int,
    limit: int,
) -> tuple[int, list[Conversation]]:
    """分页查询用户自己的会话"""
    condition = col(Conversation.user_id) == user_id
    count = session.exec(
        select(func.count()).select_from(Conversation).where(condition)
    ).one()
    conversations = session.exec(
        select(Conversation)
        .where(condition)
        .order_by(
            Conversation.last_message_at.desc(),
            Conversation.created_at.desc(),
        )
        .offset(skip)
        .limit(limit)
    ).all()
    return count, list(conversations)


def list_all_conversations(
    *,
    session: Session,
    skip: int,
    limit: int,
) -> tuple[int, list[Conversation]]:
    """分页查询全部会话（管理端）"""
    count = session.exec(
        select(func.count()).select_from(Conversation)
    ).one()
    conversations = session.exec(
        select(Conversation)
        .order_by(
            Conversation.last_message_at.desc(),
            Conversation.created_at.desc(),
        )
        .offset(skip)
        .limit(limit)
    ).all()
    return count, list(conversations)


def count_unread_messages(
    *,
    session: Session,
    conversation_ids: list[uuid.UUID],
    reader_id: uuid.UUID,
) -> dict[uuid.UUID, int]:
    """批量统计各会话中他人发来且当前查看者未读的消息数（不区分发送方角色）"""
    if not conversation_ids:
        return {}
    rows = session.exec(
        select(
            ConversationMessage.conversation_id,
            func.count(),
        )
        .where(
            col(ConversationMessage.conversation_id).in_(conversation_ids),
            col(ConversationMessage.sender_id) != reader_id,
            col(ConversationMessage.read_at).is_(None),
        )
        .group_by(ConversationMessage.conversation_id)
    ).all()
    return dict(rows)


def count_unread_total(
    *,
    session: Session,
    user_id: uuid.UUID,
    can_view_all: bool,
) -> int:
    """统计当前查看者可见会话中他人发来且未读的消息总数（客服坐席统计全部会话）"""
    stmt = (
        select(func.count())
        .select_from(ConversationMessage)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(
            col(ConversationMessage.sender_id) != user_id,
            col(ConversationMessage.read_at).is_(None),
        )
    )
    if not can_view_all:
        stmt = stmt.where(col(Conversation.user_id) == user_id)
    return session.exec(stmt).one() or 0


def touch_conversation(
    *,
    conversation: Conversation,
    now: datetime,
    preview: str,
) -> None:
    """更新会话最后消息时间与预览"""
    conversation.last_message_at = now
    conversation.last_message_preview = preview[:200]


def set_conversation_status(
    *,
    conversation: Conversation,
    status: str,
) -> None:
    """更新会话状态"""
    conversation.status = status


def purge_old_conversations(
    *,
    session: Session,
    before: datetime,
    limit: int,
) -> int:
    """物理删除超期会话，返回删除条数

    超期判定以最后消息时间为准（无消息时取创建时间）：早于 ``before`` 的会话
    连同一会话消息一并删除，消息由数据库外键 ``ON DELETE CASCADE`` 级联清理；
    单次最多删除 ``limit`` 条，分批由调用方控制。
    """
    ids = session.exec(
        select(Conversation.id)
        .where(
            func.coalesce(
                Conversation.last_message_at, Conversation.created_at
            )
            < before
        )
        .order_by(Conversation.created_at)
        .limit(limit)
    ).all()
    if not ids:
        return 0
    session.exec(delete(Conversation).where(col(Conversation.id).in_(ids)))
    session.commit()
    return len(ids)
