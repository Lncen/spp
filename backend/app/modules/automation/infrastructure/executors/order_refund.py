"""自动化模块：订单向上游退单申请执行器"""

import logging
import uuid

from sqlmodel import Session

from app.core.db import engine
from app.modules.automation.infrastructure.executors.base import (
    BaseExecutor,
    ExecutorTerminalError,
    register_executor,
)
from app.modules.automation.models import AutomationTask
from app.modules.order.application.sync import apply_refund_application
from app.modules.order.domain.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.product.constants import RedeemType
from app.modules.supplier.infrastructure.clients.base import (
    SupplierClientRejectedError,
)

logger = logging.getLogger(__name__)


@register_executor("apply_supplier_refund")
class ApplySupplierRefundExecutor(BaseExecutor):
    """将申请售后中的 API 订单向上游申请退单，失败交由任务池重试

    幂等策略：以订单状态、supplier_order_id 与 supplier_id 为业务唯一标识，
    不同供应商可能返回相同的上游订单号，故目标达成判定必须同时落在供应商维度上；
    订单不存在 / 非 API 履约 / 无上游单号 / 不可退 / 已非申请售后中
    均视为目标已达成（check_already_done），重复执行不会重复申请退单；
    并发防重由 apply_refund_application 的条件更新保证。
    供应商缺失或上游调用失败时订单保持 APPLYING_AFTER_SALE，
    任务按 max_retry 重试后进入失败终态，供人工介入处理。
    """

    idempotent = True

    def _parse_order_id(
        self,
        *,
        task: AutomationTask,
    ) -> uuid.UUID:
        """解析 payload 中的订单 ID，payload 非法时抛出 ValueError。"""
        try:
            return uuid.UUID(str(task.payload["order_id"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(
                f"任务 payload 缺少有效 order_id: {task.payload.get('order_id')!r}"
            ) from exc

    def check_already_done(self, *, task: AutomationTask) -> bool:
        """检查订单是否已达到退单申请目标（无需再申请）。"""
        order_id = self._parse_order_id(task=task)

        with Session(engine) as session:
            db_order = session.get(Order, order_id)
            if db_order is None:
                return True
            return (
                db_order.fulfillment_type != RedeemType.AUTO_API
                or not db_order.supplier_order_id
                or not db_order.can_refund
                or db_order.status != OrderStatus.APPLYING_AFTER_SALE
            )

    def execute(self, *, task: AutomationTask) -> None:
        """执行 API 订单的上游退单申请。"""
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
            try:
                apply_refund_application(session=session, db_order=db_order)
            except SupplierClientRejectedError as exc:
                # 上游明确业务性拒绝（如"当前订单状态不允许退款"）：
                # 重试无意义，直接进入失败终态，订单保持 APPLYING_AFTER_SALE 供人工处理
                raise ExecutorTerminalError(
                    f"订单 {db_order.order_no} 上游拒绝退单申请: {exc}"
                ) from exc
