"""自动化模块：任务池 / 事件 / 规则测试"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.core.db import engine
from app.init_models_data.automation_rules import seed_automation_rules
from app.modules.automation.domain.constants import AutomationTaskStatus
from app.modules.automation.infrastructure.tasks import automation_task_scan
from app.modules.automation.models import (
    AutomationEvent,
    AutomationRule,
    AutomationTask,
    AutomationTaskArchive,
)
from app.modules.automation.repositories.task import (
    claim_due_tasks,
    create_task,
    mark_failed,
    recover_stale_running_tasks,
)

TASK_URL = f"{settings.API_V1_STR}/automation/tasks"
EVENT_URL = f"{settings.API_V1_STR}/automation/events"
RULE_URL = f"{settings.API_V1_STR}/automation/rules"


@pytest.fixture(autouse=True)
def _clean_automation_tables() -> None:
    """每个用例前清空自动化表，保证用例相互独立。"""
    with Session(engine) as session:
        session.exec(delete(AutomationTask))
        session.exec(delete(AutomationTaskArchive))
        session.exec(delete(AutomationEvent))
        session.exec(delete(AutomationRule))
        session.commit()


@pytest.fixture(scope="module", autouse=True)
def _restore_seeded_rules_after_module() -> None:
    """模块结束后恢复种子自动化规则。

    本模块每个用例会清空 AutomationRule 表（含种子规则），
    若不恢复会破坏依赖种子规则的其他模块用例（如订单售后自动退单）。
    """
    yield
    with Session(engine) as session:
        seed_automation_rules(session=session)


def _get_archive(*, session: Session, task_id: uuid.UUID) -> AutomationTaskArchive | None:
    """按原任务 ID 查询归档记录（task_id 为归档表独立列，非主键）"""
    return session.exec(
        select(AutomationTaskArchive).where(
            AutomationTaskArchive.task_id == task_id
        )
    ).first()


def test_create_and_list_task(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.post(
        TASK_URL,
        headers=superuser_token_headers,
        json={"task_type": "log", "payload": {"msg": "hello"}, "max_retry": 2},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["task_type"] == "log"
    assert data["status"] == "pending"
    assert data["payload"] == {"msg": "hello"}

    r = client.get(
        TASK_URL,
        headers=superuser_token_headers,
        params={"limit": 50},
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_create_task_unknown_type_422(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.post(
        TASK_URL,
        headers=superuser_token_headers,
        json={"task_type": "not_exist"},
    )
    assert r.status_code == 422


def test_read_task_options(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.get(
        f"{TASK_URL}/task-options",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    values = [opt["value"] for opt in r.json()["data"]]
    assert "log" in values
    assert "submit_supplier_order" in values


def test_scan_claims_and_executes_task(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.post(
        TASK_URL,
        headers=superuser_token_headers,
        json={"task_type": "log", "payload": {}},
    )
    task_id = r.json()["id"]

    stats = automation_task_scan()
    assert stats["claimed"] == 1
    assert stats["success"] == 1

    with Session(engine) as session:
        task = session.get(AutomationTask, uuid.UUID(task_id))
        assert task is None
        archived = _get_archive(session=session, task_id=uuid.UUID(task_id))
        assert archived is not None
        assert archived.status == AutomationTaskStatus.SUCCESS


def test_task_pool_retry_then_failed() -> None:
    with Session(engine) as session:
        task = create_task(
            session=session,
            task_type="log",
            payload={},
            max_retry=1,
        )
        session.commit()
        task_id = task.id

    now = datetime.now(UTC)
    with Session(engine) as session:
        claimed = claim_due_tasks(
            session=session,
            limit=10,
            now=now + timedelta(seconds=1),
        )
        assert len(claimed) == 1
        mark_failed(session=session, task=claimed[0], error_message="e1", now=now)
        assert claimed[0].status == AutomationTaskStatus.PENDING
        assert claimed[0].retry_count == 1

    with Session(engine) as session:
        claimed = claim_due_tasks(
            session=session,
            limit=10,
            now=now + timedelta(seconds=1),
        )
        assert len(claimed) == 1
        mark_failed(session=session, task=claimed[0], error_message="e2", now=now)
        assert session.get(AutomationTask, task_id) is None
        archived = _get_archive(session=session, task_id=task_id)
        assert archived is not None
        assert archived.status == AutomationTaskStatus.FAILED
        assert archived.retry_count == 1


def test_read_task_archives(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    # 创建失败任务并归档
    with Session(engine) as session:
        task = create_task(
            session=session,
            task_type="log",
            payload={"msg": "archived"},
            max_retry=0,
        )
        session.commit()
        session.refresh(task)
        task_id = task.id
        mark_failed(
            session=session,
            task=task,
            error_message="boom",
            now=datetime.now(UTC),
        )
        assert session.get(AutomationTask, task_id) is None
        assert _get_archive(session=session, task_id=task_id) is not None

    r = client.get(
        f"{TASK_URL}/archive",
        headers=superuser_token_headers,
        params={"limit": 50},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    archived = next(
        item for item in body["data"] if item["task_id"] == str(task_id)
    )
    assert archived["status"] == "failed"
    assert archived["last_error"] == "boom"
    assert "archived_at" in archived

    # 状态过滤
    r = client.get(
        f"{TASK_URL}/archive",
        headers=superuser_token_headers,
        params={"status": "success"},
    )
    assert r.status_code == 200
    assert all(item["status"] == "success" for item in r.json()["data"])


def test_retry_and_cancel_task(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    # 重试耗尽后立即归档，可重新进入队列；重试计数清零，重新获得完整重试预算
    with Session(engine) as session:
        task = create_task(
            session=session,
            task_type="log",
            payload={},
            max_retry=1,
        )
        session.commit()
        session.refresh(task)
        task_id = task.id
        mark_failed(
            session=session,
            task=task,
            error_message="boom-1",
            now=datetime.now(UTC),
        )
        assert task.status == AutomationTaskStatus.PENDING
        assert task.retry_count == 1
        mark_failed(
            session=session,
            task=task,
            error_message="boom-2",
            now=datetime.now(UTC),
        )
        assert session.get(AutomationTask, task_id) is None
        archived = _get_archive(session=session, task_id=task_id)
        assert archived is not None
        assert archived.status == AutomationTaskStatus.FAILED
        assert archived.retry_count == 1

    r = client.post(
        f"{TASK_URL}/{task_id}/retry",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert r.json()["retry_count"] == 0
    with Session(engine) as session:
        assert session.get(AutomationTask, task_id) is not None
        assert _get_archive(session=session, task_id=task_id) is None

    r = client.post(
        f"{TASK_URL}/{task_id}/cancel",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "canceled"
    with Session(engine) as session:
        assert session.get(AutomationTask, task_id) is None
        assert _get_archive(session=session, task_id=task_id) is not None

    r = client.post(
        f"{TASK_URL}/{task_id}/cancel",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404

    r = client.post(
        f"{TASK_URL}/{task_id}/retry",
        headers=superuser_token_headers,
    )
    assert r.status_code == 422


def test_terminal_failure_archives_without_retry() -> None:
    """业务终态失败（terminal=True）跳过重试，直接失败归档。"""
    with Session(engine) as session:
        task = create_task(
            session=session,
            task_type="log",
            payload={},
            max_retry=3,
        )
        session.commit()
        session.refresh(task)
        task_id = task.id
        mark_failed(
            session=session,
            task=task,
            error_message="terminal",
            now=datetime.now(UTC),
            terminal=True,
        )
        assert session.get(AutomationTask, task_id) is None
        archived = _get_archive(session=session, task_id=task_id)
        assert archived is not None
        assert archived.status == AutomationTaskStatus.FAILED
        assert archived.retry_count == 0


def test_recover_stale_running_task() -> None:
    with Session(engine) as session:
        task = create_task(session=session, task_type="log", payload={})
        session.commit()
        task_id = task.id

    with Session(engine) as session:
        claimed = claim_due_tasks(
            session=session,
            limit=10,
            now=datetime.now(UTC) + timedelta(seconds=1),
        )
        assert len(claimed) == 1

    with Session(engine) as session:
        task = session.get(AutomationTask, task_id)
        assert task is not None
        task.updated_at = datetime.now(UTC) - timedelta(minutes=11)
        session.add(task)
        session.commit()

    with Session(engine) as session:
        recovered = recover_stale_running_tasks(
            session=session,
            before=datetime.now(UTC) - timedelta(minutes=10),
        )
        assert recovered == 1
        task = session.get(AutomationTask, task_id)
        assert task is not None
        assert task.status == AutomationTaskStatus.PENDING


def test_rule_crud_and_validation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.post(
        RULE_URL,
        headers=superuser_token_headers,
        json={
            "name": "规则-测试",
            "event_type": "order.paid",
            "action_type": "log",
            "config": {"source": "test"},
        },
    )
    assert r.status_code == 200
    rule_id = r.json()["id"]
    assert r.json()["is_active"] is True

    r = client.post(
        RULE_URL,
        headers=superuser_token_headers,
        json={"name": "规则-非法动作", "event_type": "x", "action_type": "not_exist"},
    )
    assert r.status_code == 422

    r = client.post(
        f"{RULE_URL}/{rule_id}/toggle",
        headers=superuser_token_headers,
    )
    assert r.json()["is_active"] is False

    r = client.put(
        f"{RULE_URL}/{rule_id}",
        headers=superuser_token_headers,
        json={"config": {"source": "updated"}},
    )
    assert r.json()["config"] == {"source": "updated"}

    r = client.get(RULE_URL, headers=superuser_token_headers)
    assert r.json()["count"] >= 1

    r = client.get(
        f"{RULE_URL}/{rule_id}",
        headers=superuser_token_headers,
    )
    assert r.json()["id"] == rule_id

    r = client.delete(
        f"{RULE_URL}/{rule_id}",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200


def test_event_publish_generates_task(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.post(
        RULE_URL,
        headers=superuser_token_headers,
        json={
            "name": "规则-事件生成任务",
            "event_type": "order.paid",
            "action_type": "log",
            "config": {"source": "rule"},
        },
    )
    assert r.status_code == 200

    r = client.post(
        EVENT_URL,
        headers=superuser_token_headers,
        json={"event_type": "order.paid", "payload": {"order_id": "10001"}},
    )
    assert r.status_code == 200

    with Session(engine) as session:
        events = session.exec(select(AutomationEvent)).all()
        assert len(events) == 1
        tasks = session.exec(select(AutomationTask)).all()
        assert len(tasks) == 1
        assert tasks[0].task_type == "log"
        assert tasks[0].payload == {"order_id": "10001", "source": "rule"}

    r = client.get(EVENT_URL, headers=superuser_token_headers)
    assert r.json()["count"] == 1


def test_event_dispatch_honors_rule_delay_seconds(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """规则 task_options.delay_seconds 使生成任务的 execute_at 延后"""
    r = client.post(
        RULE_URL,
        headers=superuser_token_headers,
        json={
            "name": "规则-延时执行",
            "event_type": "order.paid",
            "action_type": "log",
            "config": {"task_options": {"delay_seconds": 120}},
        },
    )
    assert r.status_code == 200

    r = client.post(
        EVENT_URL,
        headers=superuser_token_headers,
        json={"event_type": "order.paid", "payload": {"order_id": "10003"}},
    )
    assert r.status_code == 200

    with Session(engine) as session:
        task = session.exec(select(AutomationTask)).one()
        delta = task.execute_at - datetime.now(UTC)
        assert timedelta(seconds=110) <= delta <= timedelta(seconds=130)


def test_rule_disabled_skips_task_creation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    r = client.post(
        RULE_URL,
        headers=superuser_token_headers,
        json={
            "name": "规则-停用",
            "event_type": "order.paid",
            "action_type": "log",
            "config": {},
        },
    )
    rule_id = r.json()["id"]
    client.post(
        f"{RULE_URL}/{rule_id}/toggle",
        headers=superuser_token_headers,
    )

    r = client.post(
        EVENT_URL,
        headers=superuser_token_headers,
        json={"event_type": "order.paid", "payload": {"order_id": "10002"}},
    )
    assert r.status_code == 200

    with Session(engine) as session:
        tasks = session.exec(select(AutomationTask)).all()
        assert len(tasks) == 0


def test_register_executor_requires_idempotent_declaration() -> None:
    """执行器注册强制校验：未显式声明 idempotent 时注册即报错。"""
    from app.modules.automation.infrastructure.executors.base import (
        BaseExecutor,
        register_executor,
    )

    with pytest.raises(TypeError):

        @register_executor("__test_missing_idempotent__")
        class _MissingIdempotentExecutor(BaseExecutor):
            def execute(self, *, task: AutomationTask) -> None:
                pass


def test_scan_skips_execute_when_already_done(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """幂等预检查命中时，任务池直接标记成功归档，不调用 execute。"""
    from app.modules.automation.infrastructure.executors.base import (
        EXECUTORS,
        BaseExecutor,
        register_executor,
    )

    executed: list[str] = []

    @register_executor("__test_done_executor__")
    class DoneExecutor(BaseExecutor):
        idempotent = True

        def check_already_done(self, *, task: AutomationTask) -> bool:
            return True

        def execute(self, *, task: AutomationTask) -> None:
            executed.append(str(task.id))

    try:
        r = client.post(
            TASK_URL,
            headers=superuser_token_headers,
            json={"task_type": "__test_done_executor__"},
        )
        assert r.status_code == 200
        task_id = r.json()["id"]

        stats = automation_task_scan()
        assert stats["success"] == 1
        assert executed == []
        with Session(engine) as session:
            assert session.get(AutomationTask, uuid.UUID(task_id)) is None
            archived = _get_archive(
                session=session, task_id=uuid.UUID(task_id)
            )
            assert archived is not None
            assert archived.status == AutomationTaskStatus.SUCCESS
    finally:
        EXECUTORS.pop("__test_done_executor__", None)


def test_submit_supplier_order_idempotency_check(db: Session) -> None:
    """订单履约幂等判定：已生成上游单号 / 非 API 履约 / 订单不存在视为已完成。"""
    from decimal import Decimal

    from app.modules.automation.infrastructure.executors.order_submit import (
        SubmitSupplierOrderExecutor,
    )
    from app.modules.order.domain.constants import OrderStatus
    from app.modules.order.models import Order
    from app.modules.product.constants import RedeemType
    from app.modules.user.models import User
    from tests.utils.utils import random_lower_string

    user = db.exec(select(User)).first()
    assert user is not None

    def _make_order(*, fulfillment_type: RedeemType) -> Order:
        order = Order(
            order_no=random_lower_string(),
            user_id=user.id,
            status=OrderStatus.PAID,
            product_name="幂等测试商品",
            quantity=1,
            unit_price=Decimal("1.00"),
            subtotal=Decimal("1.00"),
            fulfillment_type=fulfillment_type,
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    executor = SubmitSupplierOrderExecutor()

    # API 履约、已付款、未生成上游单号：需要履约
    order = _make_order(fulfillment_type=RedeemType.AUTO_API)
    task = AutomationTask(
        task_type="submit_supplier_order",
        payload={"order_id": str(order.id)},
    )
    assert executor.check_already_done(task=task) is False

    # 已生成上游单号：目标已达成
    order.supplier_order_id = "upstream-001"
    db.add(order)
    db.commit()
    assert executor.check_already_done(task=task) is True

    # 非 API 履约：无需处理
    manual_order = _make_order(fulfillment_type=RedeemType.MANUAL)
    manual_task = AutomationTask(
        task_type="submit_supplier_order",
        payload={"order_id": str(manual_order.id)},
    )
    assert executor.check_already_done(task=manual_task) is True

    # 订单不存在：视为完成
    missing_task = AutomationTask(
        task_type="submit_supplier_order",
        payload={"order_id": str(uuid.uuid4())},
    )
    assert executor.check_already_done(task=missing_task) is True
