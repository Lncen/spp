# 注册初始任务
from datetime import timedelta

from celery.schedules import crontab

init_tasks = {
    # 自的同步上游商品数据
    "同步上游商品状态数据": {
        "task": "app.tasks.supplier.sync_upstream_products",
        "schedule": timedelta(hours=1),
    },
    # 已付款订单向上游下单 —— 每 1 分钟执行一次
    "向上游发起已付款订单": {
        "task": "app.tasks.order.fulfill_paid_orders_periodic",
        "schedule": timedelta(minutes=6),
    },
    # 商品状态同步 —— 每 30 分钟执行一次
    "同步订单状态": {
        "task": "app.tasks.order.sync_order_status_periodic",
        "schedule": timedelta(minutes=16),
    },
    "同步商品状态": {
        "task": "app.tasks.product.sync_product_status",
        "schedule": timedelta(minutes=30),
    },
    # 数据清理 —— 每天凌晨 5:30 执行
    "清理过期数据": {
        "task": "app.tasks.cleanup.cleanup_expired_data",
        "schedule": crontab(hour=5, minute=30),
    },
    # 失败执行记录清理 —— 每天凌晨 6:00 执行
    "清理超期的celery记录": {
        "task": "app.tasks.cleanup.cleanup_schedule_runs",
        "schedule": crontab(hour=6, minute=0),
        'args': (3,),
    },
}