"""系统日志事件消费应用服务"""

import logging

from sqlmodel import Session

from app.core.db import engine
from app.modules.automation.models import AutomationEvent
from app.modules.system_log.domain.event_mapping import build_system_log_record
from app.modules.system_log.repositories.system_log import create_system_log

logger = logging.getLogger(__name__)

# 不写入系统日志表的事件类型（如高频的订单支付成功）
SYSTEM_LOG_EXCLUDED_EVENT_TYPES: frozenset[str] = frozenset({"order.paid"})

def process_system_log_event(*, event: AutomationEvent) -> None:
    """将业务事件写入独立系统日志表；失败只记录错误，不影响事件分发链"""
    if event.event_type in SYSTEM_LOG_EXCLUDED_EVENT_TYPES:
        return
      
    record = build_system_log_record(event=event)
    with Session(engine) as session:
        create_system_log(session=session, record=record)
        session.commit()
    logger.info("系统日志已记录 event_type=%s event_id=%s", event.event_type, event.id)
