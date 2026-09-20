"""实时发布器单元测试：验证同步 / 异步入口按 room 发布与失败容忍"""

import asyncio
from uuid import uuid4

from app.modules.realtime import publisher
from app.modules.realtime.server import user_room


class FakeSyncManager:
    """同步发布器替身：记录 emit 调用，可指定失败的 room"""

    def __init__(self, failing_rooms: set[str] | None = None) -> None:
        self.calls: list[tuple[str, dict, str | None]] = []
        self.failing_rooms = failing_rooms or set()

    def emit(self, event, data, to=None) -> None:
        if to in self.failing_rooms:
            raise RuntimeError("redis down")
        self.calls.append((event, data, to))


class FakeAsyncManager:
    """异步发布器替身：记录 emit 调用，可指定失败的 room"""

    def __init__(self, failing_rooms: set[str] | None = None) -> None:
        self.calls: list[tuple[str, dict, str | None]] = []
        self.failing_rooms = failing_rooms or set()

    async def emit(self, event, data, to=None) -> None:
        if to in self.failing_rooms:
            raise RuntimeError("redis down")
        self.calls.append((event, data, to))


def test_publish_to_user_emits_to_user_room(monkeypatch) -> None:
    """同步入口按用户 room 发布"""
    manager = FakeSyncManager()
    monkeypatch.setattr(publisher, "_get_sync_manager", lambda: manager)
    user_id = uuid4()
    payload = {"id": "x"}
    event_name = "notification.created"

    assert publisher.publish_to_user(
        user_id,
        event_name,
        payload,
    ) is True
    assert manager.calls == [(event_name, payload, user_room(user_id))]


def test_publish_to_users_counts_successes(monkeypatch) -> None:
    """批量同步发布逐个用户投递，失败的不计入成功数"""
    user_ids = [uuid4(), uuid4()]
    manager = FakeSyncManager(failing_rooms={user_room(user_ids[1])})
    monkeypatch.setattr(publisher, "_get_sync_manager", lambda: manager)

    assert publisher.publish_to_users(user_ids, "chat.unread.updated", {}) == 1
    assert manager.calls == [
        ("chat.unread.updated", {}, user_room(user_ids[0]))
    ]


def test_sync_publish_failure_is_best_effort(monkeypatch) -> None:
    """同步发布失败只记日志，返回 False 不抛错"""
    monkeypatch.setattr(
        publisher,
        "_get_sync_manager",
        lambda: FakeSyncManager(failing_rooms={"user:x"}),
    )

    assert publisher.publish_to_room("user:x", "e", {}) is False


def test_publish_to_user_async_emits_to_user_room(monkeypatch) -> None:
    """异步入口按用户 room 发布"""
    manager = FakeAsyncManager()
    monkeypatch.setattr(publisher, "_get_async_manager", lambda: manager)
    user_id = uuid4()

    assert asyncio.run(
        publisher.publish_to_user_async(user_id, "chat.message.created", {"id": "m"})
    ) is True
    assert manager.calls == [
        ("chat.message.created", {"id": "m"}, user_room(user_id))
    ]


def test_publish_to_users_async_gathers_all_rooms(monkeypatch) -> None:
    """批量异步发布并发投递全部用户"""
    user_ids = [uuid4(), uuid4(), uuid4()]
    manager = FakeAsyncManager(failing_rooms={user_room(user_ids[2])})
    monkeypatch.setattr(publisher, "_get_async_manager", lambda: manager)

    assert asyncio.run(
        publisher.publish_to_users_async(user_ids, "chat.message.read", {"id": "c"})
    ) == 2
    assert [call[2] for call in manager.calls] == [
        user_room(user_ids[0]),
        user_room(user_ids[1]),
    ]


def test_async_publish_failure_is_best_effort(monkeypatch) -> None:
    """异步发布失败只记日志，返回 False 不抛错"""
    monkeypatch.setattr(
        publisher,
        "_get_async_manager",
        lambda: FakeAsyncManager(failing_rooms={"chat:x"}),
    )

    assert asyncio.run(
        publisher.publish_to_room_async("chat:x", "e", {})
    ) is False
