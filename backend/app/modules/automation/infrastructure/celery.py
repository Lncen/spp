"""自动化模块：Celery 基础设施"""

from typing import Any

from celery.result import AsyncResult

from app.core.celery_app import celery_app, discover_tasks
from app.modules.automation.schemas import TaskOption, TaskStatusPublic

TASK_LABELS: dict[str, str] = {
    "app.modules.automation.infrastructure.tasks.cleanup_expired_data": "celery_清理过期数据",
    "app.modules.automation.infrastructure.tasks.cleanup_automation_task_archives" : "自动化_清理自动化任务归档数据",
    "app.modules.automation.infrastructure.tasks.automation_task_scan": "自动化_任务池扫描",
    "app.modules.automation.infrastructure.tasks.redispatch_stale_automation_events": "自动化_事件补发",
    "app.modules.automation.infrastructure.tasks.sync_order_status_periodic": "订单_同步订单状态",
    "app.modules.automation.infrastructure.tasks.sync_product_status": "商品_同步商品状态",
    "app.modules.automation.infrastructure.tasks.sync_upstream_products": "供应商_同步供应商商品",
    "app.modules.automation.infrastructure.tasks.cleanup_expired_refresh_tokens": "用户_清理过期刷新令牌",
    "app.modules.automation.infrastructure.tasks.cleanup_completed_orders": "订单_清理已完成订单",
    "app.modules.automation.infrastructure.tasks.cleanup_wallet_transactions": "钱包_清理历史流水",
    "app.modules.automation.infrastructure.tasks.requeue_stale_notification_deliveries": "通知_投递兜底扫描",
    "app.modules.automation.infrastructure.tasks.cleanup_notification_records": "通知_清理通知记录",
}


def list_task_options() -> list[TaskOption]:
    """列出可配置的 Celery 任务。"""
    discover_tasks()
    options: list[TaskOption] = []
    for name, task in sorted(celery_app.tasks.items()):
        if not (name.startswith("app.tasks.") or name.startswith("app.modules.")):
            continue
        signature = None
        if getattr(task, "__wrapped__", None) is not None:
            try:
                signature = str(task.__wrapped__)
            except Exception:  # noqa: BLE001
                signature = None
        options.append(
            TaskOption(
                value=name,
                label=TASK_LABELS.get(name, name),
                signature=signature,
                doc=task.__doc__,
            )
        )
    return options


def send_task_now(*, task_name: str, args: list[Any], kwargs: dict[str, Any]) -> str:
    """立即发送一次任务，返回 Celery 任务 ID。"""
    result = celery_app.send_task(task_name, args=args, kwargs=kwargs)
    return result.id


def fetch_task_status(task_id: str) -> TaskStatusPublic:
    """查询 Celery 任务执行状态（结果来自 Redis result backend）"""
    result = AsyncResult(task_id, app=celery_app)
    if result.state in {"PENDING", "STARTED", "RETRY"}:
        return TaskStatusPublic(status=result.state, success=None)
    if result.state == "SUCCESS":
        return TaskStatusPublic(
            status=result.state,
            success=True,
            result=result.result,
        )
    return TaskStatusPublic(status=result.state, success=False)
