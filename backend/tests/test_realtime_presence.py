"""Presence（在线状态）测试：多设备、断开清理、心跳续期与批量查询

通过真实的 Redis 验证生命周期：Redis 在测试环境（容器的 `redis` 服务）可用，
调用方与 `test_settings.py` 一致，使用 `run_redis_sync` 在同步测试里执行异步实现。
"""

from uuid import UUID, uuid4

import pytest

from app.core.redis import get_redis, run_redis_sync
from app.modules.realtime import manager


def _online_key(user_id: UUID) -> str:
    return f"realtime:online:{user_id}"


def test_local_connection_tracking_keeps_other_sids() -> None:
    """进程内绑定：移除一个 sid 后其余连接仍视为在线"""
    user_id = uuid4()
    manager.add_connection(user_id, "sid-a")
    manager.add_connection(user_id, "sid-b")

    assert manager.get_user_by_sid("sid-a") == user_id
    assert manager.has_local_connections(user_id) is True

    assert manager.remove_connection("sid-a") == user_id
    assert manager.has_local_connections(user_id) is True

    assert manager.remove_connection("sid-b") == user_id
    assert manager.has_local_connections(user_id) is False
    assert manager.get_user_by_sid("sid-b") is None


@pytest.mark.usefixtures("client")
def test_multi_device_disconnect_clears_empty_set() -> None:
    """多设备：单个设备断开不判离线，最后一个断开后不残留空 Set"""
    user_id = uuid4()
    key = _online_key(user_id)
    try:
        assert run_redis_sync(manager.mark_online(user_id, "sid-1")) is True
        # 同一用户第二个设备接入，不产生重复的「转为在线」
        assert run_redis_sync(manager.mark_online(user_id, "sid-2")) is False
        assert run_redis_sync(get_redis().scard(key)) == 2

        # 断开一个设备：仍在线
        assert run_redis_sync(manager.mark_offline(user_id, "sid-1")) is False
        assert run_redis_sync(get_redis().exists(key)) == 1

        # 断开最后一个设备：离线且 key 被删除（不会因空 Set 永远显示在线）
        assert run_redis_sync(manager.mark_offline(user_id, "sid-2")) is True
        assert run_redis_sync(get_redis().exists(key)) == 0
        assert run_redis_sync(manager.mark_offline(user_id, "sid-2")) is True
    finally:
        run_redis_sync(get_redis().delete(key))


@pytest.mark.usefixtures("client")
def test_heartbeat_refreshes_ttl_and_restores_sid() -> None:
    """心跳续期：TTL 被刷新到 90 秒，sid 丢失时重新登记"""
    user_id = uuid4()
    key = _online_key(user_id)
    try:
        run_redis_sync(get_redis().delete(key))
        # 模拟 worker 崩溃后 TTL 已过期：心跳应重新登记并续期
        assert run_redis_sync(manager.refresh_heartbeat(user_id, "sid-1")) is True
        assert run_redis_sync(get_redis().sismember(key, "sid-1")) == 1
        ttl = run_redis_sync(get_redis().ttl(key))
        assert 0 < ttl <= manager.PRESENCE_TTL_SECONDS
    finally:
        run_redis_sync(get_redis().delete(key))


@pytest.mark.usefixtures("client")
def test_batch_online_reports_online_state() -> None:
    """批量在线查询：按集合连接数判断，离线用户返回 False"""
    online_user = uuid4()
    offline_user = uuid4()
    key = _online_key(online_user)
    try:
        run_redis_sync(manager.mark_online(online_user, "sid-1"))

        result = manager.batch_online([online_user, offline_user])

        assert result == {str(online_user): True, str(offline_user): False}
    finally:
        run_redis_sync(get_redis().delete(key))
