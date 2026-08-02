"""供应商相关异步任务"""

import uuid
from typing import Any

from celery import shared_task
from sqlmodel import Session

from app.core.db import engine
from app.modules.supplier.models import Supplier
from app.modules.supplier.service import (
    supplier_client,
    sync_upstream_product,
)
from app.modules.supplier.service.clients.base import SupplierClientError


@shared_task(ignore_result=False)
def sync_upstream_products(
    supplier_id: str,
    product_ids: list[str],
    category_id: str | None = None,
) -> dict[str, Any]:
    """逐个拉取上游商品详情并同步到本地，单个失败不阻断其余商品"""
    created: list[str] = []
    updated: list[str] = []
    failed: list[dict[str, str]] = []

    with Session(engine) as session:
        supplier = session.get(Supplier, supplier_id)
        if supplier is None:
            return {
                "status": "failed",
                "created": [],
                "updated": [],
                "failed": [
                    {"product_id": pid, "error": "供应商不存在"}
                    for pid in product_ids
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
        except SupplierClientError as e:
            return {
                "status": "failed",
                "created": [],
                "updated": [],
                "failed": [
                    {"product_id": pid, "error": str(e)} for pid in product_ids
                ],
            }

    return {
        "status": "success",
        "created": created,
        "updated": updated,
        "failed": failed,
    }
