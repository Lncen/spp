"""自动化模块：订单向上游履约执行器"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.core.db import engine
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
    mark_stale_claim,
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

    def _load_order(
        self,
        *,
        task: AutomationTask,
    ) -> tuple[uuid.UUID, Order | None]:
        """解析 payload 中的订单 ID 并加载订单，payload 非法时抛出 ValueError。"""
        try:
            order_id = uuid.UUID(str(task.payload["order_id"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(
                f"任务 payload 缺少有效 order_id: {task.payload.get('order_id')!r}"
            ) from exc
        with Session(engine) as session:
            return order_id, session.get(Order, order_id)

    def check_already_done(self, *, task: AutomationTask) -> bool:
        """业务目标已达成：订单不存在 / 非 API 履约 / 已生成上游单号。"""
        _, db_order = self._load_order(task=task)
        if db_order is None:
            return True
        return (
            db_order.fulfillment_type != RedeemType.AUTO_API
            or db_order.supplier_order_id is not None
        )

    def execute(self, *, task: AutomationTask) -> None:
        order_id, db_order = self._load_order(task=task)
        if db_order is None:
            logger.warning(
                "自动化任务 %s: 订单 %s 不存在，视为完成", task.id, order_id
            )
            return
        with Session(engine) as session:
            # _load_order 的会话已关闭，返回的是游离对象，直接传给 claim_order
            # 会在 session.refresh 时报错（订单已认领但履约未执行）。
            # 这里在当前会话重新加载，确保认领/履约操作的对象处于持久化状态。
            db_order = session.get(Order, order_id)
            if db_order is None:
                logger.warning(
                    "自动化任务 %s: 订单 %s 不存在，视为完成", task.id, order_id
                )
                return
            # 兜底防御：check_already_done 与 execute 之间订单状态理论上不变，
            # 仍保留已完成判定，避免重复下单
            if (
                db_order.fulfillment_type != RedeemType.AUTO_API
                or db_order.supplier_order_id is not None
            ):
                return
            # 订单已转异常（人工确认中）：任务视为不可重试的失败，避免被归档为 SUCCESS
            if db_order.status == OrderStatus.EXCEPTION:
                raise ExecutorTerminalError(
                    f"订单 {db_order.order_no} 处于异常状态，等待人工确认"
                )
            # 处理中订单：超时转人工确认；未超时说明认领后尚未完成，
            # 不能当作成功跳过（见下方抛错说明）
            if db_order.status == OrderStatus.PROCESSING:
                if mark_stale_claim(
                    session=session,
                    db_order=db_order,
                    before=datetime.now(UTC)
                    - timedelta(minutes=CLAIM_STALE_MINUTES),
                ):
                    raise ExecutorTerminalError(
                        f"订单 {db_order.order_no} 认领超时，已转人工确认"
                    )
                # 未超时说明认领后尚未完成（可能是本任务此前认领后异常/崩溃），
                # 不能静默返回（会被任务池归档为成功），改为可重试异常：
                # 其他执行者完成则下一轮 check_already_done 命中成功；
                # 一直未完成则由 mark_stale_claim 超时转人工确认。
                raise RuntimeError(
                    f"订单 {db_order.order_no} 仍在处理中且未超时，等待认领结果"
                )
            # 已被其他执行者认领，跳过
            if not claim_order(session=session, db_order=db_order):
                return
            try:
                fulfill_claimed_order(session=session, db_order=db_order)
            except FulfillmentUnknownError as exc:
                # 结果未知：订单已转人工确认，不自动重试
                logger.warning("订单 %s 履约结果未知，已转人工确认: %s", db_order.order_no, exc)
            except Exception:  # noqa: BLE001
                # 明确失败已回滚为 PAID，交由任务池重试
                logger.exception("订单 %s 履约失败，交由任务池重试", db_order.order_no)
                raise
