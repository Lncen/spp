"""自动化模块：商品定时同步 Celery 任务"""

from celery import shared_task
from sqlmodel import Session, select

from app.core.db import engine
from app.modules.automation.infrastructure.tasks.supplier_sync import (
    dispatch_upstream_products_sync,
)
from app.modules.product.product.models import ProductSupplier
from app.modules.supplier.models import Supplier


@shared_task(
    ignore_result=False,
    name="app.modules.automation.infrastructure.tasks.sync_product_status",
)
def sync_product_status() -> dict:
    """定时分发已同步商品的上游成本价与关闭下单状态同步

    与手动同步（POST /suppliers/{id}/upstream-products/sync）执行同一个
    sync_upstream_products 任务；本任务仅收集各供应商下已同步商品并分发，
    实际拉取与写库由 worker 异步完成。

    返回分发统计。
    """
    stats = {
        "total_checked": 0,
        "dispatched": [],
        "failed": [],
    }

    try:
        with Session(engine) as session:
            suppliers = session.exec(select(Supplier)).all()
            for supplier in suppliers:
                rows = session.exec(
                    select(ProductSupplier).where(
                        ProductSupplier.supplier_id == supplier.id
                    )
                ).all()
                product_ids = [row.sku_id for row in rows if row.sku_id]
                if not product_ids:
                    continue
                stats["total_checked"] += len(product_ids)
                task_id = dispatch_upstream_products_sync(
                    supplier_id=str(supplier.id),
                    product_ids=product_ids,
                )
                stats["dispatched"].append(task_id)
    except Exception as e:  # noqa: BLE001
        stats["failed"].append({"product_id": None, "error": str(e)})

    return stats
