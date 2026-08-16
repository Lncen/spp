"""系统日志与操作审计只读查询 API 测试"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.modules.system_log.models import AuditLog, SystemLog


def test_read_system_logs_and_detail(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """写入系统日志后，可列表筛选并读取详情"""
    log = SystemLog(
        level="error",
        event_type="order.fulfillment_failed",
        module="order",
        resource_type="order",
        resource_id="ORD-1001",
        status="failed",
        context={"order_no": "ORD-1001"},
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    r = client.get(
        f"{settings.API_V1_STR}/system-logs/",
        headers=superuser_token_headers,
        params={"level": "error", "module": "order", "limit": 10},
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1
    assert any(item["id"] == str(log.id) for item in r.json()["data"])

    r = client.get(
        f"{settings.API_V1_STR}/system-logs/",
        headers=superuser_token_headers,
        params={"limit": 10},
    )
    assert r.status_code == 200

    r = client.get(
        f"{settings.API_V1_STR}/system-logs/{log.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["event_type"] == "order.fulfillment_failed"
    assert r.json()["status"] == "failed"


def test_read_audit_logs_and_detail(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """写入审计记录后，可列表筛选并读取详情"""
    audit_log = AuditLog(
        actor_identifier="admin@example.com",
        action="order.update_status",
        resource_type="order",
        resource_id="ORD-1002",
        before={"status": 1},
        after={"status": 6},
        changes={"status": {"old": 1, "new": 6}},
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    r = client.get(
        f"{settings.API_V1_STR}/audit-logs/",
        headers=superuser_token_headers,
        params={"action": "order.update_status", "limit": 10},
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1
    assert any(item["id"] == str(audit_log.id) for item in r.json()["data"])

    r = client.get(
        f"{settings.API_V1_STR}/audit-logs/",
        headers=superuser_token_headers,
        params={"limit": 10},
    )
    assert r.status_code == 200

    r = client.get(
        f"{settings.API_V1_STR}/audit-logs/{audit_log.id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["resource_id"] == "ORD-1002"
    assert r.json()["changes"]["status"]["old"] == 1
