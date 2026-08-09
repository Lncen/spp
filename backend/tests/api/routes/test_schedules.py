"""计划任务模块：失败执行记录路由测试"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.core.config import settings
from app.modules.schedule.models import ScheduleRun
from app.tasks.cleanup import cleanup_schedule_runs


def test_read_failed_runs_requires_superuser(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/schedules/runs/failed",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_read_failed_runs_empty(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/schedules/runs/failed",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


def test_read_failed_runs_lists_record(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    run = ScheduleRun(
        task_id="failed-task-001",
        task_name="app.modules.product.tasks.sync_product_status",
        schedule_name="同步商品状态",
        error_type="ValueError",
        error_message="boom",
    )
    db.add(run)
    db.commit()
    response = client.get(
        f"{settings.API_V1_STR}/schedules/runs/failed",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["data"][0]["task_id"] == "failed-task-001"
    assert body["data"][0]["error_message"] == "boom"


def test_cleanup_schedule_runs_deletes_expired(db: Session) -> None:
    db.add(
        ScheduleRun(
            task_id="expired-task",
            task_name="app.tasks.cleanup.cleanup_schedule_runs",
            error_message="old",
            created_at=datetime.now(UTC) - timedelta(days=31),
        )
    )
    db.add(
        ScheduleRun(
            task_id="recent-task",
            task_name="app.tasks.cleanup.cleanup_schedule_runs",
            error_message="new",
            created_at=datetime.now(UTC),
        )
    )
    db.commit()

    stats = cleanup_schedule_runs()
    assert stats["schedule_runs_deleted"] == 1
    assert stats["errors"] == []

    expired_left = db.exec(
        select(func.count())
        .select_from(ScheduleRun)
        .where(ScheduleRun.task_id == "expired-task")
    ).one()
    recent_left = db.exec(
        select(func.count())
        .select_from(ScheduleRun)
        .where(ScheduleRun.task_id == "recent-task")
    ).one()
    assert expired_left == 0
    assert recent_left == 1
