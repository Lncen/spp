"""实时发布器单元测试：验证按用户 room 发布与失败容忍"""

import asyncio
from uuid import uuid4

from app.modules.realtime import publisher
from app.modules.realtime.events import RealtimeEvent
from app.modules.realtime.server import user_room


def test_publish_to_user_emits_to_user_room(monkeypatch):
    emitted: list[tuple[str, dict, str]] = []

    class FakeServer:
        async def emit(self, event, data, to=None):
            emitted.append((event, data, to))
            return True

    def fake_run(awaitable, *, _timeout=2.0):
        return asyncio.run(awaitable)

    monkeypatch.setattr(publisher, "_ensure_publisher", lambda: (FakeServer(), None))
    monkeypatch.setattr(publisher, "_run_sync", fake_run)

    user_id = uuid4()
    payload = {"id": "x"}

    assert publisher.publish_to_user(
        user_id,
        RealtimeEvent.NOTIFICATION_CREATED,
        payload,
    ) is True
    assert emitted == [
        (RealtimeEvent.NOTIFICATION_CREATED, payload, user_room(user_id))
    ]


def test_publish_failure_is_best_effort(monkeypatch):
    class FakeServer:
        async def emit(self, event, data, to=None):
            raise RuntimeError("redis down")

    def fake_run(awaitable, *, _timeout=2.0):
        return asyncio.run(awaitable)

    monkeypatch.setattr(publisher, "_ensure_publisher", lambda: (FakeServer(), None))
    monkeypatch.setattr(publisher, "_run_sync", fake_run)

    assert publisher.publish_to_room("user:x", "e", {}) is False
