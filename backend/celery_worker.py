"""Celery Worker 入口

启动方式：
    celery -A celery_worker worker -l info
    celery -A celery_worker beat -l info

同时启动 worker + beat（开发环境推荐）：
    celery -A celery_worker worker -B -l info

生产环境建议分开启动以实现高可用：
    celery -A celery_worker worker --concurrency=4 -l info
    celery -A celery_worker beat -l info
"""

from app.core.celery_app import celery_app, discover_tasks

discover_tasks()

if __name__ == "__main__":
    celery_app.start()
