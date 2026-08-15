"""自动化模块：供应商上游商品同步 Celery 任务与任务分发"""

import uuid
from typing import Any

from celery import shared_task
from sqlmodel import Session

from app.core.celery_app import celery_app
from app.core.db import engine
from app.modules.supplier.application.sync import sync_upstream_product
from app.modules.supplier.infrastructure.clients.base import (
    SupplierClientError,
    supplier_client,
)
from app.modules.supplier.models import Supplier
from app.modules.supplier.repositories.supplier import (
    find_matched_supplier_row,
    mark_product_sync_failed,
)

SYNC_UPSTREAM_PRODUCTS_TASK = (
    "app.modules.automation.infrastructure.tasks.sync_upstream_products"
)


def dispatch_upstream_products_sync(
    *,
    supplier_id: str,
    product_ids: list[str],
    category_id: str | None = None,
) -> str:
    """发送上游商品同步任务，返回 Celery 任务 ID"""
    task = celery_app.send_task(
        SYNC_UPSTREAM_PRODUCTS_TASK,
        kwargs={
            "supplier_id": supplier_id,
            "product_ids": product_ids,
            "category_id": category_id,
        },
    )
    return task.id


@shared_task(ignore_result=False, name=SYNC_UPSTREAM_PRODUCTS_TASK)
def sync_upstream_products(
    supplier_id: str,
    product_ids: list[str],
    category_id: str | None = None,
) -> dict[str, Any]:
    """逐个拉取上游商品详情并同步到本地，单个失败不阻断其余商品"""
    created: list[str] = []
    updated: list[str] = []
    failed: list[dict[str, str]] = []

    # 任务内会反复读写 supplier，commit 后不主动过期对象，避免每商品重复 SELECT
    with Session(engine, expire_on_commit=False) as session:
        supplier = session.get(Supplier, supplier_id)
        if supplier is None:
            return {
                "status": "failed",
                "created": [],
                "updated": [],
                "failed": [
                    {"product_id": pid, "error": "供应商不存在"} for pid in product_ids
                ],
            }

        try:
            with supplier_client(
                session=session,
                supplier_id=supplier.id,
            ) as client:
                for product_id in product_ids:
                    try:
                        detail = client.query_product_detail(product_id)
                        action, local_product_id = sync_upstream_product(
                            session=session,
                            supplier=supplier,
                            detail=detail,
                            category_id=(
                                uuid.UUID(category_id) if category_id else None
                            ),
                        )
                        target = created if action == "created" else updated
                        target.append(str(local_product_id))
                    except SupplierClientError as e:
                        failed.append({"product_id": product_id, "error": str(e)})
                    except Exception as e:  # noqa: BLE001
                        failed.append({"product_id": product_id, "error": str(e)})
                    else:
                        continue
                    # 单商品同步失败：本地已存在匹配商品时回写同步异常
                    session.rollback()
                    matched = find_matched_supplier_row(
                        session=session,
                        supplier_id=supplier.id,
                        sku_id=product_id,
                    )
                    if matched is not None:
                        mark_product_sync_failed(
                            session=session,
                            product_id=matched.product_id,
                        )
        except SupplierClientError as e:
            return {
                "status": "failed",
                "created": [],
                "updated": [],
                "failed": [{"product_id": pid, "error": str(e)} for pid in product_ids],
            }

    return {
        "status": "success",
        "created": created,
        "updated": updated,
        "failed": failed,
    }
