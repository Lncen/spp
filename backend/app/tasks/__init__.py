# 注册初始任务
from datetime import timedelta

from celery.schedules import crontab  # type: ignore[import-untyped]

init_tasks = {
    # # 自的同步上游商品
    # "同步上游商品": {
    #     "task": "app.modules.supplier.tasks.sync_upstream_products",
    #     "schedule": timedelta(hours=1),
    # },
    # 已付款订单向上游下单 —— 每 1 分钟执行一次
    "订单_向上游下单": {
        "task": "app.modules.order.tasks.fulfill_paid_orders_periodic",
        "schedule": timedelta(seconds=372),
    },
    # 商品状态同步 —— 每 30 分钟执行一次
    "订单_同步订单状态": {
        "task": "app.modules.order.tasks.sync_order_status_periodic",
        "schedule": timedelta(seconds=333),
    },
    "商品_同步本地商品状态": {
        "task": "app.modules.product.tasks.sync_product_status",
        "schedule": timedelta(minutes=30),
    },
    # 数据清理 —— 每天凌晨 5:30 执行
    "清理_过期数据": {
        "task": "app.tasks.cleanup.cleanup_expired_data",
        "schedule": crontab(hour=5, minute=30),
    },
    # 失败执行记录清理 —— 每天凌晨 6:00 执行
    "清理_超期的celery记录": {
        "task": "app.tasks.cleanup.cleanup_schedule_runs",
        "schedule": crontab(hour=6, minute=0),
        'args': (3,),
    },
    # 过期刷新令牌清理 —— 每天凌晨 5:00 执行
    "清理_过期的刷新令牌": {
        "task": "app.modules.auth.tasks.cleanup_expired_refresh_tokens",
        "schedule": crontab(hour=5, minute=0),
    },
}
