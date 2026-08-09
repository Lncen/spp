"""商品相关定时任务"""

from celery import shared_task
from sqlmodel import Session, select

from app.core.db import engine
from app.modules.item.models import Item


@shared_task(ignore_result=False)
def sync_product_status() -> dict:
    """同步商品的状态

    执行逻辑（按需修改）：
    1. 检查过期商品，标记为下架
    2. 检查库存为 0 的商品，标记为缺货
    3. 更新需要同步到外部平台的商品

    返回同步统计。
    """
    stats = {
        "total_checked": 0,
        "marked_out_of_stock": 0,
        "marked_disabled": 0,
        "errors": [],
    }

    try:
        with Session(engine) as session:
            # 获取所有商品
            items = session.exec(select(Item)).all()
            stats["total_checked"] = len(items)

            for item in items:
                # TODO: 在这里添加具体的商品状态同步逻辑
                # 例如：检查库存、过期时间、外部 API 同步等
                pass

            session.commit()
    except Exception as e:
        stats["errors"].append(str(e))

    return stats
