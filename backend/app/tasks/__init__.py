# 注册初始任务
from datetime import timedelta

from celery.schedules import crontab  # type: ignore[import-untyped]

init_tasks = {
    # # 自的同步上游商品
    # "同步上游商品": {
    #     "task": "app.modules.supplier.tasks.sync_upstream_products",
    #     "schedule": timedelta(hours=1),
    # },
    # 商品状态同步 —— 每 30 分钟执行一次
    "订单_同步订单状态": {
        "task": "app.modules.order.tasks.sync_order_status_periodic",
        "schedule": timedelta(hours=1),
    },
    "商品_同步本地商品状态": {
        "task": "app.modules.product.tasks.sync_product_status",
        "schedule": timedelta(hours=1),
    },


    # 数据清理 —— 每天凌晨 5:30 执行
    "清理_过期数据": {
        "task": "app.tasks.cleanup.cleanup_expired_data",
        "schedule": crontab(hour=5, minute=30),
    },
    # 过期刷新令牌清理 —— 每天凌晨 5:00 执行
    "清理_过期的刷新令牌": {
        "task": "app.modules.auth.tasks.cleanup_expired_refresh_tokens",
        "schedule": crontab(hour=5, minute=0),
    },


    # 自动化任务池扫描 —— 每 3 分钟认领到期任务并执行
    "自动化_任务池扫描": {
        "task": "app.modules.automation.infrastructure.tasks.automation_task_scan",
        "schedule": timedelta(seconds=30),
    },
    # 自动化任务归档数据清理 —— 每天凌晨 4:00 执行
    "自动化_归档数据清理": {
        "task": (
            "app.modules.automation.infrastructure.tasks."
            "cleanup_automation_task_archives"
        ),
        "schedule": crontab(hour=4, minute=0),
    },
}
