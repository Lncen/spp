"""系统日志应用服务层"""

from app.modules.system_log.application.audit_log_create import record_audit_log
from app.modules.system_log.application.audit_log_query import (
    get_audit_log,
    list_audit_logs_page,
)
from app.modules.system_log.application.event_listen import (
    process_system_log_event,
)
from app.modules.system_log.application.system_log_query import (
    get_system_log,
    list_system_logs_page,
)

__all__ = [
    "get_audit_log",
    "get_system_log",
    "list_audit_logs_page",
    "list_system_logs_page",
    "process_system_log_event",
    "record_audit_log",
]
