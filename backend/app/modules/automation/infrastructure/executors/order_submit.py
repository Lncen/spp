"""自动化模块：订单向上游履约执行器"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlmodel import Session
from sqlalchemy import update
from app.core.db import engine
from app.modules.order.infrastructure.notification import notify_order_exception
from app.modules.automation.infrastructure.executors.base import (
    BaseExecutor,
    ExecutorTerminalError,
    register_executor,
)
from app.modules.automation.models import AutomationTask
from app.modules.order.application.fulfill_core import (
    FulfillmentUnknownError,
    claim_order,
    fulfill_claimed_order,
)
from app.modules.order.domain.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.product.constants import RedeemType

logger = logging.getLogger(__name__)

# 认领超时时间：超过该时长仍处于处理中视为执行者失联，转人工确认
CLAIM_STALE_MINUTES = 10


@register_executor("submit_supplier_order")
class SubmitSupplierOrderExecutor(BaseExecutor):
    """将已付款的 API 履约订单向上游下单，失败交由任务池重试

    幂等策略：以订单状态与 supplier_order_id 为唯一业务标识，
    订单不存在 / 非 API 履约 / 已生成上游单号均视为目标已达成（check_already_done），
    重复执行不会重复下单；并发由 claim_order 原子认领保证只履约一次。
    """

    idempotent = True

    def _parse_order_id(
        self,
        *,
        task: AutomationTask,
    ) -> uuid.UUID |None:
        """解析 payload 中的订单 ID 并加载订单，payload 非法时抛出 ValueError。"""
        try:
            return uuid.UUID(str(task.payload["order_id"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(
                f"任务 payload 缺少有效 order_id: {task.payload.get('order_id')!r}"
            ) from exc

    def _mark_stale_claim(self,*, session: Session, db_order: Order, before: datetime) -> bool:
        """认领超时订单标记异常转人工确认，不自动重新下单"""
        result = session.exec(
            update(Order)
            .where(
                Order.id == db_order.id,
                Order.status == OrderStatus.PROCESSING,
                Order.processing_at.is_not(None),
                Order.processing_at < before,
                Order.supplier_order_id.is_(None),
            )
            .values(
                status=OrderStatus.EXCEPTION,
                failed_at=datetime.now(UTC),
            )
        )
        marked = result.rowcount == 1
        session.commit()
        if marked:
            session.refresh(db_order)
            notify_order_exception(db_order=db_order)
        return marked

    def check_already_done(self, *, task: AutomationTask) -> bool:
        """检查订单是否已经达到履约目标。"""
        order_id = self._parse_order_id(task=task)

        with Session(engine) as session:
            db_order = session.get(Order, order_id)

            if db_order is None:
                return True

            return (
                    db_order.fulfillment_type != RedeemType.AUTO_API
                    or db_order.supplier_order_id is not None
            )

    def execute(self, *, task: AutomationTask) -> None:
        """执行 API 履约订单的上游下单。"""
        order_id = self._parse_order_id(task=task)

        with Session(engine) as session:
            db_order = session.get(Order, order_id)

            if db_order is None:
                logger.warning(
                    "自动化任务 %s: 订单 %s 不存在，视为完成",
                    task.id,
                    order_id,
                )
                return

            # 兜底检查：
            # check_already_done() 与 execute() 之间可能发生并发状态变化，
            # 因此这里必须基于当前 Session 中的最新订单状态再次判断。
            if db_order.fulfillment_type != RedeemType.AUTO_API or db_order.supplier_order_id is not None:
                return

            # 已进入人工异常处理流程，不再自动重试。
            if db_order.status == OrderStatus.EXCEPTION:
                raise ExecutorTerminalError(
                    f"订单 {db_order.order_no} 处于异常状态，等待人工确认"
                )

            # PROCESSING 表示订单已经被某个执行者认领。
            # 如果认领已经超时，则转人工；否则等待原执行者完成。
            if db_order.status == OrderStatus.PROCESSING:
                if self._mark_stale_claim(
                                    session=session,
                                    db_order=db_order,
                                    before=datetime.now(UTC) - timedelta(minutes=CLAIM_STALE_MINUTES),
                ):
                    raise ExecutorTerminalError(
                        f"订单 {db_order.order_no} 认领超时，已转人工确认"
                    )

                raise RuntimeError(
                    f"订单 {db_order.order_no} 仍在处理中且未超时，等待认领结果"
                )

            # 原子认领。
            #
            # False 的含义必须严格定义为：
            # 订单已经被其他执行者认领/完成，而不是数据库异常。
            if not claim_order(session=session,db_order=db_order,):
                return

            try:
                fulfill_claimed_order(session=session,db_order=db_order)
            except FulfillmentUnknownError as exc:
                # 请求结果未知：
                # 不能自动重试，否则可能导致上游重复下单。
                # fulfill_claimed_order 应负责将订单转为 EXCEPTION。
                logger.warning(
                    "订单 %s 履约结果未知，已转人工确认: %s",
                    db_order.order_no,
                    exc,
                )
            except Exception:
                # 明确失败：
                # fulfill_claimed_order 应负责回滚/恢复订单状态，
                # 然后重新抛出，让 AutomationTask 进入 retry。
                logger.exception(
                    "订单 %s 履约失败，交由任务池重试",
                    db_order.order_no,
                )
                raise
