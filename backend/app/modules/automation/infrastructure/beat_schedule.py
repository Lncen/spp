"""自动化模块：Celery beat 初始调度配置

由 celery_app 启动时写入，作为数据库计划任务的初始种子；
任务名字符串与历史保持一致，兼容既有 beat 配置与数据库计划任务。
"""

# 注册初始任务
from datetime import timedelta

from celery.schedules import crontab  # type: ignore[import-untyped]

init_tasks = {
    # # 同步上游商品
    # "同步上游商品": {
    #     "task": "app.modules.automation.infrastructure.tasks.sync_upstream_products",
    #     "schedule": timedelta(hours=1),
    # },
    # 商品状态同步 —— 每 30 分钟执行一次
    "订单_同步订单状态": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "sync_order_status_periodic"
        ),
        "schedule": timedelta(hours=1),
    },
    "商品_同步本地商品状态": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
                "sync_product_status"
        ),
        "schedule": timedelta(hours=1),
    },
    # 数据清理 —— 每天凌晨 5:30 执行
    "celery——清理过期数据": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "cleanup_expired_data"
        ),
        "schedule": crontab(hour=5, minute=30),
    },
    # 已完成订单数据清理 —— 每天凌晨 3:00 执行
    "订单_历史数据清理": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "cleanup_completed_orders"
        ),
        "schedule": crontab(hour=3, minute=0),
    },
    # 通知投递兜底扫描 —— 每 5 分钟恢复超时的 pending/sending 投递并重新入队
    "通知_投递兜底扫描": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "requeue_stale_notification_deliveries"
        ),
        "schedule": timedelta(minutes=5),
    },
    # 通知记录历史数据清理 —— 每天凌晨 3:30 执行
    "通知_历史数据清理": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "cleanup_notification_records"
        ),
        "schedule": crontab(hour=3, minute=30),
    },
    # 自动化任务归档数据清理 —— 每天凌晨 4:00 执行
    "自动化_归档数据清理": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "cleanup_automation_task_archives"
        ),
        "schedule": crontab(hour=4, minute=0),
    },
    # 自动化任务池扫描 —— 每 30 秒认领到期任务并执行
    "自动化_任务池扫描": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "automation_task_scan"
        ),
        "schedule": timedelta(seconds=30),
    },
    # 自动化事件补发 —— 每分钟扫描未完成或失败的事件
    "自动化_事件补发": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "redispatch_stale_automation_events"
        ),
        "schedule": timedelta(minutes=1),
    },
    # 钱包流水数据清理 —— 每天凌晨 4:30 执行
    "钱包_历史数据清理": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "cleanup_wallet_transactions"
        ),
        "schedule": crontab(hour=4, minute=30),
    },
    # 过期刷新令牌清理 —— 每天凌晨 5:00 执行
    "用户_清理过期的刷新令牌": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "cleanup_expired_refresh_tokens"
        ),
        "schedule": crontab(hour=5, minute=0),
    },
    # 数据备份 —— 每天凌晨 2:00 执行
    "系统_创建/清理过期数据备份": {
        "task": "app.modules.backup.infrastructure.tasks.create_backup",
        "schedule": crontab(hour=2, minute=0),
    },
}
